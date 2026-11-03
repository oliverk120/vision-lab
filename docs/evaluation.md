# Evaluation rules (Milestone 1)

Only synthetic mocks are registered. They inspect timestamps, not pixels, and do not validate any motion-detection hypothesis. Pixel differences in the gallery are inspection aids, not predictions.

## Ground truth

The default target definition is actual objects or people changing position, excluding illumination/exposure changes alone. A recording stores an editable definition, video-level Yes/No/Unknown, scene notes, tags, and development/holdout membership. Keep definitions consistent when comparing a dataset; changing the text does not relabel existing intervals automatically.

Temporal labels use **[start, end)** source-relative seconds. An environmental label may be Unknown while overlapping confirmed physical motion. Confirmed Yes and No cannot overlap. Same-truth overlapping intervals are unioned to avoid counting time twice. Unknown and unlabeled time is excluded from temporal denominators. Video-level No does **not** automatically label every second negative: add explicit negative intervals when temporal scoring is wanted. A video-level Unknown is excluded from video confusion counts.

## Predictions and grouping

A score in [0,1] is thresholded using `score >= threshold`; when score is absent, use the detector's boolean. A prediction applies from its actual source timestamp until the earliest of the next sample, source end, or `max_sample_hold` seconds later. Duplicate timestamps have zero-duration earlier holds. The maximum hold defaults in the UI to one sampling period. This is an explicit approximation of a sampled signal, not proof that motion occurred between frames.

Consecutive positive holds are unioned, bridging gaps no longer than `allowable_gap`. Drop events shorter than `minimum_duration`. A video-level prediction is positive if **at least one grouped event survives**. No threshold is automatically tuned, especially on holdout footage.

## Distinct metric families

1. **Video confusion:** one TP/FP/TN/FN per known-labeled recording per algorithm/configuration. Precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = 2TP/(2TP+FP+FN); accuracy = (TP+TN)/N; balanced accuracy = mean(positive recall, negative recall). Undefined denominators produce null, not zero. Balanced accuracy is null if either class is absent. The comparison table aggregates counts within experiment, algorithm/configuration, and split; it does not average F1 scores across videos.
2. **Time-weighted confusion:** intersect raw thresholded sample holds with explicit positive/negative labels. Counts have units of **seconds**, not frames. Event gap/minimum-duration rules do not alter these raw time metrics. Report labeled, evaluated, and uncovered labeled seconds. Missing prediction coverage is reported separately, never silently counted as a true negative.
3. **Event metrics:** union positive ground-truth intervals. Process truth intervals chronologically; choose one unused prediction overlapping the truth expanded by `tolerance` seconds, preferring maximum actual overlap, then closest start. Each event can match at most once. Report detected/missed truth events. Unmatched events overlapping confirmed negative time are false alarms; other unmatched events are ignored for false-alarm scoring and listed separately. Event precision/recall therefore describe annotated coverage only, not entire unknown recordings. A long event matching one target is not also counted as a false alarm, even if it spills into negative time; time-weighted FP duration exposes that behavior.
4. **False alarms/minute:** unmatched negative-overlapping events divided by explicitly negative labeled minutes. This is **not** divided by whole-video duration. The table reports the arithmetic mean of defined per-video rates, labeled as a mean; inspect per-video metrics and exposure for interpretation.
5. **Latency:** `max(0, prediction_start - truth_start)` for matched events. Early/tolerance matches have zero latency. Missed events are counted separately, not given zero latency.
6. **Cost:** per-call monotonic processing duration, summed algorithm time, mean per processed frame, total per-video/algorithm decode+transform+algorithm runtime, and missed sampling targets. Run runtime excludes subsequent scoring/result serialization. CPU durations vary even when predictions are deterministic.

The per-frame browser table uses the label at the sampled timestamp and marks TP/FP/FN/TN/Unknown. It is diagnostic, not the time-weighted metric. Events falling entirely between low-FPS samples may have no FN row; they remain missed events in the temporal results. The shared-time comparison displays both transforms, explicitly indicating when that frame was not sampled by an algorithm.

## Reproducibility and portability

Each run snapshots source SHA-256/metadata, video IDs, annotations and target definition, split, algorithm identity/version/configuration, stream configuration, evaluation configuration, exact PTS/time base/source timestamp, code commit and dirty marker, package/Python/platform versions, lockfile hash, and timing. Annotation edits never retroactively change saved results. Results use JSON plus CSV; optional masks/debug images are referenced by each prediction. Export ZIPs contain results, not original footage. Import rejects unexpected/traversing paths and never overwrites an experiment.

Compare like-for-like input hashes, annotation snapshots, definitions, sampling and preprocessing settings. Code marked dirty is not exactly reproducible from its commit alone; commit the tested code before a durable benchmark. Offline runs are sequential and deterministic for deterministic plugins; third-party algorithms must declare their seeds and nondeterminism. Python plugins are trusted local code, not a security sandbox: the public interface supplies only the current sample and never a source/cache handle.
