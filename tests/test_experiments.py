from dataclasses import asdict
import io
import json
import zipfile
import pytest
from vision_lab.library import Library, validate_annotations
from vision_lab.streams import StreamConfig
from vision_lab.experiments import run_batch, summaries, comparison, export_run, import_run, delete_video_results
from vision_lab.experiments.evaluation import EvaluationConfig, evaluate, confusion, truth_at


def annotations(motion='Yes',intervals=None):
    return dict(motion=motion,description='',definition='physical motion',tags=[],split='development',intervals=intervals or [])


def interval(start,end,target='Yes',id='a'):
    return dict(id=id,start=start,end=end,target=target,category='test',description='')


def predictions(values):
    return [dict(timestamp=t,detected=bool(p),score=float(p)) for t,p in values]


def test_confusion():
    m=confusion(2,1,6,1)
    assert m['precision']==pytest.approx(2/3)
    assert m['recall']==pytest.approx(2/3)
    assert m['f1']==pytest.approx(2/3)
    assert m['accuracy']==.8
    assert m['balanced_accuracy']==pytest.approx((2/3+6/7)/2)
    assert confusion()['accuracy'] is None
    assert confusion(tn=7)['balanced_accuracy'] is None


def test_temporal_evaluation_and_unknown():
    a=annotations(intervals=[interval(1,3),interval(3,5,'No','b')])
    p=predictions([(0,1),(1,0),(2,1),(3,0),(4,1),(5,1)])
    m=evaluate(p,a,6,EvaluationConfig())
    assert m['temporal']['tp']==1 and m['temporal']['fn']==1
    assert m['temporal']['fp']==1 and m['temporal']['tn']==1
    assert m['evaluated_seconds']==4
    assert m['events']['detected']==1 and m['events']['missed']==0
    assert m['events']['latency_mean_seconds']==1
    assert m['events']['false_alarms']==1
    assert m['events']['false_alarms_per_minute']==30
    assert m['events']['ignored_unmatched']==[[0.,1.]]
    assert m['video']['tp']==1
    assert truth_at(a,3)=='No' and truth_at(a,5)=='Unknown'


def test_grouping_matching_and_incomplete_coverage():
    p=predictions([(0,1),(1,0),(2,1)])
    a=annotations(intervals=[interval(0,1),interval(2,3,id='b')])
    m=evaluate(p,a,4,EvaluationConfig(allowable_gap=1))
    assert m['events']['predicted']==[[0,3]]
    assert m['events']['detected']==1 and m['events']['missed']==1  # one-to-one
    assert evaluate(p,a,4,EvaluationConfig(minimum_duration=2))['events']['predicted']==[]
    short=annotations(intervals=[interval(.2,.3)])
    m=evaluate(predictions([(0,0),(1,0)]),short,2,EvaluationConfig(max_sample_hold=.1))
    assert m['events']['missed']==1
    assert m['uncovered_labeled_seconds']==pytest.approx(.1)
    assert m['temporal']['recall'] is None
    unknown=evaluate(p,annotations('Unknown'),4,EvaluationConfig())
    assert unknown['video']['excluded']==1 and unknown['temporal']['accuracy'] is None


def test_tolerance_and_threshold():
    p=predictions([(1.1,1)])
    a=annotations(intervals=[interval(0,1)])
    assert evaluate(p,a,2,EvaluationConfig())['events']['detected']==0
    assert evaluate(p,a,2,EvaluationConfig(tolerance=.2))['events']['detected']==1
    with pytest.raises(ValueError):
        EvaluationConfig(threshold=2)


def test_annotations_overlap():
    a=annotations(intervals=[interval(0,1),interval(.5,1.5,'Unknown','b')])
    assert validate_annotations(a,2)==a
    a['intervals'][1]['target']='No'
    with pytest.raises(ValueError,match='conflict'):
        validate_annotations(a,2)
    with pytest.raises(ValueError):
        validate_annotations(annotations(intervals=[interval(1,3)]),2)


