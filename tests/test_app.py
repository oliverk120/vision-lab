"""Streamlit executes real widget callbacks; no browser server required."""
import io
from pathlib import Path
from streamlit.testing.v1 import AppTest
from vision_lab.library import Library


def widget(elements,label):
    return next(e for e in elements if e.label==label)


def assert_healthy(app):
    assert not app.exception, [e.message for e in app.exception]
    assert not app.error, [e.value for e in app.error]


def test_empty_app(tmp_path,monkeypatch):
    monkeypatch.setenv('VISION_LAB_DATA',str(tmp_path/'data'))
    monkeypatch.setenv('VISION_LAB_RUNS',str(tmp_path/'runs'))
    app=AppTest.from_file(Path('app/main.py').resolve(),default_timeout=20).run()
    assert_healthy(app)
    assert [tab.label for tab in app.tabs]==['Video Library','Frame Explorer','Experiments','Results']


def test_library_gallery_annotations_replay_and_results(video,tmp_path,monkeypatch):
    root=tmp_path/'data'
    runs=tmp_path/'runs'
    library=Library(root)
    meta=library.add(io.BytesIO(video.read_bytes()),'Synthetic moving object.mp4')
    monkeypatch.setenv('VISION_LAB_DATA',str(root))
    monkeypatch.setenv('VISION_LAB_RUNS',str(runs))
    app=AppTest.from_file(Path('app/main.py').resolve(),default_timeout=30).run()
    assert_healthy(app)
    widget(app.selectbox,'Contains physical motion').set_value('Yes')
    widget(app.button,'Save video labels').click().run()
    assert_healthy(app)
    assert library.annotations(meta['id'])['motion']=='Yes'
    widget(app.selectbox,'Target motion during this interval').set_value('Yes')
    widget(app.button,'Save interval').click().run()
    assert_healthy(app)
    assert len(library.annotations(meta['id'])['intervals'])==1
    widget(app.button,'Next sampled frame').click().run()
    assert_healthy(app)
    widget(app.button,'Play / Resume').click().run()
    assert_healthy(app)
    widget(app.button,'Pause').click().run()
    widget(app.number_input,'Seek to source second').set_value(.5)
    widget(app.button,'Seek (starts a fresh paused epoch)').click().run()
    assert_healthy(app)
    assert app.session_state['replay'].position==.5
    widget(app.multiselect,'Videos').set_value([meta['id']]).run()
    widget(app.button,'Run batch').click().run()
    assert_healthy(app)
    assert list(runs.glob('*/config.json'))
    assert any(e.label=='Per-video algorithm/configuration' for e in app.selectbox)
    widget(app.selectbox,'Inspect prediction outcome').set_value('FN').run()
    assert_healthy(app)
