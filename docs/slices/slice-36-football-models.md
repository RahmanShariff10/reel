# Slice 36 — Football data models

**Owner:** Dev A (Dev B reviews) · **Sprint:** F1 · **Target week:** 1 · **Depends on:** none

## Module
`common`

## What to build
Replace the cricket models in `common/models.py` and `common/config.py` with those in ARCHITECTURE.md's Data model:
- `Scorebox`: add `clock_box`, remove `order`.
- `ScoreReading`, `ScoreTimelineEntry`, `ScoreEvent`: football fields.
- `Moment` replaces `Delivery`.
- `Event` and `EventType`: new types, `moment_id`, `minute`, `half`.
- `ShotLabel`: `wide`, `medium`, `close_up`, `crowd`, `graphic`.
- `Summary`: `final_score`, `halves`, `moments_found`.
- `JobPaths`: `moments_json`, `commentary_json` replace `deliveries_json`.
- Config sections for `scoreboard`, `moments`, `commentary`, `highlights`, and `signals.commentary`, with the defaults in ARCHITECTURE.md.

This slice is expected to leave cricket-dependent modules and their tests broken until their replacement slices land. List them in the PR and skip those test files with a `reason` naming the slice that replaces them.

## Acceptance criteria
- [x] Given each new model, then it round-trips through `write_model` / `read_model`.
- [x] Given a `ScoreReading` with `home` of -1, then validation fails.
- [x] Given `Moment.minute` of `"45+2"` or null, then it validates.
- [x] Given an `Event` type of `"wicket"`, then validation fails.
- [x] Given `load_config()`, then every new threshold in ARCHITECTURE.md is present with its documented default.
- [x] Given the test suite, then only tests skipped with a named replacement slice are not run; everything else passes.

## Out of scope for this slice
Any module logic.

## Human review required?
Both devs agree the model changes (`common` rule).
