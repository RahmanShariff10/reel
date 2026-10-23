# Slice 26 — Ablation and official-highlights agreement

**Owner:** Dev B · **Sprint:** 06 · **Target week:** 11–12 · **Depends on:** 13, 22, 25

## Module
`eval`

## What to build
- **E4 ablation runner** `uv run python -m eval.ablation --match <id>`:
  - runs these configurations: audio only → audio + camera shots/replays → full (+ score reading);
  - each variant copies the job folder and deletes outputs from the first affected stage onwards, so the expensive scan is reused;
  - computes E1/E3 for each variant.
- **E5 official-highlights agreement:** reads `eval/annotations/official_<match_id>.csv` (innings, over_ball) and compares it with the deliveries in our same-length reel. Reports precision, recall and Jaccard. For variants without over.ball, deliveries are matched by time overlap with the annotated moments.
- Results are written to `eval/reports/<match_id>/ablation.md` and included in the summary report.

## Acceptance criteria
- [ ] Given a match, then each ablation variant reuses the scan outputs (scan stage not re-run, verified by timings or call counts).
- [ ] Given the variants, then a table shows E1/E3 per variant in a fixed order.
- [ ] Given an official list identical to our reel's deliveries, then E5 precision = recall = Jaccard = 1.0.
- [ ] Given a variant without over.ball, then E5 still computes by time overlap.
- [ ] Given a run, then `ablation.md` is written and linked from `summary.md`.

## Out of scope for this slice
Viewer survey (human task in sprint 06–07).

## Human review required?
No.
