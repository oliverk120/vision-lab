# Development roadmap

Milestone 0 is complete. The user authorized and expanded Milestone 1 to include the experimentation workbench; later algorithms still require explicit requests. They are learning checkpoints, not automatic expansion of scope.

| Milestone | Scope | Completion evidence |
| --- | --- | --- |
| **0 — Architecture and scaffold** | README, agent guidance, architecture, decision/hypothesis records, roadmap, directories, ignore rules, configuration specification, M1 plan | Documents agree; links/config parse; directories preserved; no implementation, dependencies, data or secrets committed |
| **1 — Video infrastructure** | Implemented: MP4/MOV replay/cache, A/B frame explorer, local library/annotations, mock plugin batches, evaluation, results UI; real-phone and hosted Codespaces acceptance remain to be checked | Real phone recording replays; VFR timing and synchronization correct; no future/expired access; seek/restart/loop reset safely; repeatable offline samples; UI exposes timing/cache/metrics; see [detailed plan](milestone-1.md) |
| **2 — Basic motion detection** | Stream A frame differences/background subtraction; sensitivity and illumination experiments; visualization | Automated algorithm cases plus labeled motion/light/noise examples; heatmaps and scores visible; report physical-motion recall, false triggers and CPU cost |
| **3 — Person detection** | Small pretrained CPU detector using B frames; presence, count, boxes, confidence | Known fixtures exercise preprocessing and coordinates; evaluate labeled footage across resolutions; record count/detection errors, latency, model/license/version; stationary people remain detectable |
| **4 — Scheduling and escalation** | Startup/idle/activity inference, motion triggers, optional bursts, high-quality cache retrieval | Fake-timeline scheduling tests, bounded queues and stale-result rejection; compare cost/false negatives/delay with continuous inference, including still people and expired footage |
| **5 — Temporal analysis** | Tracking and event recognition; embeddings, GRU/LSTM, attention experiments | Same-epoch sequence tests, track/event metrics on labeled sequences, comparisons with single-frame baseline; quantify extra cost and failure cases |
| **6 — Custom model training** | Labeled datasets, PyTorch training/fine-tuning, evaluation, checkpoint/version comparisons | Reproducible manifests and splits, leakage checks, resumable checkpoint provenance, held-out metrics and fair baseline comparison; durable artifact backups |

## Later extensions, not implicit milestones

USB webcams and IP cameras should use the existing source contract, with capability flags and real compressed rolling segments. Tiered retention may preserve lower-quality history for roughly 24 hours and selected events longer; durations require experiments. GPU execution, vision-language models, and video transformers are options only when evidence justifies their complexity.

Production hosting, database servers, authentication, multi-user collaboration, custom compression, GPU provisioning, distributed processing, and large training infrastructure remain out of scope until separately justified.
