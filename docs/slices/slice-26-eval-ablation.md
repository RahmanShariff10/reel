# Slice 26 — Ablation

**Owner:** Dev B · **Sprint:** F5 · **Target week:** 11–12 · **Depends on:** 49, 50

## Module
`eval`

## What to build
**E4 ablation runner** `uv run python -m eval.ablation --match <id>`:
- runs these configurations in a fixed order: audio only → + camera shots → + commentary → full (+ score reading);
- each variant copies the job folder and deletes outputs from the first affected stage onwards, so the expensive scan is reused;
- computes E1, E2, E3 and E5 for each variant.

Results are written to `eval/reports/<match_id>/ablation.md` and linked from the summary report.

## Acceptance criteria
- [ ] Given a match, then each ablation variant reuses the scan outputs (scan stage not re-run, verified by timings or call counts).
- [ ] Given the variants, then a table shows the metrics per variant in the fixed order.
- [ ] Given a variant without the score signal, then goal metrics are n/a rather than 0.
- [ ] Given a run, then `ablation.md` is written and linked from `summary.md`.

## Out of scope for this slice
Viewer survey (a human task, only if footage rights allow).

## Human review required?
No.
