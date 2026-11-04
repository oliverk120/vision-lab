"""The website (rendered by Streamlit's test runner) and python start.py."""
import io
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

from vision_lab.video import save_upload

ROOT = Path(__file__).resolve().parents[1]


def run_app(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_LAB_DATA", str(tmp_path / "data"))
    return AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()


def assert_ok(app):
    assert not app.exception, [e.message for e in app.exception]


def captions(app):
    def walk(node):
        yield node
        for child in getattr(node, "children", {}).values():
            yield from walk(child)
    return [i.caption for n in walk(app._tree) if getattr(n, "type", "") == "image" for i in n.proto.imgs]


def test_empty_app(tmp_path, monkeypatch):
    app = run_app(tmp_path, monkeypatch)
    assert_ok(app)
    assert "Upload a video" in app.info[0].value
    assert not app.sidebar  # phones hide the sidebar, so nothing essential may live there


def test_views(video30, tmp_path, monkeypatch):
    save_upload(io.BytesIO(video30.read_bytes()), "clip.mp4", tmp_path / "data")
    app = run_app(tmp_path, monkeypatch)
    assert_ok(app)
    app.button[0].click().run()  # Play
    assert_ok(app)
    assert app.session_state.camera.playing
    app.radio[0].set_value("Frame browser").run()
    assert_ok(app)
    assert not app.session_state.camera.playing  # leaving the camera view pauses it
    tile = next(b for b in app.button if b.label == "0.133 s")  # third Stream A sample
    tile.click().run()
    assert_ok(app)
    assert any(c.startswith("Original frame #4 at 0.133 s · 160×90") for c in captions(app))
    assert "Absolute pixel difference (bright = changed)" in captions(app)
    assert any(m.label == "Mean difference" for m in app.metric)
    app.radio[1].set_value("B").run()
    assert_ok(app)
    app.radio[0].set_value("Original video").run()
    assert_ok(app)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_start_script(tmp_path):
    """Starts once, opens the forwarded Codespaces address, and never starts a duplicate."""
    port = free_port()
    opened = tmp_path / "opened.txt"
    browser = tmp_path / "browser"
    browser.write_text(f'#!/bin/sh\necho "$1" >> {opened}\n')
    browser.chmod(0o755)
    env = dict(os.environ, VISION_LAB_PORT=str(port), VISION_LAB_DATA=str(tmp_path / "data"), BROWSER=str(browser),
               CODESPACE_NAME="test-space", GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN="app.github.dev")
    start = [sys.executable, str(ROOT / "start.py")]
    server = subprocess.Popen(start, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(300):
            if opened.exists():
                break
            time.sleep(0.2)
        url = f"https://test-space-{port}.app.github.dev"
        assert opened.read_text().split() == [url]

        second = subprocess.run(start, env=env, capture_output=True, text=True, timeout=60)
        assert second.returncode == 0 and "already running" in second.stdout
        assert opened.read_text().split() == [url, url]  # reopened, not restarted
        assert server.poll() is None
    finally:
        server.terminate()  # like closing the terminal
        server.wait(timeout=30)
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", port)) != 0  # Streamlit stopped too, nothing orphaned

    with socket.socket() as blocker:  # a different program holding the port
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("127.0.0.1", port))
        blocker.listen()
        third = subprocess.run(start, env=env, capture_output=True, text=True, timeout=60)
    assert third.returncode == 1 and "used by another program" in third.stdout
