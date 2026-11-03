"""Vision Lab browser workbench. Start: uv run streamlit run app/main.py."""
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import uuid
import zipfile

import altair as alt
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

from vision_lab.library import Library, read_json
from vision_lab.sources import FileSource
from vision_lab.sources.replay import Replay
from vision_lab.streams import StreamConfig, transform, sample_index, enlarge
from vision_lab.export import export_frames
from vision_lab.motion import REGISTRY
from vision_lab.experiments import run_batch, summaries, comparison, export_run, import_run
from vision_lab.experiments.evaluation import EvaluationConfig, truth_at

st.set_page_config(page_title='Vision Lab',layout='wide')
DATA = Path(os.environ.get('VISION_LAB_DATA','data'))
RUNS = Path(os.environ.get('VISION_LAB_RUNS','runs'))
library = Library(DATA)
st.title('Vision Lab')
st.caption('Inspect the pixels. Label the evidence. Compare explanations. CPU-only research workbench.')


@st.cache_resource(max_entries=12)
def load_source(path, video_id):
    return FileSource(path,video_id)


@st.cache_data(max_entries=24)
def thumbnail(path, video_id):
    return enlarge(load_source(path,video_id).get(0).pixels,192)


def settings(prefix, defaults):
    columns=st.columns(4)
    width=columns[0].number_input('Width',1,4096,defaults.width,key=prefix+'w')
    height=columns[1].number_input('Height',1,4096,defaults.height,key=prefix+'h')
    color=columns[2].selectbox('Colour',['gray','rgb'],index=0 if defaults.color=='gray' else 1,key=prefix+'c')
    fps=columns[3].number_input('FPS',0.1,120.0,float(defaults.fps),step=0.1,key=prefix+'f')
    return StreamConfig(width,height,color,fps)


def timeline(intervals, events=()):
    rows=[dict(start=i['start'],end=i['end'],label=i['category'],kind='Label: '+i['target']) for i in intervals]
    rows += [dict(start=a,end=b,label='predicted event',kind='Prediction') for a,b in events]
    if rows:
        chart=alt.Chart(pd.DataFrame(rows)).mark_bar().encode(x=alt.X('start:Q',title='Source seconds'),x2='end:Q',y='kind:N',color='label:N',tooltip=['start','end','label','kind'])
        st.altair_chart(chart,width='stretch')
    else:
        st.info('No interval labels yet. Unlabeled time is unknown.')


def annotate(meta):
    vid=meta['id']
    annotations=library.annotations(vid)
    with st.expander('Video labels and interval annotations',expanded=True):
        with st.form('labels'+vid):
            motion=st.selectbox('Contains physical motion',['Unknown','Yes','No'],index=['Unknown','Yes','No'].index(annotations['motion']))
            description=st.text_area('Scene description',annotations['description'])
            tags=st.text_input('Environmental tags (comma separated)',', '.join(annotations['tags']),help='Examples: lighting changes, shadows, reflections, camera movement, static scene')
            split=st.selectbox('Dataset split',['development','holdout'],index=int(annotations['split']=='holdout'))
            definition=st.text_area('Target-event definition',annotations['definition'])
            if st.form_submit_button('Save video labels'):
                annotations.update(motion=motion,description=description,tags=[t.strip() for t in tags.split(',') if t.strip()],split=split,definition=definition)
                library.save_annotations(vid,annotations)
                st.success('Labels saved')
        st.caption('Intervals are [start, end): end is exclusive. Unknown environmental labels may overlap physical motion; confirmed Yes and No may not overlap.')
        existing=annotations['intervals']
        choices=['New interval']+[i['id'] for i in existing]
        selected=st.selectbox('Edit interval',choices,format_func=lambda v: v if v=='New interval' else next(f"{i['start']:.3f}–{i['end']:.3f}: {i['category']}" for i in existing if i['id']==v),key='interval'+vid)
        item=next((i for i in existing if i['id']==selected),dict(start=0.,end=min(1.,meta['duration']),target='Unknown',category='physical motion',description=''))
        with st.form('interval-form'+vid+selected):
            columns=st.columns(2)
            start=columns[0].number_input('Start (seconds)',0.,float(meta['duration']),float(item['start']),step=0.01,format='%.3f')
            end=columns[1].number_input('End (seconds)',0.,float(meta['duration']),float(item['end']),step=0.01,format='%.3f')
            category=st.text_input('Event category',item['category'])
            target=st.selectbox('Target motion during this interval',['Unknown','Yes','No'],index=['Unknown','Yes','No'].index(item['target']))
            description=st.text_input('Interval description',item['description'])
            save=st.form_submit_button('Save interval')
            delete=st.form_submit_button('Delete interval',disabled=selected=='New interval')
            if save or delete:
                updated=[i for i in existing if i['id']!=selected]
                if save:
                    updated.append(dict(id=str(uuid.uuid4()) if selected=='New interval' else selected,start=start,end=end,target=target,category=category,description=description))
                annotations['intervals']=updated
                library.save_annotations(vid,annotations)
                st.rerun()
        timeline(library.annotations(vid)['intervals'])


