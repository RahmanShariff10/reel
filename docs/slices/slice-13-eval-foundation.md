# Slice 13 — Evaluation foundation

**Owner:** Dev A · **Sprint:** 03 · **Target week:** 6–7 · **Depends on:** 02, 12

## Module
`eval`

## What to build
- **Cricsheet loader** `eval/cricsheet.py`: reads a Cricsheet T20 JSON and returns balls with innings, over.ball, total runs, batter runs, extras type, wicket flag, and is-four / is-six. Ground truth: a four is batter runs 4 or byes/leg-byes 4; a six is batter runs 6. Wides and no-balls keep their own over.ball handling.
- **Annotation format** `eval/annotations/<match_id>.csv`, with columns `match_id, innings, over_ball, type, t_start_s, t_moment_s`, and a validator.
- **E1 metric** `uv run python -m eval.e1 --job <job_id> --cricsheet <file>`: matches our score events to Cricsheet balls by innings + over.ball (with over.ball read from the timeline), then reports precision / recall / F1 for four, six and wicket. Writes `eval/reports/<match_id>/e1.md` and `e1.json`.
- A tiny hand-made Cricsheet-format JSON committed as a test fixture.

## Acceptance criteria
- [ ] Given the fixture JSON, then the loader returns the correct number of fours, sixes and wickets per innings.
- [ ] Given a ball with 4 leg-byes, then it counts as a four; given a wide, then the over.ball numbering stays correct.
- [ ] Given an annotation file with a missing column or a bad over format, then the validator reports the line and the problem.
- [ ] Given predictions identical to the ground truth, then E1 reports precision = recall = 1.0 for every type.
- [ ] Given predictions missing one of n sixes, then six recall is (n−1)/n.
- [ ] Given a run, then the report files are written to `eval/reports/<match_id>/`.

## Out of scope for this slice
E2–E5 metrics (slices 25–26).

## Human review required?
No.