def test_library_persistence_export_import_and_delete(video,tmp_path):
    library=Library(tmp_path/'data')
    original=video.read_bytes()
    meta=library.add(io.BytesIO(original),'phone.MP4')
    assert library.path(meta['id']).read_bytes()==original
    a=annotations(intervals=[interval(.2,.8)])
    library.save_annotations(meta['id'],a)
    library.rename(meta['id'],'Test','Notes')
    assert Library(tmp_path/'data').annotations(meta['id'])==a
    exported=library.export()
    second=Library(tmp_path/'other')
    copy=second.add(io.BytesIO(original),'renamed.mp4')
    assert copy['id']!=meta['id']
    assert second.import_annotations(exported)==(1,[])
    assert second.annotations(copy['id'])==a
    with pytest.raises(ValueError):
        library.directory('../escape')
    library.delete(meta['id'])
    assert not library.list()
    with pytest.raises(ValueError):
        library.add(io.BytesIO(original),'phone.mp4',max_bytes=1)
    assert not library.list()


def test_batch_storage_reproducible_and_portable(video,tmp_path):
    library=Library(tmp_path/'data')
    meta=library.add(io.BytesIO(video.read_bytes()),'test.mp4')
    library.save_annotations(meta['id'],annotations(intervals=[interval(.2,.8),interval(1,1.8,'No','b')]))
    candidates=[dict(name='mock_pulse',config={'period_seconds':1}),dict(name='mock_never',config={})]
    runs=tmp_path/'runs'
    ids=[run_batch(library,[meta['id']],candidates,StreamConfig(fps=5),EvaluationConfig(max_sample_hold=.2),runs) for _ in range(2)]
    rows=summaries(runs)
    assert len(rows)==4 and len(comparison(rows))==4
    configurations=[json.loads((runs/i/'config.json').read_text()) for i in ids]
    all_predictions=[]
    for manifest in configurations:
        assert manifest['status']=='complete'
        p=json.loads((runs/manifest['id']/manifest['combinations'][0]['id']/'predictions.json').read_text())
        assert len(p)==10
        assert all('processing_seconds' in row for row in p)
        all_predictions.append([{k:v for k,v in row.items() if k!='processing_seconds'} for row in p])
    assert all_predictions[0]==all_predictions[1]
    exported=export_run(runs/ids[0])
    assert import_run(exported,tmp_path/'imported')==ids[0]
    with pytest.raises(ValueError,match='already exists'):
        import_run(exported,tmp_path/'imported')
    delete_video_results(meta['id'],runs)
    assert summaries(runs)==[]


def test_archive_path_traversal(video,tmp_path):
    library=Library(tmp_path/'data')
    meta=library.add(io.BytesIO(video.read_bytes()),'test.mp4')
    run=run_batch(library,[meta['id']],[dict(name='mock_never',config={})],StreamConfig(fps=1),EvaluationConfig(),tmp_path/'runs')
    payload=io.BytesIO(export_run(tmp_path/'runs'/run))
    with zipfile.ZipFile(payload,'a') as archive:
        archive.writestr('../outside','bad')
    with pytest.raises(ValueError,match='Unexpected'):
        import_run(payload.getvalue(),tmp_path/'imported')


def test_ten_videos_ten_configurations(video,tmp_path):
    library=Library(tmp_path/'data')
    ids=[library.add(io.BytesIO(video.read_bytes()),f'video-{i}.mp4')['id'] for i in range(10)]
    candidates=[dict(name='mock_pulse',config={'period_seconds':i+1}) for i in range(10)]
    run=run_batch(library,ids,candidates,StreamConfig(fps=1),EvaluationConfig(),tmp_path/'runs')
    manifest=json.loads((tmp_path/'runs'/run/'config.json').read_text())
    assert manifest['status']=='complete'
    assert len(manifest['combinations'])==100
    assert len(summaries(tmp_path/'runs'))==100
    delete_video_results(ids[0],tmp_path/'runs')
    assert len(summaries(tmp_path/'runs'))==90
