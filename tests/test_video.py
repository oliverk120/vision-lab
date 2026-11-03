from fractions import Fraction
import hashlib
import zipfile
import json
import numpy as np
import pytest
from conftest import make_video
from vision_lab.sources import FileSource
from vision_lab.streams import StreamConfig, Sampler, sample_index, transform, enlarge
from vision_lab.sources.replay import Replay
from vision_lab.cache import RollingCache, CacheError
from vision_lab.export import export_frames


def test_vfr_decode_and_mapping(vfr):
    digest=hashlib.sha256(vfr.read_bytes()).hexdigest()
    source=FileSource(vfr,'test')
    frames=list(source.frames())
    assert [f.timestamp for f in frames]==list(map(Fraction,['0','.1','.25','.5','.9','1']))
    assert source.metadata['vfr']
    assert source.metadata['codec']=='mpeg4'
    assert frames[2].pixels.shape==(48,64,3)
    assert not frames[2].pixels.flags.writeable
    assert frames[2].pts*frames[2].time_base-source.origin==Fraction(1,4)
    assert source.get(2).timestamp==frames[2].timestamp
    assert hashlib.sha256(vfr.read_bytes()).hexdigest()==digest


def test_sampling(vfr):
    source=FileSource(vfr)
    c=StreamConfig(32,32,'gray',4)
    assert [i for i,_ in sample_index(source,c)]==[0,2,3,4,5]
    assert [t for _,t in sample_index(source,c)]==list(map(Fraction,['0','.25','.5','.75','1']))
    s=Sampler(c)
    samples=[x for f in source.frames() if (x:=s.consume(f)) is not None]
    assert [x.frame.sequence for x in samples]==[0,2,3,4,5]
    assert s.accept(Fraction(1)) is None
    assert samples[0].pixels.shape==(32,32)
    rgb=transform(source.get(0),StreamConfig(320,320,'rgb',1))
    assert rgb.pixels.shape==(320,320,3)
    assert rgb.transform['top']==40
    assert np.all(rgb.pixels[:40]==0)
    assert enlarge(samples[0].pixels,64).shape==(64,64)
    fast=sample_index(source,StreamConfig(fps=120))
    assert len(fast)==len(source.index)


def test_color_conversion(video):
    from dataclasses import replace
    frame=FileSource(video).get(0)
    pixels=np.zeros_like(frame.pixels)
    pixels[:,:,0]=255
    gray=transform(replace(frame,pixels=pixels),StreamConfig(64,48,'gray',1))
    assert np.all(gray.pixels==76)  # RGB red, not BGR blue


def test_cache_boundaries(vfr):
    source=FileSource(vfr)
    cache=RollingCache(source,.5)
    with pytest.raises(CacheError,match='NOT_YET'):
        cache.frame_at(0)
    frames=list(source.frames())
    for f in frames[:4]:
        cache.ingest(f)
    assert cache.frame_at(0).sequence==0
    assert cache.frame_at(.4).sequence==2
    with pytest.raises(CacheError,match='NOT_YET'):
        cache.frame_at(.6)
    cache.ingest(frames[4])
    with pytest.raises(CacheError,match='EXPIRED'):
        cache.frame_at(.25)
    with pytest.raises(CacheError,match='NO_FRAME'):
        cache.frame_at(.4)
    assert [f.sequence for f in cache.frames_between(.5,.9)]==[3,4]
    with pytest.raises(CacheError,match='NOT_YET'):
        list(cache.frames_between(.5,1))
    assert cache.crop_at(.5,(0,0,8,8))[1].shape==(8,8,3)
    cache.reset(1)
    with pytest.raises(CacheError,match='STALE_EPOCH'):
        cache.ingest(frames[0])
    new=source.get(3,1)
    cache.ingest(new)
    with pytest.raises(CacheError,match='OUTSIDE_EPOCH'):
        cache.frame_at(.25)


def test_cache_revalidates_race(video):
    source=FileSource(video)
    cache=RollingCache(source)
    cache.ingest(source.get(0))
    original=source.get
    def racing_get(seq,epoch=0):
        result=original(seq,epoch)
        cache.reset(1)
        return result
    source.get=racing_get
    with pytest.raises(CacheError,match='STALE_EPOCH'):
        cache.frame_at(0)


def test_replay_clock_pause_speed_seek_loop(vfr):
    now=[100.]
    replay=Replay(FileSource(vfr),{'A':StreamConfig(fps=4)},clock=lambda:now[0])
    replay.play()
    assert replay.tick()==1
    now[0]+=.1
    assert replay.tick()==1
    replay.pause()
    position=replay.position
    now[0]+=100
    assert replay.position==position
    assert replay.tick()==0
    replay.play()
    replay.set_speed(2)
    now[0]+=.07501
    assert replay.tick()==1
    assert replay.frame.sequence==2
    epoch=replay.epoch
    replay.seek(.5)
    assert replay.epoch==epoch+1 and not replay.playing
    assert replay.cache.watermark is None and not replay.latest
    replay.play()
    replay.tick()
    assert replay.frame.sequence==3
    replay.set_mode('offline')
    replay.play()
    replay.tick()
    assert replay.eof
    replay.loop=True
    replay.restart()
    replay.play()
    epoch=replay.epoch
    replay.tick(20)
    assert replay.epoch==epoch+1 and replay.playing
    assert replay.cache.watermark is None
    replay.close()


def test_offline_reproducible(vfr):
    sequences=[]
    for _ in range(2):
        r=Replay(FileSource(vfr),{'A':StreamConfig(fps=4),'B':StreamConfig(fps=1)})
        r.set_mode('offline')
        r.play()
        out=[]
        while not r.eof:
            if r.tick(1):
                out.append((r.frame.sequence,str(r.frame.timestamp),tuple((k,v.frame.sequence) for k,v in r.latest.items())))
        sequences.append(out)
        r.close()
    assert sequences[0]==sequences[1]


@pytest.mark.parametrize('scene',['moving','stationary','brightness','short_event'])
def test_synthetic_scenes(tmp_path,scene):
    source=FileSource(make_video(tmp_path/(scene+'.mp4'),scene=scene))
    frames=list(source.frames())
    changes=[np.mean(np.abs(f.pixels.astype(float)-frames[0].pixels.astype(float))) for f in frames]
    if scene=='stationary':
        assert max(changes)<2
    else:
        assert max(changes)>1
    if scene=='short_event':
        assert 5 not in [i for i,_ in sample_index(source,StreamConfig(fps=1))]


def test_export(video,tmp_path):
    source=FileSource(video)
    path=export_frames(source,StreamConfig(fps=2),.5,1.5,tmp_path/'frames.zip')
    with zipfile.ZipFile(path) as archive:
        records=json.loads(archive.read('timestamps.json'))
        assert [r['timestamp'] for r in records]==['1/2','1','3/2']
        assert all(r['file'] in archive.namelist() for r in records)


def test_invalid_inputs(tmp_path):
    bad=tmp_path/'bad.mp4'
    bad.write_bytes(b'not video')
    with pytest.raises(Exception):
        FileSource(bad)
    for kwargs in ({'fps':0},{'fps':float('nan')},{'width':0},{'color':'bgr'}):
        with pytest.raises(ValueError):
            StreamConfig(**kwargs)
