# Slice 25 — Evaluation metrics and report

**Owner:** Dev A · **Sprint:** 06 · **Target week:** 11–12 · **Depends on:** 13, 22

## Module
`eval`

## What to build
- **E2 delivery detection:** detected deliveries vs Cricsheet balls (including wides and no-balls), matched by innings + over.ball where readable and by order otherwise. Reports recall, precision and the count gap.
- **E3 clip accuracy:** for each annotated wicket and boundary, find the event's clip. A clip "contains the moment" if `clip.start ≤ t_start_s` and `clip.end ≥ t_moment_s + 3 s` (tolerances in config). Reports the % of clips containing the moment, plus the median and 90th-percentile start offset.
- **Runtime:** total and per-stage processing time from `summary.json`.
- **Report:** `uv run python -m eval.report --matches m1,m2,...` aggregates E1–E3 and runtime across matches into `eval/reports/summary.md` and `summary.csv`, comparing each number with its PRD target.

## Acceptance criteria
- [ ] Given a constructed job where every delivery matches Cricsheet, then E2 recall and precision are 1.0.
- [ ] Given a clip starting 2 s after the annotated `t_start_s`, then it counts as not containing the moment, and the offset is reported as +2 s.
- [ ] Given several matches, then the report aggregates per match and overall, and marks each metric met/not met against the PRD targets.
- [ ] Given the same inputs, then the report is identical across runs.

## Out of scope for this slice
Ablation and official-highlights comparison (slice 26). Viewer survey analysis (human task).

## Human review required?
No.
