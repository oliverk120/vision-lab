from fractions import Fraction
import av
import numpy as np
import pytest


def make_video(path, times=None, scene='moving'):
    times = times or [i*100 for i in range(20)]
    with av.open(str(path),'w') as container:
        stream=container.add_stream('mpeg4',rate=10)
        stream.width=64
        stream.height=48
        stream.pix_fmt='yuv420p'
        stream.time_base=Fraction(1,1000)
        stream.codec_context.time_base=Fraction(1,1000)
        for i,t in enumerate(times):
            pixels=np.full((48,64,3),20,dtype=np.uint8)
            if scene=='moving':
                pixels[16:24,(i*2)%48:(i*2)%48+8]=220
            elif scene=='brightness':
                pixels[:]=20 if i<10 else 180
            elif scene=='short_event' and i==5:
                pixels[16:24,20:28]=220
            frame=av.VideoFrame.from_ndarray(pixels,format='rgb24')
            frame.pts=t
            frame.time_base=Fraction(1,1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


@pytest.fixture
def video(tmp_path):
    return make_video(tmp_path/'video.mp4')


@pytest.fixture
def vfr(tmp_path):
    return make_video(tmp_path/'vfr.mov',[1000,1100,1250,1500,1900,2000])
