# Architecture

Status: design contract for incremental implementation, not implemented behavior. Initial values are hypotheses, not proven optimal settings. See [decisions](decisions.md) for alternatives and deferred choices.

## Components and information flow

```text
MP4/MOV now; USB/IP later
           ↓
source adapter → ingestion + shared clock → high-resolution rolling cache
                              │                         ↑
                              ├→ Stream A → motion      │ retrieval
                              └→ Stream B → detector    │
                                              ↓         │
                                      escalation controller
                                              ↓         │
                                      advanced analysis ┘
                                              ↓
                                      results / event history
```

The cache logically precedes derived analysis. Ingestion may fan out already-arrived frames directly rather than writing and re-decoding every frame. Cache watermark advancement must precede publishing those frames. All consumers see the same source, timeline, and retention rules. Models and UI must not bypass the cache to read the source file.

| Component | Owns | Does not own |
| --- | --- | --- |
| Source | Read-only decode, source metadata, presentation timestamps, source capabilities | Model policy or retention |
| Ingestion/replay | Simulated clock, playback controls, epoch transitions, frame arrival | Detection decisions |
| Cache | Availability, retention, source indexing, frame/interval/clip/crop retrieval | Model-specific access rules |
| Streams | Deterministic temporal sampling, resize and color transforms | Independent camera clocks |
| Motion/detection | Analysis of supplied frames and metadata | Source file access or replay control |
| Controller | Scheduling state, bounded analysis requests, escalation | Decode or cache internals |
| App | User controls, source and intermediate views, diagnostics | Core timing logic |
| Run recorder | Configuration, provenance, metrics, analysis/event history | Scheduling |

## Time and frame identity

- **Source timestamp:** decoder presentation timestamp (PTS) with its rational time base. Keep the original integer PTS and time base; normalize the first presented frame to zero for display and scheduling. Do not derive timestamps from frame count divided by nominal FPS.
- **Simulated playback time:** the camera's current playhead in source-relative units. In paced replay it advances according to speed while playing, and freezes on pause. In offline mode it advances through input timestamps as processing permits.
- **Wall time:** real elapsed time, measured with a monotonic clock for scheduling. UTC is only run/log metadata, never the media clock.
- **Processing duration:** monotonic elapsed time for decode, transform, inference, or retrieval, distinct from all media timestamps.
- **Arrival watermark:** latest source-relative PTS published by ingestion in the current epoch. It may lag the playhead under load; no consumer can retrieve beyond it.

Proposed frame envelope: run ID, source ID, epoch ID, presentation-order sequence number, original PTS/time base, normalized timestamp, dimensions, pixel format, orientation, transform metadata, and an immutable/read-only pixel payload. Use `(run, source, epoch, sequence)` as identity; duplicate timestamps alone are not unique. NumPy-compatible arrays are the likely decoded payload; do not commit to a public Python class until Milestone 1.

VFR gaps stay gaps. Never invent intermediate source frames. Emit decoder output in presentation order, preserving stable ordering for duplicate PTS. Investigate absent/nonmonotonic timestamps and fail clearly in the initial implementation rather than silently assuming constant FPS. Decoder reordering for B-frames must be resolved before ingestion. Record any later repair policy explicitly.

## Source and replay contract

Proposed operations: open/inspect metadata; iterate timestamped frames; play; pause/resume; set speed; seek; restart; close. Expose capabilities such as seekable, finite duration, and supported controls. EOF is explicit. USB/IP sources will share the frame/event interface but may reject seek, restart, or playback speed as unsupported.

Two modes share the same pipeline:

- **Paced replay:** speed 1 reproduces source timing; other positive speeds scale the mapping from source time to monotonic time. Pause/resume and speed changes re-anchor the mapping without jumping source time. If processing is behind, display lag; do not silently discard frames. An explicit future drop policy must report omissions.
- **Offline replay:** no timing sleeps; process as fast as hardware permits, preserving presentation order, simulated timestamps, and deterministic sampling. Backpressure may slow wall-clock progress without changing media semantics.

Every seek, restart, and loop creates a new epoch, cancels pending work, clears cache availability and sampler/controller/temporal state, and rejects stale results. Retain old run logs tagged with their epoch. For a seek to `t`, decode from a preceding keyframe privately, discard preroll, then publish the first frame at or after `t`. Earlier footage is not available merely because it exists in the file. Pause seek playback until play is requested. Restart is seek-to-zero. Loop resets to zero and resumes, recording a loop/epoch event. No state is silently carried across boundaries.

The UI's original-video preview follows this same arrived timeline. Full-file browser playback or seeking outside the replay controls must not become a second source of frames or advance cache availability. Controls may request a seek, but consumers only see the new epoch's published frames.

## High-resolution rolling cache

Initial illustrative source: 1080p color around 30 FPS; retention: 600 simulated seconds. Initial implementation is a logical indexed view of the original compressed MP4/MOV, accessed only by the cache adapter. Do not duplicate the source or store ten minutes of raw frames in RAM.

