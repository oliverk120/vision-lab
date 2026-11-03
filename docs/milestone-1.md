# Milestone 1 original implementation plan

Historical video-only plan retained for context. The subsequent user request expanded this milestone to the library, annotations, mock experiment runner and evaluation workbench. See `development.md` for current operation/limits and `validation.md` for evidence. Actual motion algorithms remain out of scope.

Goal: make a phone recording behave like a camera, with a trustworthy high-resolution timeline and two observable derived streams. No motion detection, pretrained models, scheduling controller, tracking, training, or tiered retention.

Read [architecture](architecture.md), [decisions](decisions.md), [configuration](../config/README.md), and [development](development.md) first. Follow their provisional contracts; document any measured reason to change them.

## Ordered implementation slices

1. **Establish minimal development tooling.** Inspect available Python and codecs. Introduce Python 3.12 project metadata and a uv lockfile for only PyAV, OpenCV headless, Streamlit, and relevant test tooling. Add a minimal Codespaces configuration and private Streamlit port forwarding. Validate locked install, imports, and decoder support. Do not install PyTorch or download models.
2. **Define frame/time/source contracts.** Introduce frame envelopes, rational PTS conversion, an injectable monotonic clock, epochs, capability flags, and explicit errors. Test nonzero initial PTS, variable gaps, duplicate timestamps, and invalid/missing timestamps before depending on UI timing.
3. **Implement read-only MP4/MOV ingestion and replay.** Inspect codec, duration, rotation, and time base. Preserve presentation order; paced speed 1 and accelerated pacing use the shared clock; offline mode skips waits only. Implement play/pause/resume, speed changes, seek, restart, EOF and loop semantics. Test with fake clocks; do not write sleep-sensitive tests. Keep original-file hashes unchanged.
4. **Implement the logical cache.** Index only arrived frames; use the original compressed file through a private adapter. Implement availability, frame and interval retrieval, short clips and crops with actual timestamp/coverage metadata. Enforce retention and epoch checks both before and after retrieval. Handle random-access keyframe preroll internally; no raw-frame ten-minute RAM buffer.
5. **Implement derived streams.** Common ordered arrivals feed independent rational target grids. Produce A (64×64 gray, 15 FPS) and B (320×320 RGB, 1 FPS default/configurable) with letterboxing and coordinate metadata. No inference. Record missed target slots, actual sample times, and settings revisions.
6. **Integrate Streamlit.** Upload to ignored local storage without overwriting existing files; expose source preview and all replay controls, cache bounds/watermark, A/B previews and settings, frame identities/timestamps, lag/throughput/durations. Handle Streamlit reruns and session cleanup without duplicate decoders/workers. Preserve clock and pipeline ownership outside UI rendering.
7. **Validate, document, and record a baseline.** Run the meaningful test suite, a generated VFR fixture, and a user-provided phone MP4/MOV if available. Capture a minimal reproducibility manifest and inspect repeat runs. Explain limitations and provide exact setup/start/test commands. If no real phone recording is available, report that manual acceptance check as pending; never claim synthetic media establishes phone compatibility.

Each slice should leave a reviewable commit and corresponding tests. Prefer small interfaces over empty general-purpose frameworks.

## Acceptance matrix

| Area | Required evidence |
| --- | --- |
| Replay modes | Same source frame order/timestamps in paced and offline modes; speed changes affect wall pacing, not sampling; speed 1 honors PTS gaps |
| Controls | Pause freezes simulated time/arrival; resume has no jump; forward/backward seek discards preroll and creates epoch; restart/loop clear state; old queued results rejected; EOF explicit |
| Timestamp handling | VFR, nonzero initial PTS, duplicate PTS, gaps, presentation reordering, and invalid timestamp errors covered; nominal FPS never substitutes for PTS |
| Availability | Before first arrival no footage; exact inclusive retention boundary works; future/expired requests fail distinctly; intervals/clips/crops cannot leak future/expired/preroll footage |
| Async safety | Seek/eviction during retrieval is revalidated; no stale-epoch result enters new state |
| Sampling | Two offline runs produce identical frame IDs/timestamps given the same controls/config; source gaps and above-source rates do not create duplicate frames; A and B share source identity/time |
| Transforms | Shapes/channels and aspect ratio correct, phone orientation handled, source-coordinate mapping tested, source pixels not mutated |
| UI | Upload, play, pause, resume, restart, seek, loop, speed/mode and stream settings operate; all displays reflect the same epoch; timing and cache status understandable |
| Performance | Measure CPU/RAM, decode/transform durations, throughput, wall lag and UI drops on stated hardware; bounded memory/queues; do not invent universal FPS thresholds |
| Integrity | Original source hashes unchanged; private data and generated outputs ignored; resolved configuration, code and dependency identity recorded |
| Real footage | Demonstrate an actual phone MP4/MOV replay and report codec/rotation/VFR support; clear errors for unsupported input |

Generate small synthetic fixtures in temporary directories with the selected decoder/encoder tooling; keep fixtures or generation recipes non-private. Test semantic behavior, not just imports or an open port. Automated checks cannot substitute for the browser controls/real-footage acceptance pass.

## Exact prompt for the next task

> Implement Milestone 1 — Video infrastructure for Vision Lab, following AGENTS.md, docs/architecture.md, docs/milestone-1.md, docs/development.md, and config/README.md. Inspect the current repository first. Set up the minimal Python 3.12 CPU development environment with reproducibly locked dependencies and Codespaces support. Implement read-only MP4/MOV replay with source-PTS timing, paced and offline modes, all documented playback controls and epoch resets, the logical high-resolution rolling cache with no-future-access and expiration enforcement, synchronized configurable Stream A and Stream B, and a basic Streamlit interface exposing controls, timestamps, cache availability, and performance diagnostics. Add meaningful tests and run the acceptance checks in docs/milestone-1.md; report real-phone-video or browser checks as pending if unavailable. Do not implement motion detection, model inference, escalation, tracking, training, or tiered retention. Preserve original recordings, keep private/large artifacts out of Git, document justified design changes, and finish with verified setup/start/test instructions and remaining limitations.
