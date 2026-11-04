# Vision Lab

A small, personal computer-vision learning project. Upload videos from your phone, replay them as if they were a live camera, and look closely at the cheap low-resolution streams that future motion detection and neural networks will analyse.

## Start

In a GitHub Codespace terminal:

```sh
python start.py
```

This starts the website on port 8501 and asks VS Code to open its forwarded `https://…app.github.dev` address in your browser. Press Ctrl+C to stop it. Running `python start.py` again while it is running only reopens the browser, so you never get two servers. If no tab appears, click the address printed in the terminal, or use the globe icon next to port 8501 in the **Ports** panel.

Packages are installed when the Codespace is created (`pip install -r requirements.txt`). If they are missing, `start.py` installs them.

## What it does

- **Upload and choose videos:** MP4 and MOV files of up to 512 MB each. They are stored unchanged in `data/videos/<id>/`.
- **Original video:** the recording as your browser plays it.
- **Simulated camera:** replays the video as a live camera. You can play, pause, restart and change the speed. Each frame arrives at its recorded time, and the page shows the latest source frame and both streams, along with timing and cache status.
- **Derived streams** (fixed for now, configurable in code):
  - **Stream A:** 64×64 greyscale at 15 FPS.
  - **Stream B:** 320×320 colour at 1 FPS.
  - Both are letterboxed, so the picture is never stretched.
- **Frame browser:** clickable thumbnails of every frame each stream takes. Each one is shown next to its full-resolution original, with the pixel difference from the previous frame in that stream.
- **Rolling cache:** fetches the full-resolution frame at any time the camera has already delivered, within the last 10 minutes. Times in the future, or ones that have expired, are refused.

## How it works

```text
video source ──▶ rolling cache (full resolution) ──▶ Stream A, Stream B ──▶ future analysis
```

| File | Role |
| --- | --- |
| `vision_lab/video.py` | Read-only decoding with exact timestamps; upload storage. A live camera would replace `VideoFile`. |
| `vision_lab/cache.py` | `RollingCache`: arrived footage only, for a limited time window. |
| `vision_lab/streams.py` | `StreamConfig`, timestamp-based `Sampler`, resize/greyscale (`derive`). |
| `vision_lab/camera.py` | `SimulatedCamera`: paces frames by their timestamps and feeds cache and streams. |
| `app.py` | The Streamlit website (UI only). |
| `start.py` | One-command launcher. |

**Design rules**

- **Time comes from the file's own timestamps:** this keeps variable frame rates and phone videos correct. Every stream picks the first frame at or after each of its time slots (0, 1/fps, 2/fps…), never duplicates a frame, and shares the source frame's identity and time.
- **Nothing is written to disk except your uploads:** gallery images are made on demand and kept only in memory.
- **To add analysis later**, consume the `Sample`s returned by `SimulatedCamera.update()`, and fetch full-resolution detail through `camera.cache.get(time)`. Never read ahead in the file.

## Tests

```sh
python -m pytest -q
```

The tests cover:

- Decoding: exact timestamps, B-frames, variable frame rate and phone rotation.
- Stream sizes, colour and rates.
- Cache rules and camera timing.
- Upload storage.
- The website's views.
- `start.py`: the forwarded address, no duplicate servers, and a clear error when port 8501 is taken.

The rotation test needs the `ffmpeg` command and is skipped without it.

## Limitations

- **Automatic browser opening has not been verified in a real Codespace yet.** `start.py` uses the `$BROWSER` helper that VS Code provides in its terminals. In the browser version of Codespaces, a pop-up blocker may stop the new tab; the printed address and the Ports panel always work. Outside VS Code terminals (for example over SSH), the address is only printed.
- **Not yet tested with real phone footage** (iPhone HEVC, HDR, variable frame rate). Some browsers cannot play HEVC in the *Original video* view; the other views decode on the server.
- **Live replay speed:** on this project's test machine, 1080p decoding ran at about 4× real time. A slow Codespace may lag behind, and the page shows the lag.
- **Single user, local only.** Back up anything valuable in `data/` yourself, because Codespaces disks are not permanent storage.

## Older data and history

- **Earlier work is still on disk:** labels (`data/videos/*/annotations.json`) and experiment results (`runs/`) from the earlier, larger version are no longer used by the app. They are left exactly where they were and remain ignored by Git.
- **Earlier code is in Git history:** that version had annotation tools, mock detectors, an experiment runner, scoring and design documents. Its last commit is `3e0fc23`.
