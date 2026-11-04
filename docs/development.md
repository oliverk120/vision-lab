# Development and operation

Python 3.12, CPU execution, uv lockfile, PyAV/FFmpeg libraries, OpenCV headless, and Streamlit. No PyTorch, model downloads, database, or external service is needed. GitHub is the source of truth; Codespaces is the primary supported development target. Use the existing checkout in isolated Codex cloud tasks; do not create worktrees unless requested.

## GitHub Codespaces

1. Open the repository on GitHub, choose **Code → Codespaces → Create codespace on main**.
2. Wait for setup (`.devcontainer/devcontainer.json` installs uv and runs `uv sync --locked`). Vision Lab then **starts automatically** in the background and port **8501** is forwarded privately. The first time, a browser tab opens; if your browser blocks it, use the notification or Ports panel.
3. Nothing else is needed. The website also restarts automatically whenever the Codespace starts, resumes, or VS Code reconnects.

| To… | Do this |
| --- | --- |
| Open the website | **Terminal → Run Task… → Vision Lab: Open website**, or Ports panel → globe icon beside *Vision Lab (8501)* |
| Run it in a visible terminal | **Run and Debug → Run Vision Lab** (F5). This stops the background copy first; Ctrl+C stops it |
| Restart after code changes | Task **Vision Lab: Restart** (Streamlit also offers *Rerun* in the page for app edits) |
| Stop / check / view log | Tasks **Vision Lab: Stop**, **Vision Lab: Status**, **Vision Lab: Show log** |

All of these call `scripts/vision-lab.sh` (`start`, `run`, `stop`, `restart`, `status`, `open`, `logs`), which you can also run directly in a terminal. It guarantees **one server at a time**: a per-port lock serialises commands, a PID file identifies the server it started, `start` does nothing if it is already running, `run` replaces the background copy, and if port 8501 is held by something it did not start it refuses and names that process instead of launching a duplicate. The background log and PID file live in `~/.local/state/vision-lab/`, outside the repository. Manually running `uv run --locked streamlit run app/main.py` still works, but bypasses this protection—Streamlit will then report that port 8501 is in use.

Codespaces stop after inactivity; the running website stops with them and comes back on resume. Keep port visibility **private**. Run tests: `uv run --locked pytest -q`. To refresh dependencies without changing the lockfile: `uv sync --locked`, then restart.

## Workbench

- **Video Library:** add multiple MP4/MOV files, expand a recording, load its original player on demand, edit its name/notes and video/interval labels. Export annotations as JSON. Imports match source SHA-256 even if a new upload has a different UUID. Delete requires a checkbox and removes local originals/annotations plus that video's generated experiment combinations; other batch results remain.
- **Frame Explorer:** choose a recording and independent A/B settings. Play, pause, change speed, seek, restart, loop, or use accelerated offline mode. Camera cache lookups reject future/expired data. The separate gallery browses the full dataset for annotation: choose chronological thumbnails, step samples, view nearest-neighbour/interpolated enlargement, source correspondence, pixel values, and absolute differences. Export one PNG or a timestamped ZIP range/whole stream.
- **Experiments:** select videos, mock algorithms, period configurations, stream settings, and evaluation rules. One batch runs the Cartesian product. Development and holdout are selectable; no automatic tuning. Only timestamp-driven synthetic mocks exist now.
- **Results:** filter algorithms, sort table headers, inspect video confusion and temporal metrics, charts, labeled/predicted intervals, diagnostic FP/FN frames and side-by-side transforms. Export/import portable results; source footage is separate.

## Storage

- `data/videos/<uuid>/original.mp4` (or `.mov`), `metadata.json`, `annotations.json`.
- `data/cache/exports/<uuid>/frames.zip` only when requested; regenerable thumbnails are held in a bounded memory cache.
- `runs/<experiment-uuid>/config.json`, then `<combination-uuid>/predictions.json`, `predictions.csv`, `metrics.json`, optional `artifacts/*.png`.

Set `VISION_LAB_DATA` and `VISION_LAB_RUNS` for different local roots (used by tests). No secrets are required. Back up **original footage plus annotation JSON exports and result ZIPs** to user-chosen durable storage; Codespaces disks are disposable. `.gitignore` excludes data/runs, media, model artifacts and secrets. Review staged files before committing.

## Limits and deliberate simplifications

- Upload limit: **512 MiB per file**, configured in Streamlit and checked by the library. Streamlit buffers compressed uploads/downloads and original playback media; load original players only when wanted. Split very long recordings externally without modifying your originals. Disk-full/unsupported-file errors are displayed; failed uploads are cleaned up.
- Decoding/indexing uses bounded image memory; the compact timestamp index grows with frame count. Random access currently decodes from the beginning for reliable exact sequence IDs, so long-video seeking can be slow. Gallery pages decode in one pass. No permanent thousands-of-image cache is generated.
- Replay is cooperative and ticks every 0.2 seconds, up to 32 frames per tick. This is a diagnostic preview, not smooth 30-FPS browser video. Every source frame is processed; the UI shows latest images, so display refreshes skip intermediate images. Lag is visible. Offline experiments run directly without UI pacing. Long batches block that session until done; no worker service or cancellation control yet.
- Changing stream settings or retention starts a fresh replay session. Settings are saved in experiment manifests. The initial TOML is a documented example, not a separate import path. No compressed cache clip export yet; frame/interval/crop APIs and gallery PNG/ZIP exports are implemented.
- Playback pause freezes simulated time; it does not mean the entire original file is unavailable in **explicit dataset-inspection mode**. Only replay/cache consumers have causal access.
- PyAV supports codecs available in its linked FFmpeg build. Right-angle display rotation is applied when exposed by decoded frames. Browser native original playback depends on browser codec support (e.g. HEVC/MOV may not play); decoded galleries/replay remain available. HDR color management, audio playback in simulated mode, arbitrary orientation transforms, and damaged timestamp repair are not implemented. Missing/nonmonotonic timestamps fail explicitly.
- Predictions and result tables are compact in-memory metadata per combination, appropriate for short-video datasets. Very long runs/large debug-image outputs need streaming metadata and paginated result tables later. Result ZIP imports are limited to 100 MiB uncompressed; export requires enough RAM for the archive. Frame ZIP generation streams image encoding to disk, but browser download is buffered.
- This is a single-user local workbench. Atomic JSON writes prevent partial files, not concurrent multi-user edits. Plugins are trusted code. No authentication, production serving, or live-camera adapter is implemented.

## Add the first detector in Milestone 2

Implement a class matching `vision_lab.motion.Detector`: `name`, `version`, `reset()`, and `process(sample) -> Prediction`. Register a factory in `REGISTRY`. Keep background state inside the instance and reset it for each video/configuration. The sample carries pixels, source frame identity and timestamps, sampling target, and spatial transform. Do not read source files or use future frames. Emit optional scores in [0,1], masks/debug images, and explain normalization. The runner measures processing time and persists provenance/results automatically.

Start with one straightforward frame-difference baseline, then illumination-sensitive synthetic cases and real labeled development recordings. Preserve the original hypotheses, compare misses/false alarms and cost, and inspect failures before adding further methods. Holdout footage must remain out of parameter tuning.