def library_tab():
    st.subheader('Video Library')
    st.caption('Originals remain unchanged. Up to 512 MiB per upload; local storage is not a backup.')
    uploads=st.file_uploader('Upload phone videos',type=['mp4','mov'],accept_multiple_files=True)
    if st.button('Add uploads',disabled=not uploads):
        for upload in uploads:
            upload.seek(0)
            with st.spinner(f'Indexing {upload.name}'):
                library.add(upload,upload.name)
        st.success('Recordings added')
        st.rerun()
    st.download_button('Export annotations and metadata',json.dumps(library.export(),indent=2),'vision-lab-annotations.json','application/json')
    imported=st.file_uploader('Import annotations (matches source SHA-256)',type=['json'])
    if st.button('Import annotations',disabled=imported is None):
        count,missing=library.import_annotations(json.loads(imported.getvalue()))
        st.success(f'Updated {count} local recording(s). Unmatched files: {missing}')
    videos=library.list()
    for meta in videos:
        with st.expander(meta['name']+' · '+meta['id'][:8]):
            columns=st.columns([1,3])
            columns[0].image(thumbnail(str(library.path(meta['id'])),meta['id']),width=200)
            columns[1].write({k:meta[k] for k in ('duration','width','height','fps','frames','codec','size_bytes','vfr')})
            st.caption('Original-file inspection below is unrestricted dataset browsing, not the simulated camera cache.')
            if st.checkbox('Load original video player',key='player'+meta['id']):
                st.video(str(library.path(meta['id'])))
            with st.form('name'+meta['id']):
                name=st.text_input('Name',meta['name'])
                notes=st.text_area('Notes',meta['notes'])
                if st.form_submit_button('Save name and notes'):
                    library.rename(meta['id'],name,notes)
                    st.rerun()
            annotate(meta)
            confirmed=st.checkbox('Delete this recording, annotations and its generated results permanently',key='confirm'+meta['id'])
            if st.button('Delete video',disabled=not confirmed,key='delete'+meta['id']):
                from vision_lab.experiments import delete_video_results
                replay=st.session_state.pop('replay',None)
                if replay:
                    replay.close()
                delete_video_results(meta['id'],RUNS)
                library.delete(meta['id'])
                load_source.clear()
                thumbnail.clear()
                st.rerun()


