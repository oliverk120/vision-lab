# Configuration specification

[example.toml](example.toml) is a proposed Milestone 1 experiment configuration, not a working runtime configuration. No loader or validator exists yet. All units are explicit; original media remains read-only. These settings are hypotheses and can be revised with documented reasons.

| Field | Meaning and future validation |
| --- | --- |
| `schema_version` | Integer schema version; initially 1; reject unknown versions/keys rather than silently ignoring misspellings |
| `source.kind` | Initially `file`; webcam/IP adapters later |
| `source.path` | User-selected local MP4/MOV file; browser upload supplies this value; example path need not exist |
| `replay.mode` | `paced` or `offline`; both preserve source timing and ordering |
| `replay.speed` | Finite positive pacing multiplier; 1 means real time; recorded but ignored for offline waits |
| `replay.loop` | Boolean; each loop creates a new epoch; finite offline experiments should disable looping |
| `cache.retention_seconds` | Finite positive duration in simulated/source time; initial 600; inclusive bounds per architecture |
| `streams.<name>.width/height` | Positive integer output dimensions |
| `streams.<name>.color` | `gray` or `rgb`; no implicit OpenCV BGR exposure |
| `streams.<name>.fps` | Finite positive target frequency, interpreted as an exact decimal/rational for sampling, not source FPS |
| `streams.<name>.resize` | Initially `letterbox`; report scale/padding/rotation metadata |

Record the full resolved configuration with each run. Runtime stream changes create logged revisions effective at the next arrival; they must not retrospectively change earlier results. The source's observed dimensions/FPS are metadata, never forced to 1080p/30. Sample rate above source cadence does not synthesize frames.

Initial B rate is a preview sampling default, **not** the future detector schedule. Startup/60-second idle/1-second active/burst scheduling belongs to Milestone 4 and is deliberately absent here. No model, motion, training, or tiered-retention settings are enabled.
