# Experiments and hypotheses

No hypotheses below have been validated. Initial dimensions, rates, models, and retention durations are starting points for experiments, not conclusions.

## Initial hypothesis register

| ID | Hypothesis | Suggested experiment and measures |
| --- | --- | --- |
| H01 | Low-resolution, high-FPS footage may suffice for basic motion detection | Compare resolutions and sampling rates on labeled physical-motion events; recall, false triggers, CPU time |
| H02 | Classical image processing may cost less than neural inference for motion detection | Frame difference/background subtraction vs small model on identical footage; accuracy, CPU time, energy only if measured |
| H03 | Small single-frame networks at low frequency may detect people adequately | Sweep model size and frequency; event recall, time to detection, missed short appearances |
| H04 | Reliable counting may need higher resolution | Compare count error, small/occluded-person recall, and latency across resolutions |
| H05 | Motion-triggered scheduling may substantially reduce inference cost | Compare continuous and triggered inference on the same labeled timeline; total work, false negatives, detection delay, stationary-person misses |
| H06 | High-resolution rolling cache may combine cheap monitoring with richer later analysis | Compare low-res-only results with escalated cache retrieval; coverage, expired requests, retrieval latency, accuracy |
| H07 | Selective model sophistication may outperform continuous expensive analysis on cost | Compare cascades against always-on model; total decode/transform/inference cost at matched recall |
| H08 | Temporal attention may help interpret multi-frame events | Compare frame baseline, recurrent sequence model, attention; event metrics, data needs, latency |
| H09 | Retention tiers may provide useful history at manageable storage cost | Vary quality/FPS/duration; bytes retained, retrievable event coverage, retrieval quality |
| H10 | CPUs may suffice for early stages | Measure sustained throughput, lag, memory, decode and inference latency on documented CPU allocations |

Lighting changes are not synonymous with physical motion. Include light switches, gradual illumination, shadows, sensor noise, camera movement, empty scenes, still people, brief entry/exit, multiple people, and occlusion as separate labeled cases. Report results by case instead of hiding them in one aggregate score.

## Run record specification

Future runs live under ignored `runs/<run-id>/`; this is a specification, not a recorder implementation. A manifest should contain:

- Run ID, UTC start, hypothesis/experiment ID, code commit and dirty-state marker, dependency lock digest, Python/decoder/library versions.
- Source hash, anonymized source identifier, size/duration, codec, dimensions, rotation, time base, VFR observations, and label-set version. Do not publish personal file paths or imagery.
- Full resolved configuration with units and schema version, replay mode/speed, seek/loop/control history and epochs, stream configuration revisions, sampling and overload policies, seeds, and determinism limitations.
- CPU model/allocation, RAM, OS, optional accelerator, thread/worker limits, and concurrent-load observations.
- Exact model implementation/version, weight hash and license/source, preprocessing, thresholds, device, and training/dataset versions where applicable.
- Frame/request/result identity, source/target/simulated timestamps, monotonic durations, queue delay, outputs/confidence, failures, cancellations, gaps/drops, and cache availability/quality.
- Aggregate metrics, methodology, warm-up treatment, repeat counts, variability, and links to local artifacts or durable backups.

Record model checkpoints, raw outputs, clips, and labels outside Git and back them up explicitly. Keep compact sanitized experiment reports in documentation only after reviewing them for private material. Gitignore is a guard, not a substitute for reviewing staged files.

## Fair comparison protocol

1. State the hypothesis and falsifiable success criterion before running. Preserve the original statement.
2. Use the same input hashes, labels/splits, time ranges, replay mode, and hardware limits. Change one factor at a time when practical.
3. Separate deterministic sampling equivalence from nondeterministic runtime duration and model/device behavior. Offline speed is not proof of real-time viability.
4. Report total pipeline cost, not just inference: decode, transforms, retrieval, queue wait, model work, memory, and storage where relevant.
5. Compare accuracy/recall and latency alongside cost. Count skipped inference, missing frames, expired clips, and false negatives; do not claim savings from silently doing less required work.
6. Repeat runs, state warm-up handling and variability, and keep failures and counterexamples.
7. Record conclusion as supported, contradicted, or inconclusive with scope and limitations. Link follow-up hypotheses and superseding decisions.

## Experiment report template

- ID/date/title and linked hypothesis IDs:
- Original hypothesis and expected result:
- Setup, input/label hashes, code/config/model versions, run IDs:
- Variables changed and controls:
- Metrics and acceptance criteria:
- Results (including failures and variance):
- Interpretation, confounders, limits:
- Conclusion status and next experiment:

No training infrastructure is required yet. Milestone 6 will add dataset splits, leakage checks, training seeds, optimizer schedules, checkpoint provenance, and held-out evaluation.