For watermark `W`, retention `R`, and the first published time in this epoch `E`, available indexed frames have timestamps in `[max(E, W-R), W]`. Bounds are inclusive. The interval is a bound, not a promise that a frame exists at every time. Eviction advances on ingestion; pause does not expire media by wall time. Failed arrival or pending decode cannot advance `W`.

Proposed API contracts:

| Request | Semantics |
| --- | --- |
| `availability()` | Epoch, watermark, retained bounds, gaps, and highest available quality |
| `frame_at(t)` | Highest-quality retained frame at or before `t`; return actual timestamp and offset; never select after the requested time |
| `frames_between(start, end)` | All retained frames in the inclusive interval, in presentation order; pagination/iteration may bound memory |
| `clip(start, end)` | Requested interval plus actual coverage; reject unavailable portions by default, explicit partial mode may truncate and report gaps |
| `crop_at(t, region)` | Same availability rules as frame lookup, crop from source-resolution pixels, return actual crop bounds and transform |

Distinguish `NOT_YET_AVAILABLE`, `EXPIRED`, `OUTSIDE_EPOCH`, `NO_FRAME`, `INVALID_REQUEST`, and `STALE_EPOCH`. Check the requested timestamp itself before choosing a prior frame: asking for future time cannot return a stale frame as a successful future lookup. Interval requests must validate both endpoints. An event clip requiring post-event frames must wait for those frames or return explicitly partial coverage; it cannot read ahead.

Random access may decode earlier keyframes internally, but must never expose unarrived/expired frames or preroll. Revalidate availability/epoch on completion of asynchronous requests to prevent a seek or eviction race. Clip exports must trim to authorized coverage rather than leak expired/future frames via keyframe-aligned copying. Original files remain unchanged.

Later live adapters can store standard-codec compressed segments with timestamp indexes behind the same API. Segment boundaries/keyframes are internal details. Future tiered retention may choose the highest quality still retained (e.g. 10 minutes high quality, 24 hours sparse/lower quality, selected events longer), returning tier/quality/coverage metadata. Tiering is not in Milestone 1.

## Derived streams and synchronization

Initial Stream A: 64×64 grayscale at 15 FPS. Initial Stream B: 320×320 RGB at a fixed configurable 1 FPS for visualization only. Later detection scheduling is separate from this fixed sampling setting. Preserve aspect ratio by letterboxing; record padding, scale, source dimensions, and phone rotation transforms so later boxes/crops map correctly.

Proposed deterministic sampler: anchor a target grid to the requested epoch start; for each ingested frame, emit it once if its PTS meets or exceeds the next target. Attach both target and actual source timestamps. Advance the grid past the emitted PTS; count crossed targets as missed rather than duplicating the frame. Equal-PTS frames do not create extra samples. Rates above source cadence never fabricate frames. Compute grid times with rational arithmetic, not cumulative float additions. Streams independently sample the same ordered arrivals. Neither stream's compute speed changes its media schedule.

Mid-run setting changes are explicit recorded configuration revisions effective at the next arrival; re-anchor the affected sampler there. Resize/color transforms do not change source timestamps. Display lag, skipped target slots, source gaps, and actual sample rates rather than implying uniform frame intervals. A bounded UI refresh queue may replace old display frames, but must not change core sampling results.

## Models, controller, and future results

Individual single-frame models can remain stateless: accept a frame/crop envelope and model configuration; return frame identity, model/version/weight digest, preprocessing configuration, outputs, confidence, and duration. Later temporal adapters consume ordered same-epoch sequences. Each analysis request/result has an ID linking it to the exact run/frame/model; record failure, cancellation, and skipped work too.

The controller consumes timestamped motion/detection/events and emits analysis requests with target timestamps/regions, requested model/quality, reason, priority, and deadline. It owns state and cost budgets, while cache and models remain independently replaceable. It may increase inference frequency, fetch better frames/sequences, request tracking, retain a clip, or return to cheap monitoring.

Future scheduling hypothesis: run at startup, every 60 simulated seconds while idle even if a person is stationary, immediately on meaningful motion, about once per second during activity, with optional initial bursts. Deduplicate overlapping triggers. These are Milestone 4 experiments, not rules to implement now.

When expensive inference arrives, use bounded worker queues and explicit overload/cancellation policies so ingestion is not held by a slow model. Choose threads/processes only after measurements; no distributed broker now. Record queue wait separately from inference time and reject stale-epoch results. Offline experiments may use deterministic backpressure; paced experiments must report deadline misses and drops so comparisons remain fair.

## Browser observability

Milestone 1 UI: upload MP4/MOV, source preview, play/pause/resume/restart/seek/loop/speed/mode controls, simulated timestamp, arrival watermark, retained range, both derived streams and settings, actual frame timestamps, sample gaps, lag, throughput, decode/transform durations, and memory observations. Keep background playback state separate from Streamlit reruns; pause must actually stop clock advancement. Later add motion heatmaps, boxes/counts/confidence, escalation history, latency, training controls, and comparisons.

No model inference, motion algorithms, tiered storage, training framework, or external services are required for Milestone 1.