@st.fragment(run_every=0.2)
def replay_panel():
    replay=st.session_state.get('replay')
    if replay is None:
        return
    cols=st.columns(4)
    if cols[0].button('Play / Resume'):
        replay.play()
    if cols[1].button('Pause'):
        replay.pause()
    if cols[2].button('Restart'):
        replay.restart()
    loop=cols[3].checkbox('Loop',value=replay.loop)
    replay.loop=loop
    mode=st.selectbox('Replay mode',['paced','offline'],index=int(replay.mode=='offline'))
    if mode!=replay.mode:
        replay.set_mode(mode)
    speed=st.number_input('Playback speed',0.1,32.,float(replay.speed),step=0.1)
    if speed!=replay.speed:
        replay.set_speed(speed)
    target=st.number_input('Seek to source second',0.,float(replay.source.duration),0.,step=0.1)
    if st.button('Seek (starts a fresh paused epoch)'):
        replay.seek(target)
    replay.tick()
    st.write(dict(simulated_seconds=round(replay.position,4),epoch=replay.epoch,eof=replay.eof,
                  cache=replay.cache.availability(),frames_ingested=replay.count,
                  processing_seconds=replay.processing_seconds,
                  lag_seconds=None if replay.cache.watermark is None else max(0,replay.position-float(replay.cache.watermark)),
                  missed_targets={k:s.missed for k,s in replay.samplers.items()}))
    panels=st.columns(3)
    if replay.frame:
        panels[0].image(replay.frame.pixels,caption=f'Source {float(replay.frame.timestamp):.4f}s',width='stretch')
    for panel,name in zip(panels[1:],('A','B')):
        if name in replay.latest:
            sample=replay.latest[name]
            panel.image(enlarge(sample.pixels),caption=f'{name}: source {float(sample.frame.timestamp):.4f}s / target {float(sample.target):.4f}s',width='stretch')
    lookup=st.number_input('Retrieve arrived high-resolution frame at second',0.,float(replay.source.duration),0.,step=0.1)
    if st.button('Cache lookup'):
        try:
            frame=replay.cache.frame_at(lookup)
            st.image(frame.pixels,caption=f'Actual timestamp {float(frame.timestamp):.6f}s')
        except ValueError as exc:
            st.warning(str(exc))


