"""Sequential, bounded-image-memory experiment runs with portable local results."""
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import uuid
import zipfile

from PIL import Image
from vision_lab.library import read_json, write_json
from vision_lab.motion import REGISTRY
from vision_lab.sources import FileSource
from vision_lab.streams import Sampler, StreamConfig
from vision_lab.experiments.evaluation import EvaluationConfig, evaluate, confusion


def code_version():
    try:
        commit = subprocess.check_output(['git','rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip())
        return dict(commit=commit,dirty=dirty)
    except (OSError, subprocess.CalledProcessError):
        return dict(commit=None,dirty=None)


def run_batch(library, video_ids, candidates, stream, evaluation, root='runs', progress=None):
    if not video_ids or not candidates:
        raise ValueError('Select videos and at least one algorithm configuration')
    for c in candidates:
        if c['name'] not in REGISTRY:
            raise ValueError('Unknown algorithm')
    experiment_id = str(uuid.uuid4())
    folder = Path(root)/experiment_id
    folder.mkdir(parents=True)
    lock = Path('uv.lock')
    manifest = dict(schema_version=1, id=experiment_id, date=datetime.now(timezone.utc).isoformat(),
                    code=code_version(), python=platform.python_version(), platform=platform.platform(),
                    cpu=platform.processor(), available_cpu_count=os.cpu_count(),
                    dependencies={n:importlib.metadata.version(n) for n in ('av','numpy','opencv-python-headless','streamlit')},
                    lock_sha256=hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None,
                    stream=asdict(stream), evaluation=asdict(evaluation), candidates=candidates,
                    videos=video_ids, mode='offline', status='running', combinations=[])
    write_json(folder/'config.json', manifest)
    total = len(video_ids)*len(candidates)
    try:
        for video_id in video_ids:
            source = FileSource(library.path(video_id),video_id)
            metadata = read_json(library.directory(video_id)/'metadata.json')
            annotations = library.annotations(video_id)
            for candidate in candidates:
                combo_id = str(uuid.uuid4())
                output = folder/combo_id
                output.mkdir()
                detector = REGISTRY[candidate['name']](candidate['config'])
                detector.reset()
                sampler = Sampler(stream)
                predictions = []
                started = time.perf_counter()
                for frame in source.frames():
                    sample = sampler.consume(frame)
                    if sample is None:
                        continue
                    before = time.perf_counter()
                    prediction = detector.process(sample)
                    elapsed = time.perf_counter()-before
                    artifacts = {}
                    images = dict(prediction.debug)
                    if prediction.mask is not None:
                        images['mask'] = prediction.mask
                    for index,(label,pixels) in enumerate(images.items()):
                        relative = f'artifacts/{frame.sequence:08d}_{index}.png'
                        (output/'artifacts').mkdir(exist_ok=True)
                        Image.fromarray(pixels).save(output/relative)
                        artifacts[label] = relative
                    predictions.append(dict(sequence=frame.sequence, pts=frame.pts, time_base=str(frame.time_base),
                                            timestamp=float(frame.timestamp), exact_timestamp=str(frame.timestamp),
                                            target=str(sample.target), detected=prediction.detected, score=prediction.score,
                                            processing_seconds=elapsed, artifacts=artifacts))
                runtime = time.perf_counter()-started
                metrics = evaluate(predictions, annotations, float(source.duration), evaluation)
                cost = sum(p['processing_seconds'] for p in predictions)
                metrics.update(processed_frames=len(predictions), processing_seconds=cost,
                               average_processing_seconds=cost/len(predictions) if predictions else None,
                               total_runtime_seconds=runtime, missed_sampling_targets=sampler.missed)
                write_json(output/'metrics.json',metrics)
                write_json(output/'predictions.json',predictions)
                with (output/'predictions.csv').open('w',newline='') as handle:
                    writer = csv.DictWriter(handle,fieldnames=['sequence','pts','time_base','timestamp','exact_timestamp','target','detected','score','processing_seconds','artifacts'])
                    writer.writeheader()
                    writer.writerows({**p,'artifacts':json.dumps(p['artifacts'])} for p in predictions)
                record = dict(id=combo_id, video_id=video_id, metadata=metadata, annotations=annotations,
                              algorithm=candidate['name'], version=detector.version, configuration=candidate['config'])
                manifest['combinations'].append(record)
                write_json(folder/'config.json',manifest)
                if progress:
                    progress(len(manifest['combinations'])/total)
        manifest['status']='complete'
    except Exception as exc:
        manifest.update(status='failed', error=str(exc))
        raise
    finally:
        write_json(folder/'config.json',manifest)
    return experiment_id


def summaries(root='runs'):
    rows=[]
    for path in sorted(Path(root).glob('*/config.json')):
        manifest=read_json(path)
        for c in manifest['combinations']:
            m=read_json(path.parent/c['id']/'metrics.json')
            rows.append(dict(experiment=manifest['id'], combination=c['id'], video=c['video_id'],
                             video_name=c['metadata']['name'], split=c['annotations']['split'],
                             algorithm=c['algorithm'], configuration=json.dumps(c['configuration'],sort_keys=True),
                             **m['video'], temporal_precision=m['temporal']['precision'], temporal_recall=m['temporal']['recall'],
                             false_alarms_per_minute=m['events']['false_alarms_per_minute'],
                             average_processing_seconds=m['average_processing_seconds'],
                             total_runtime_seconds=m['total_runtime_seconds'], processed_frames=m['processed_frames'],
                             processing_seconds=m['processing_seconds']))
    return rows


def comparison(rows):
    groups={}
    for row in rows:
        key=(row['experiment'],row['algorithm'],row['configuration'],row['split'])
        groups.setdefault(key,[]).append(row)
    output=[]
    for (experiment,algorithm,configuration,split),items in groups.items():
        counts={k:sum(i[k] for i in items) for k in ('tp','fp','tn','fn')}
        output.append(dict(experiment=experiment,algorithm=algorithm,configuration=configuration,split=split,
                           videos=len(items),**confusion(**counts),
                           false_alarms_per_minute_mean=(sum(v for i in items if (v:=i['false_alarms_per_minute']) is not None)/sum(i['false_alarms_per_minute'] is not None for i in items)) if any(i['false_alarms_per_minute'] is not None for i in items) else None,
                           average_processing_seconds=sum(i['processing_seconds'] for i in items)/max(1,sum(i['processed_frames'] for i in items)),
                           total_runtime_seconds=sum(i['total_runtime_seconds'] for i in items)))
    return output


def export_run(folder):
    folder=Path(folder)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob('*'):
            if path.is_file():
                archive.write(path,path.relative_to(folder))
    return stream.getvalue()


def import_run(payload, root='runs', max_bytes=100*1024*1024):
    # Validate archive before extracting: no arbitrary paths or overwrite.
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if sum(i.file_size for i in archive.infolist()) > max_bytes:
            raise ValueError('Result archive exceeds 100 MiB uncompressed')
        manifest=json.loads(archive.read('config.json'))
        if manifest.get('schema_version')!=1:
            raise ValueError('Unsupported results schema')
        run_id=str(uuid.UUID(manifest['id']))
        allowed={'config.json'}
        for c in manifest['combinations']:
            cid=str(uuid.UUID(c['id']))
            if cid!=c['id']:
                raise ValueError('Invalid combination ID')
            for filename in ('metrics.json','predictions.json','predictions.csv'):
                allowed.add(cid+'/'+filename)
            predictions=json.loads(archive.read(cid+'/predictions.json'))
            for p in predictions:
                for relative in p.get('artifacts',{}).values():
                    path=Path(relative)
                    if path.is_absolute() or '..' in path.parts or len(path.parts)!=2 or path.parts[0]!='artifacts' or path.suffix!='.png':
                        raise ValueError('Unsafe artifact path')
                    allowed.add(cid+'/'+relative)
            json.loads(archive.read(cid+'/metrics.json'))
        if set(archive.namelist()) != allowed:
            raise ValueError('Unexpected or missing files in results archive')
        destination=Path(root)/run_id
        if destination.exists():
            raise ValueError('Experiment already exists; import never overwrites results')
        destination.mkdir(parents=True)
        try:
            for name in allowed:
                path=destination/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(archive.read(name))
        except Exception:
            import shutil
            shutil.rmtree(destination)
            raise
    return run_id


def delete_video_results(video_id, root='runs'):
    """Remove only this video's combinations, preserving other batch results."""
    import shutil
    for path in Path(root).glob('*/config.json'):
        manifest=read_json(path)
        retained=[]
        for combination in manifest['combinations']:
            if combination['video_id']==video_id:
                shutil.rmtree(path.parent/combination['id'])
            else:
                retained.append(combination)
        if not retained:
            if video_id in manifest['videos']:
                shutil.rmtree(path.parent)
        elif len(retained)!=len(manifest['combinations']):
            manifest['combinations']=retained
            manifest['videos']=[v for v in manifest['videos'] if v!=video_id]
            manifest['status']='partially_deleted'
            write_json(path,manifest)
