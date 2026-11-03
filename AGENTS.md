# Instructions for coding agents

1. Read `README.md` and `docs/architecture.md` before major changes, then the relevant milestone plan and configuration specification.
2. Vision Lab is a general-purpose computer-vision learning project, not merely a security-camera application.
3. The user primarily directs development through natural-language requests. Explain decisions in accessible language and design ordinary experiments for the browser interface.
4. Implement only the explicitly requested milestone. Do not automatically implement future features. Milestone 0 contains documentation and directories only.
5. Preserve modular separation among sources, ingestion, cache, derived streams, models, and controller. Keep UI concerns out of core processing.
6. Preserve the common video timeline, presentation timestamps, epoch boundaries, and no-future-access rule. Distinguish source time, simulated time, wall time, and processing duration.
7. Prefer straightforward implementations over elaborate infrastructure. Explain the purpose of major dependencies or architectural changes before introducing them.
8. Make intermediate results, timing, cache availability, dropped frames, and processing cost observable through the web interface.
9. Add relevant automated tests when implementing functionality, especially deterministic sampling, cache boundaries, and reset behavior. Report skipped and unrun checks honestly.
10. Document significant architectural choices and trade-offs in `docs/decisions.md`. Keep hypotheses separate from validated conclusions; preserve earlier hypotheses and evidence history.
11. Never modify or overwrite original source recordings. Decode read-only and write derived artifacts separately.
12. Never commit video datasets, large model checkpoints, or secrets. Do not force-add ignored data. Review staged files before committing.
13. Preserve repeatability and fair comparisons: record input hashes, exact configuration, code/dependency/model versions, seeds, hardware, timing, and omissions.
14. Finish tasks with changes, testing, limitations, and suggested next steps.
15. Use existing checkouts in isolated cloud tasks. Do not create Git worktrees unless explicitly requested.
16. GitHub is the source of truth. Codespaces/cloud disks are not permanent storage; document backup/export needs without uploading private data automatically.
