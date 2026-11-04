"""Start Vision Lab:  python start.py

Runs the website on port 8501 in this terminal (Ctrl+C stops it) and opens it in your browser.
If Vision Lab is already running, it only opens the browser again, so you never get two servers.
"""
import importlib.util
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("VISION_LAB_PORT", "8501"))


def website_url() -> str:
    """In Codespaces, the forwarded https address; elsewhere, localhost."""
    name = os.environ.get("CODESPACE_NAME")
    domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    return f"https://{name}-{PORT}.{domain}" if name and domain else f"http://localhost:{PORT}"


def vision_lab_running() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=2) as response:
            return response.read() == b"ok"
    except OSError:
        return False


def port_in_use() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def open_browser(url: str):
    # VS Code (including Codespaces) sets $BROWSER in its terminals to a helper that asks the
    # VS Code window on *your* computer to open the address. Elsewhere we just print the address.
    browser = os.environ.get("BROWSER")
    if browser:
        try:
            subprocess.run([browser, url], check=True, timeout=20, capture_output=True)
            print(f"Asked VS Code to open {url} in your browser.")
            print("If no tab appeared (pop-up blocked?), click the address above or use the Ports panel.")
            return
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"Could not open the browser automatically ({exc}).")
    print(f"Open Vision Lab here: {url}")


def install_missing_packages() -> bool:
    if all(importlib.util.find_spec(m) for m in ("streamlit", "av", "PIL", "numpy")):
        return True
    print("Installing Python packages (first run only)…")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    if result.returncode:
        print("Error: package installation failed (see messages above). Try: pip install -r requirements.txt")
    return result.returncode == 0


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # keep messages in order even when logged to a file
    url = website_url()
    if vision_lab_running():
        print("Vision Lab is already running; not starting a second copy.")
        open_browser(url)
        return 0
    if port_in_use():
        print(f"Error: port {PORT} is used by another program, so Vision Lab cannot start.")
        print(f"Find it with:  lsof -i :{PORT}   then stop it, or close the terminal running it.")
        return 1
    if not install_missing_packages():
        return 1

    # Closing the terminal or a kill request stops the website too, instead of orphaning it.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    signal.signal(signal.SIGHUP, signal.default_int_handler)
    print("Starting Vision Lab…")
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
                               "--server.port", str(PORT)], cwd=ROOT)
    try:
        deadline = time.monotonic() + 90
        while not vision_lab_running():
            if server.poll() is not None:
                print(f"Error: Streamlit stopped during startup (exit code {server.returncode}); "
                      "see the messages above. If another Vision Lab was starting at the same time, "
                      "run python start.py again.")
                return 1
            if time.monotonic() > deadline:
                print("Error: Vision Lab did not respond within 90 seconds; stopping it.")
                server.terminate()
                return 1
            time.sleep(0.3)
        print(f"\nVision Lab is running at {url}\nPress Ctrl+C to stop it.")
        if "CODESPACE_NAME" in os.environ:
            print("(Ignore Streamlit's localhost addresses above: in Codespaces use this address.)")
        print()
        open_browser(url)
        return server.wait()
    except KeyboardInterrupt:
        server.terminate()
        server.wait()
        print("Vision Lab stopped.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
