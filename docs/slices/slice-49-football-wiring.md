# Slice 49 — Football pipeline wiring and cricket removal

**Owner:** Dev A · **Sprint:** F3 · **Target week:** 6 · **Depends on:** 39–48

## Module
`jobs`

## What to build
- `DEFAULT_STAGES` per ARCHITECTURE.md (10 stages), with `commentary` switchable.
- `signals.shots` actually takes effect: when off, every shot is treated as `wide` for `play_start_s`.
- Remove what's left of cricket: `deliveries/`, `jobs/placeholders.py` (unused), cricket config keys, `eval/cricsheet.py`, skipped tests from slice 36.
- `pyproject.toml` description.
- `reel run` CLI works end to end.

## Acceptance criteria
- [ ] Given the synthetic match, then `reel run` produces a reel whose goals match the schedule.
- [ ] Given a crash mid-pipeline, then a re-run skips completed stages.
- [ ] Given a re-cut to `3min`, then only `highlights` and `render` re-run.
- [ ] Given each signal off, then the pipeline completes and that signal has no effect on `events.json`.
- [ ] Given the codebase, then a search for `wicket`, `innings` and `delivery` finds nothing outside `docs/` history.
- [ ] Given the full suite, then no tests are skipped and all pass.
- [ ] Human: one real match runs through `reel run`; total and per-stage time go in the sprint notes.

## Out of scope for this slice
API and frontend.

## Human review required?
No.
