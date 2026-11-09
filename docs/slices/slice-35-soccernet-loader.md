# Slice 35 — SoccerNet loader and match preparation

**Owner:** Dev A · **Sprint:** F1 · **Target week:** 1 · **Depends on:** none

## Module
`eval`

## What to build
- `eval/soccernet.py`: load `Labels-v2.json` and `Labels-cameras.json` into dataclasses. Each label has `half`, `game_time`, `position_ms`, `label`, `team`, `visibility`. Camera labels also have `replay` (bool).
- `KEY_ACTIONS = {"Goal", "Penalty", "Red card", "Yellow->red card", "Shots on target"}`.
- `python -m eval.prepare --game <soccernet path> --videos <dir> --out <dir>`: joins `1_720p.mkv` and `2_720p.mkv` with ffmpeg stream copy into `match.mkv`, and writes `match.json` with `first_half_s`.
- `to_match_time(label, first_half_s)`: seconds in the joined file.
- `eval/manifests/matches.yaml`: 5 dev games and 10 test games, with `split` and `commentary_language`. Filled in after slice 38; the file format is built here.

Labels download to `eval/soccernet/` (gitignored). The unit-test fixture is a small hand-written label file, not a copy of a SoccerNet one.

## Acceptance criteria
- [ ] Given a `Labels-v2.json`-format fixture, then every annotation loads with the right half and milliseconds.
- [ ] Given a second-half label at 100 000 ms and `first_half_s` of 2800, then `to_match_time` returns 2900.0.
- [ ] Given the fixture, then only the five key-action labels are returned as key actions.
- [ ] Given a `Labels-cameras.json`-format fixture, then `replay` is true only for `"replay"` rows.
- [ ] Given two synthetic half videos, then `eval.prepare` produces a playable file whose duration is their sum (±0.5 s), without re-encoding.
- [ ] Given a manifest missing a required field, then a clear error names the game and field.

## Out of scope for this slice
Metrics (slice 50). Downloading videos.

## Human review required?
No.
