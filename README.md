# Vision Lab

Vision Lab is a personal, general-purpose computer-vision research and learning project. Its central question is whether inexpensive continuous visual processing can identify when expensive analysis is justified. A security camera is one initial application, not the project's purpose.

The intended system combines **high-quality video capture, cheap continuous analysis, selective escalation, reproducible experiments, and modular components**. Preserve both original hypotheses and the evidence that changes them. Favor understandable experiments over production infrastructure.

## Current status

**Milestone 1 workbench implemented:** local video library, timestamp-aware replay/cache, derived-stream frame explorer, portable annotations, batch experiments, evaluation and side-by-side results. Only deterministic mock detectors are included; no real motion algorithms or neural models yet.

Open a GitHub Codespace, wait for setup, then run from the repository root:

```sh
uv run --locked streamlit run app/main.py
```

Open the private forwarded port **8501**. Run automated checks with `uv run --locked pytest -q`. See [operation and limitations](docs/development.md) and [evaluation rules](docs/evaluation.md). No footage or model weights are included.

## Intended workflow

Upload a phone MP4/MOV recording through a simple browser interface, replay it as a simulated camera, inspect the high-resolution cache and synchronized derived streams, and compare experiment configurations. Eventually add motion analysis, CPU-compatible person detection, selective inference, temporal analysis, and PyTorch training.

```text
High-resolution source → ingestion + timestamping → rolling cache
                                  │                    │
                                  ├→ Stream A          │
                                  │  low-res motion    │
                                  └→ Stream B          │
                                     object detection │
                                           ↓          │
                                  escalation controller
                                           ↓          │
                                  high-quality lookup ←┘
                                           ↓
                                  advanced analysis → event history
```

Derived streams use the same ingested timeline. They may consume frames directly during ingestion; the logical cache boundary must still prevent future or expired footage access.

## Documentation

- [Architecture and contracts](docs/architecture.md): timing, replay, cache, streams, and model boundaries.
- [Decisions](docs/decisions.md): initial choices, rationale, and open questions.
- [Experiments](docs/experiments.md): hypotheses, evidence, and reproducibility.
- [Roadmap](docs/roadmap.md): milestones and completion criteria.
- [Milestone 1 implementation plan](docs/milestone-1.md): incremental tasks and acceptance checks.
- [Development environment](docs/development.md): proposed Codespaces and dependencies.
- [Configuration specification](config/README.md) and [example](config/example.toml).
- [Agent instructions](AGENTS.md): constraints for future coding agents.

## Repository layout

| Location | Responsibility |
| --- | --- |
| `src/vision_lab/sources/` | MP4/MOV replay and future USB/IP camera adapters |
| `src/vision_lab/cache/` | Retention, indexing, high-quality frame/clip retrieval |
| `src/vision_lab/streams/` | Resize, color conversion, timestamp-based sampling |
| `src/vision_lab/motion/` | Classical motion and visual-change analysis, Milestone 2 |
| `src/vision_lab/detection/` | Pretrained/custom model inference, Milestone 3 onward |
| `src/vision_lab/experiments/` | Batch runner, result storage and explicit evaluation |
| `src/vision_lab/controller/` | Scheduling, state, escalation, Milestone 4 |
| `app/` | Four-tab Streamlit workbench |
| `tests/` | Automated timing, cache, sampling, scoring, storage and UI tests |
| `config/` | Human-readable experiment configuration specifications |
| `data/` | Local recordings, extracted frames, datasets; contents ignored |
| `runs/` | Local metrics, outputs, checkpoints; contents ignored |

## Development and storage

GitHub is the source of truth; GitHub Codespaces is the primary target editor and runtime, with a privately forwarded Streamlit port. Codex cloud can also edit and test the project. The user primarily directs agents with natural-language requests.

Python 3.12, uv-managed locked dependencies, PyAV/FFmpeg, OpenCV headless, and Streamlit power Milestone 1. PyTorch and model packages arrive only when needed. CPU execution is the default.

Never modify original recordings. Keep footage, datasets, credentials, and model files out of Git. Codespaces and cloud workspaces are disposable: separately back up valuable recordings, labels, and checkpoints. Only sanitized configuration and compact, reviewed experiment summaries belong in Git.

## Scope limits

No production surveillance system, continuous hosting, database server, authentication, multi-user platform, custom compression, GPU provisioning, distributed processing, tracking, or temporal transformers now. Implement only the milestone explicitly requested.
