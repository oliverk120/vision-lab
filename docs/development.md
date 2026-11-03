# Proposed development environment

Milestone 0 is documentation only. There is no install command, app entry point, lockfile, or runnable test suite yet. Do not install runtime dependencies just to review this repository.

## Milestone 1 proposal

Use GitHub Codespaces as the primary browser editor/runtime. GitHub remains the source of truth. Use the existing checkout in isolated Codex cloud tasks; create no worktree unless explicitly requested.

- Python 3.12, CPU execution by default.
- uv for project metadata, isolated `.venv`, and a committed `uv.lock`. Pin the selected uv/Python version in the future environment configuration, commit dependency declarations with the lockfile, and use frozen/locked sync for repeat installs. Do not guess package pins before checking compatibility.
- PyAV for timestamp-aware decode and random access through FFmpeg libraries. Record PyAV and linked FFmpeg versions; validate the selected wheel supports phone MP4/MOV codecs. A separate FFmpeg CLI is optional for inspection/fixture generation when needed, not assumed available from a PyAV wheel.
- OpenCV headless for resize, grayscale, and later classical motion processing; avoid desktop GUI packages in cloud environments.
- Streamlit for controls and observable intermediate frames. Proposed development port: 8501, privately forwarded in Codespaces. Document the actual entry point and command when it exists.
- pytest and minimal appropriate development checks; core timing tests use fake clocks. Validate on Linux CPU first.
- TOML configuration can use Python 3.12's standard-library `tomllib`; no YAML dependency required.

The future `.devcontainer` should provision only the needed Python/toolchain/runtime dependencies, perform locked install, and document manual app startup. Do not start nonexistent services in Milestone 0. A fresh Codespace must reproduce the install, not rely on an old terminal session. In Codex cloud, save tested install/start instructions only after runtime implementation; running processes do not survive environment snapshots. No cloud runtime configuration is needed for this documentation-only milestone.

## Later dependencies

Milestone 3 selects a small CPU-compatible detector after checking code/weight licenses and provenance; add PyTorch/model packages only as required. Milestone 6 adds training dependencies and reproducibility controls. GPU packages, CUDA provisioning, model downloads, databases, and hosted services are not prerequisites now.

Typical future dependency destinations are PyPI/package artifact hosts. Model artifact destinations and any external credentials must be justified when chosen; none are needed for this scaffold. Keep TLS/checksum verification enabled. Do not put secrets in committed configuration.

## Data and experiment safety

Upload/copy footage into ignored `data/` without overwriting originals. Put generated results and checkpoints in ignored `runs/`. Back up valuable material to user-chosen durable storage separately; Codespaces/cloud disks are disposable. Do not automatically upload private recordings. Review staged filenames and content even with ignore rules in place.

When implementing functionality, document exact working directories, install, startup, readiness and test commands here. Report automated tests separately from browser and real-footage acceptance checks.
