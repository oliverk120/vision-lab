# Decision record

These are initial design choices, not evidence that the proposed system is efficient. Preserve superseded entries and link new decisions and experiments rather than rewriting the project's history.

## Initial decisions — 2026-11-03

| ID | Status | Choice and rationale | Trade-off / revisit trigger |
| --- | --- | --- | --- |
| D01 | Accepted | Modular single-process-first research platform, CPU by default; learn before adding infrastructure | Limited throughput; revisit with measured bottlenecks |
| D02 | Accepted | Shared source PTS timeline and explicit playback epochs; paced and offline execution share processing logic | More timing bookkeeping than frame-count/FPS; necessary for VFR and reproducibility |
| D03 | Accepted | Logical rolling view over read-only original MP4/MOV first, with all retrieval through cache | Does not reproduce live segment storage cost; replace internals for USB/IP sources |
| D04 | Accepted | Derived frames may fan out during ingestion after arrival publication | Avoids redundant I/O, but requires strict boundary enforcement |
| D05 | Provisional | 600-second high-quality retention, Stream A 64×64 gray at 15 FPS, B 320×320 RGB | Hypotheses, adjustable; evaluate accuracy/cost before treating them as defaults for real use |
| D06 | Proposed for M1 | Python 3.12, uv lockfile, PyAV timestamp-aware decoding, OpenCV headless transforms, Streamlit UI | Validate phone codecs, rotation, VFR, and UI replay lifecycle before locking dependency choices |
| D07 | Accepted | No models or motion algorithms until later milestones | M1 produces synchronized observable streams, not intelligent event detection |
| D08 | Proposed for M1 | Rational time, frame metadata envelope, at-or-before cache lookup, first-arrival-at/after-target sampling | Clear deterministic semantics; actual samples may lag grid and must expose that offset |
| D09 | Proposed for M1 | Seek/restart/loop clear state and create a new epoch; seek discards private keyframe preroll | Seeking does not instantly fill historical cache; rebuilding history can be a later explicit mode |
| D10 | Proposed for M1 | Letterbox with coordinate metadata, fixed 1 FPS B preview initially | Preserves geometry at expense of padding; model-specific preprocessing is a later versioned choice |
| D11 | Accepted | Standard codecs and local files; no database server, custom compression, or distributed system | Structured local results may need evolution as data grows |
| D12 | Accepted | Source files immutable; Git stores code/docs/config, separate durable backup for valuable data | Requires explicit export/backup beyond disposable Codespaces disks |

## Open questions and decision gates

| Question | Options and provisional direction | Decide when / evidence |
| --- | --- | --- |
| Video source interface? | Iterator plus controls/capabilities vs asynchronous producer; use the conceptual contract in architecture first | M1 source slice; prove pause/seek without UI coupling |
| Frame representation? | Bare NumPy array vs metadata envelope vs decoder frame; prefer envelope with array-compatible payload | M1 contract tests; measure copies and ownership safety |
| Timestamp storage? | Floats vs integer ticks + rational time base; prefer original ticks and exact normalized arithmetic | M1 VFR/duplicate-PTS tests |
| Independent replay clock? | Injectable clock and pacing wrapper vs timing inside decoder; prefer independent clock | M1 fake-clock tests, pause and speed re-anchoring |
| Deterministic sampling and late frames? | Nearest/prior/first-at-or-after; propose causal first-at-or-after grid, count missed targets, no implicit duplicates | M1 sampling tests; later evaluate jitter and loss policies |
| Seek/loop cache behavior? | Clear epoch vs replay history rebuild; clear initially | M1 backward/forward seek and EOF tests |
| Initial cache backing? | Original compressed file index vs decoded ring; prefer indexed original, optional small bounded decode cache | M1 lookup latency and RAM measurements |
| Live camera buffering? | Compressed standard-codec segments with index vs in-memory packets | Live-source extension; check keyframe boundaries, reconnects, missing timestamps |
| How to avoid inference blocking ingestion? | Bounded threads/process workers; measure before choosing | M3/M4 latency and queue tests; specify backpressure/drop behavior |
| Record which models analyzed frames? | Structured local JSONL results and manifests vs embedded database | M3; every result must identify run/epoch/frame/model/request |
| Record inputs, outputs, duration, confidence? | Metadata and hashes by default, optional separately stored input crops | M3; balance auditability, disk use, and private footage |
| Reproduce after model upgrades? | Lock dependencies and retain weight digests, preprocessing and configuration manifests | M3 onward; compare on identical source and labels |
| Detector and license? | Nano YOLO family vs other small CPU-compatible detectors | M3; review weight/code licenses, provenance, accuracy and latency before adding packages |
| Phone video quirks? | PyAV codec support, optional trusted FFmpeg CLI, rotation/HDR conversion | M1 representative MP4/MOV tests; define supported codecs and clear unsupported errors |
| Streamlit playback lifecycle? | Session-owned worker and bounded display queue vs cooperative stepper | M1 UI integration; prove reruns do not create duplicate ingestion or block pause |

## New decision template

Record ID, date, status (proposed/accepted/superseded), problem, options, chosen approach, rationale, consequences, test/experiment links, and revisit condition. A performance claim needs evidence in [experiments](experiments.md).
