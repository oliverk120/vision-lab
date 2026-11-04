"""The Codespaces launcher must never run two Vision Lab servers at once."""
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'vision-lab.sh'
pytestmark = pytest.mark.skipif(shutil.which('uv') is None, reason='uv is required to launch Streamlit')


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def listeners(port):
    out = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN', '-t'], capture_output=True, text=True).stdout
    return set(out.split())


@pytest.fixture
def launcher(tmp_path):
    env = dict(os.environ, VISION_LAB_STATE=str(tmp_path / 'state'), VISION_LAB_DATA=str(tmp_path / 'data'),
               VISION_LAB_RUNS=str(tmp_path / 'runs'), VISION_LAB_PORT=str(free_port()))
    env.pop('CODESPACE_NAME', None)

    def run(*args, check=True):
        return subprocess.run(['bash', str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=180, check=check)

    run.port = int(env['VISION_LAB_PORT'])
    yield run
    run('stop', check=False)


def test_start_is_idempotent_and_stop_frees_port(launcher):
    assert 'running' in launcher('start').stdout
    first = listeners(launcher.port)
    assert len(first) == 1
    assert 'already running' in launcher('start').stdout
    assert listeners(launcher.port) == first
    assert 'Running' in launcher('status').stdout
    launcher('stop')
    assert not listeners(launcher.port)
    assert 'Not running' in launcher('status').stdout


def test_refuses_port_used_by_another_process(launcher):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', launcher.port))
        s.listen()
        result = launcher('start', check=False)
    assert result.returncode != 0
    assert 'did not start' in result.stderr
