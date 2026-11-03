# Milestone 1 validation

Validated in the Codex Linux cloud workspace on 2026-11-03, Python 3.12.14. This is current-instance evidence, not a claim that hosted Codespaces or every phone codec has been tested.

## Automated checks

`uv sync --locked` succeeded and is repeatable. `uv run --locked pytest -q` completed with **24 passing tests**, including:

- MP4/MOV decode, VFR and nonzero initial PTS, frame/source mapping, RGB/grayscale conversion and letterboxing.
- Rational sampling, rates exceeding source cadence, gaps, unchanged original hashes, frame/ZIP exports.
- Future/expired cache boundaries, empty/epoch lookup behavior, interval/crop retrieval, retrieval reset races.
- Fake-clock pause/resume/speed, seek/restart/loop reset, repeatable offline sequences.
- Synthetic moving-object, stationary, brightness-change and between-samples short-event fixtures.
- Annotation persistence, hash-matched portable imports, interval boundaries and conflicting-label rejection.
- Video confusion formulas, undefined metrics, unknown temporal coverage, sample holds, event grouping/matching/tolerance, missed events and latency.
- Experiment persistence, repeat predictions, portable ZIP import/export and unsafe-path rejection.
- **10 videos × 10 configurations = 100 completed combinations**, plus deletion preserving the other 90 combinations.
- Streamlit AppTest: empty app, labels and interval saving, gallery stepping, replay controls, batch execution and results/FN filtering.

Four upstream Streamlit/Pandas deprecation warnings occur in chart rendering; they do not fail tests. JSON/TOML configuration parsing, local documentation links, Python compilation, Git whitespace checks and ignore rules were also checked.

## Application smoke checks

Started the actual Streamlit server on port 8501 using isolated temporary data/run roots. Its health endpoint returned `ok`. Exercised the UI in headless Chromium 154 with Playwright and inspected a screenshot:

- Uploaded four generated MP4s through the browser (moving object, stationary scene, brightness changes, short event).
- Opened the frame gallery, selected a thumbnail, stepped a sampled frame, played and paused simulated replay.
- Saved a video-level motion label and interval annotation.
- Selected a video and ran the three synthetic mock algorithms.
- Opened comparison results and false-negative inspection.

Browser scripts/screenshots and generated videos stayed outside Git. Initial browser automation needed synchronization with Streamlit rerenders; after waiting for completed rendering, the workflow passed. No production accuracy conclusion follows from synthetic mocks.

## Remaining acceptance checks

- **Real phone footage:** no user recording was supplied. Actual iPhone/Android MP4/MOV, orientation, HEVC/HDR and VFR behavior need representative files. Decoder support and browser-native playback are distinct.
- **Hosted Codespaces:** devcontainer and private port configuration are provided, but an actual GitHub Codespace was not launched here. Open a Codespace and run the documented command to verify its image/build and forwarded browser access.
- **Performance:** synthetic short-video functionality and a 100-combination batch passed; this is not a sustained 1080p/30 or long-recording performance benchmark. Random access and UI refresh limits are documented in development.md.
- **Future algorithms:** all detector results remain synthetic. The first real motion baseline and accuracy evaluation belong to Milestone 2.

Cloud install/start instructions were saved as a configuration draft. Saving does not publish a snapshot or prove fresh-task restoration. Review/save the environment settings and publish when desired.