def explorer_tab():
    st.subheader('Frame Explorer')
    videos=library.list()
    if not videos:
        st.info('Upload a video in Video Library to begin.')
        return
    by_id={v['id']:v for v in videos}
    vid=st.selectbox('Recording',list(by_id),format_func=lambda v:by_id[v]['name'])
    source=load_source(str(library.path(vid)),vid)
    st.write(source.metadata)
    columns=st.columns(2)
    with columns[0]:
        st.markdown('**Stream A**')
        a=settings('a',StreamConfig())
    with columns[1]:
        st.markdown('**Stream B**')
        b=settings('b',StreamConfig(320,320,'rgb',1.))
        st.caption('Suggested B range: 0.1–5 FPS. Wider ranges are available for experiments.')
    retention=st.number_input('Cache retention (simulated seconds)',0.1,86400.,600.)
    key=(vid,a,b,retention)
    if st.session_state.get('replay_key')!=key:
        old=st.session_state.get('replay')
        if old:
            old.close()
        st.session_state.replay=Replay(source,{'A':a,'B':b},retention)
        st.session_state.replay_key=key
    st.caption('Changing stream settings starts a new replay session. Simulated-camera lookups enforce arrival and retention.')
    replay_panel()
    st.divider()
    st.markdown('### Dataset inspection gallery')
    st.caption('Unrestricted offline inspection for labeling. This gallery does not change replay or cache availability. No permanent frame files are generated.')
    stream_name=st.radio('Gallery stream',['A','B'],horizontal=True)
    config=a if stream_name=='A' else b
    index=sample_index(source,config)
    page=st.number_input('Gallery page',1,max(1,(len(index)+11)//12),1,key=f'page-{vid}-{stream_name}-{config}')
    nearest=st.checkbox('Nearest-neighbour enlargement (show pixel structure)',True)
    gallery_key=f'selected-{vid}-{stream_name}-{config}'
    if gallery_key not in st.session_state:
        st.session_state[gallery_key]=0
    # Decode the selected page in one pass, with at most twelve thumbnails retained.
    page_entries=index[(page-1)*12:page*12]
    wanted={seq:(offset,target) for offset,(seq,target) in enumerate(page_entries)}
    tiles=st.columns(4)
    if page_entries:
        for frame in source.frames(source.index[page_entries[0][0]][2]):
            if frame.sequence>page_entries[-1][0]:
                break
            if frame.sequence in wanted:
                offset,target=wanted[frame.sequence]
                sample=transform(frame,config,target)
                with tiles[offset%4]:
                    st.image(enlarge(sample.pixels,192,nearest),caption=f'{float(frame.timestamp):.6f}s')
                    if st.button(f'Inspect frame {frame.sequence}',key=f'tile-{vid}-{stream_name}-{frame.sequence}'):
                        st.session_state[gallery_key]=(page-1)*12+offset
    selected=st.session_state[gallery_key]
    nav=st.columns(3)
    if nav[0].button('Previous sampled frame',disabled=selected==0):
        selected-=1
    if nav[2].button('Next sampled frame',disabled=selected==len(index)-1):
        selected+=1
    st.session_state[gallery_key]=selected
    st.caption(f'Sample {selected+1} of {len(index)}')
    inspect=st.columns(3)
    current=None
    previous=None
    for panel,offset,label in zip(inspect,(-1,0,1),('Previous','Selected','Next')):
        position=selected+offset
        if 0<=position<len(index):
            seq,target=index[position]
            sample=transform(source.get(seq),config,target)
            panel.image(enlarge(sample.pixels,384,nearest),caption=f'{label}: {float(sample.frame.timestamp):.6f}s',width='stretch')
            if offset==0:
                current=sample
            if offset==-1:
                previous=sample
    st.image(current.frame.pixels,caption=f'Highest-resolution source frame {current.frame.sequence} · {float(current.frame.timestamp):.6f}s',width='stretch')
    st.write(dict(tensor_shape=current.pixels.shape,dtype=str(current.pixels.dtype),pts=current.frame.pts,time_base=str(current.frame.time_base),source_timestamp=str(current.frame.timestamp),sampling_target=str(current.target),transform=current.transform))
    x=st.number_input('Pixel x',0,config.width-1,0)
    y=st.number_input('Pixel y',0,config.height-1,0)
    st.write('Pixel value:',current.pixels[y,x].tolist())
    if previous is not None:
        st.image(enlarge(cv2.absdiff(current.pixels,previous.pixels),384,nearest),caption='Absolute pixel difference from previous sample — visualization only, not a motion prediction')
    buffer=io.BytesIO()
    Image.fromarray(current.pixels).save(buffer,format='PNG')
    st.download_button('Export selected frame',buffer.getvalue(),f'{vid}_frame{current.frame.sequence}_t{float(current.frame.timestamp):.6f}.png','image/png')
    with st.expander('Export time range or whole derived stream'):
        export_start=st.number_input('Export start seconds',0.,float(source.duration),0.)
        export_end=st.number_input('Export end seconds',0.,float(source.duration),float(source.duration))
        st.caption('ZIP contains PNGs and exact timestamp metadata. Whole-stream export uses the full range; large exports can be slow.')
        if st.button('Generate frame ZIP'):
            folder=DATA/'cache'/'exports'/vid
            folder.mkdir(parents=True,exist_ok=True)
            target=folder/'frames.zip'
            export_frames(source,config,export_start,export_end,target)
            st.session_state.export_path=str(target)
        path=st.session_state.get('export_path')
        if path and Path(path).exists() and Path(path).parent.name==vid:
            with open(path,'rb') as handle:
                st.download_button('Download frame ZIP',handle,'frames.zip','application/zip')
    timeline(library.annotations(vid)['intervals'])


def experiments_tab():
    st.subheader('Experiments')
    st.warning('Only synthetic timestamp-based mocks are installed. Their scores demonstrate the infrastructure, not motion-detection quality.')
    videos=library.list()
    by_id={m['id']:m for m in videos}
    split=st.selectbox('Dataset filter',['development','holdout','all'])
    ids=[v for v in by_id if split=='all' or library.annotations(v)['split']==split]
    selected=st.multiselect('Videos',ids,format_func=lambda v:by_id[v]['name'])
    algorithms=st.multiselect('Algorithms',list(REGISTRY),default=list(REGISTRY))
    periods=st.text_input('Mock period configurations in seconds (comma separated)','4')
    st.caption('Each period becomes a separate configuration for every selected algorithm. No automatic tuning; holdout results are descriptive only.')
    stream=settings('experiment',StreamConfig())
    with st.expander('Evaluation rules',expanded=True):
        threshold=st.number_input('Score threshold',0.,1.,0.5)
        minimum=st.number_input('Minimum event duration seconds',0.,600.,0.)
        gap=st.number_input('Allowable positive-event gap seconds',0.,600.,0.)
        tolerance=st.number_input('Event matching tolerance seconds',0.,600.,0.)
        hold=st.number_input('Maximum prediction hold seconds',0.001,600.,1./stream.fps,format='%.4f',key=f'hold-{stream.fps}')
        st.caption('Video positive = at least one grouped event. Temporal labels use [start,end); unlabeled time is excluded. Time metrics use thresholded sample holds; event metrics use grouped events. See docs/evaluation.md.')
    if st.button('Run batch',disabled=not selected or not algorithms):
        candidate_configs=[{'period_seconds':float(p.strip())} for p in periods.split(',')]
        candidates=[dict(name=name,config=config) for name in algorithms for config in candidate_configs]
        progress=st.progress(0.)
        result=run_batch(library,selected,candidates,stream,EvaluationConfig(threshold,minimum,gap,tolerance,hold),RUNS,progress.progress)
        st.success(f'Experiment saved: {result}')
    with st.expander('Portable experiment results'):
        incoming=st.file_uploader('Import result ZIP',type=['zip'])
        if st.button('Import result archive',disabled=incoming is None):
            result=import_run(incoming.getvalue(),RUNS)
            st.success('Imported '+result)


def detail(row, label):
    folder=RUNS/row['experiment']
    manifest=read_json(folder/'config.json')
    combo=next(c for c in manifest['combinations'] if c['id']==row['combination'])
    predictions=read_json(folder/combo['id']/'predictions.json')
    metrics=read_json(folder/combo['id']/'metrics.json')
    st.markdown('**'+label+' · '+combo['algorithm']+'**')
    st.write(combo['configuration'])
    timeline(combo['annotations']['intervals'],metrics['events']['predicted'])
    if predictions:
        st.line_chart(pd.DataFrame(predictions)[['timestamp','score']].set_index('timestamp'))
    st.json(metrics,expanded=False)
    st.download_button('Predictions CSV',(folder/combo['id']/'predictions.csv').read_bytes(),combo['id']+'.csv','text/csv',key=label+'csv')
    threshold=manifest['evaluation']['threshold']
    tagged=[]
    for p in predictions:
        actual=truth_at(combo['annotations'],p['timestamp'])
        detected=p['detected'] if p['score'] is None else p['score']>=threshold
        outcome='Unknown' if actual=='Unknown' else ('TP' if detected else 'FN') if actual=='Yes' else ('FP' if detected else 'TN')
        tagged.append({**p,'ground_truth':actual,'outcome':outcome})
    return combo,tagged,manifest


def results_tab():
    st.subheader('Results')
    rows=summaries(RUNS)
    if not rows:
        st.info('Run a mock experiment to populate comparisons.')
        return
    experiments=sorted({r['experiment'] for r in rows})
    experiment=st.selectbox('Experiment',experiments)
    selected=[r for r in rows if r['experiment']==experiment]
    filter_algorithms=st.multiselect('Filter algorithms',sorted({r['algorithm'] for r in selected}),default=sorted({r['algorithm'] for r in selected}))
    selected=[r for r in selected if r['algorithm'] in filter_algorithms]
    st.caption('Click column headers to sort. Rows group algorithm/configuration within one experiment and dataset split. Undefined metrics are blank; never interpreted as zero.')
    st.dataframe(pd.DataFrame(comparison(selected)),hide_index=True)
    st.download_button('Export experiment ZIP',export_run(RUNS/experiment),experiment+'.zip','application/zip')
    if not selected:
        return
    rowmap={r['combination']:r for r in selected}
    choice=st.selectbox('Per-video algorithm/configuration',list(rowmap),format_func=lambda k:rowmap[k]['video_name']+' · '+rowmap[k]['algorithm']+' · '+rowmap[k]['configuration'])
    row=rowmap[choice]
    others={r['combination']:r for r in selected if r['video']==row['video']}
    comparison_id=st.selectbox('Side-by-side comparison on the same video',list(others),format_func=lambda k:others[k]['algorithm']+' · '+others[k]['configuration'])
    cols=st.columns(2)
    with cols[0]:
        combo,tagged,manifest=detail(row,'Left')
    with cols[1]:
        other,other_tagged,other_manifest=detail(others[comparison_id],'Right')
    category=st.selectbox('Inspect prediction outcome',['All','TP','FP','FN','TN','Unknown'])
    filtered=[p for p in tagged if category=='All' or p['outcome']==category]
    st.dataframe(pd.DataFrame(filtered),hide_index=True)
    st.caption('Table outcomes describe labeled sample timestamps. Time-weighted/event metrics use the documented intervals and may differ. Missed events between samples appear in event metrics even without an FN sample.')
    local={m['sha256']:m for m in library.list()}
    video=local.get(combo['metadata']['sha256'])
    if not video:
        st.info('Original footage is not present. Re-upload the matching source to inspect frames; results remain available.')
        return
    source=load_source(str(library.path(video['id'])),video['id'])
    if filtered:
        trigger=st.selectbox('Jump to prediction frame',[p['sequence'] for p in filtered],format_func=lambda s:next(f"{p['timestamp']:.6f}s · {p['outcome']}" for p in filtered if p['sequence']==s))
        default=float(source.index[trigger][2])
    else:
        default=0.
    timestamp=st.number_input('Inspect common source timestamp',0.,float(source.duration),default,key=f'compare-time-{choice}-{category}-{default}')
    seq=max((i for i,(_,_,t) in enumerate(source.index) if float(t)<=timestamp),default=0)
    frame=source.get(seq)
    st.image(frame.pixels,caption=f'Shared source frame: {float(frame.timestamp):.6f}s',width='stretch')
    for panel,c,records,m,label in zip(st.columns(2),(combo,other),(tagged,other_tagged),(manifest,other_manifest),('left','right')):
        config=StreamConfig(**m['stream'])
        panel.image(enlarge(transform(frame,config).pixels),caption=f"{c['algorithm']} input transform at shared time",width='stretch')
        pred=next((p for p in records if p['sequence']==seq),None)
        panel.write(pred if pred else 'This source frame was not sampled by this configuration.')
        if pred:
            for name,relative in pred.get('artifacts',{}).items():
                panel.image(str(RUNS/m['id']/c['id']/relative),caption=name)


library_view,explorer_view,experiments_view,results_view=st.tabs(['Video Library','Frame Explorer','Experiments','Results'])
for tab,render in zip((library_view,explorer_view,experiments_view,results_view),(library_tab,explorer_tab,experiments_tab,results_tab)):
    with tab:
        try:
            render()
        except Exception as exc:
            st.error(f'{type(exc).__name__}: {exc}')
            st.caption('Your original recordings are not modified. Check the input and retry; report persistent errors with the operation and message.')
