# Slice 03 — Synthetic test videos

**Owner:** Dev B · **Sprint:** 01 · **Target week:** 1–2 · **Depends on:** 01

## Module
Tests (`backend/tests/fixtures/`)

## What to build
`tests/fixtures/make_synthetic.py` generates a short fake "match" with ffmpeg plus a ground-truth `schedule.json`, so every module can be tested without real footage.

**Video** (default 120 s, 1280×720, 25 fps):
- **Scenes:** solid-colour scenes separated by hard cuts. A "run_up" scene has a green field with a brown pitch rectangle; other scenes are "close_up", "crowd", "field" and "graphic".
- **Score box:** drawn with `drawtext` at a fixed position (e.g. `IND 12/1  2.3`), changing on a known schedule. It covers fours, sixes, wickets, one innings reset and one DRS reversal (wicket +1, then −1 within 60 s).
- **Hidden box:** "replay" segments where the score box is hidden.
- **Audio:** low background noise with loud bursts at known times.

**Options:** `--duration`, `--seed`, `--order runs-wickets|wickets-runs`, `--no-scorebox`, `--no-audio`, `--distractor` (an extra static number graphic, e.g. `RR 8.25`, in another corner).

**pytest:** a session-scoped fixture `synthetic_match` returns paths to the video and the schedule.

## Acceptance criteria
- [ ] Given default options, when the generator runs, then `video.mp4` and `schedule.json` are produced in under 30 s.
- [ ] Given the output, when inspected with ffprobe, then duration is within 0.1 s of requested, resolution is 1280×720, and an audio stream exists (none with `--no-audio`).
- [ ] Given `schedule.json`, then it lists every cut time and scene type, every score-box text change with its time, hidden-box intervals, the true score-box rectangle, and burst times.
- [ ] Given the same arguments and seed, when run twice, then `schedule.json` is identical.
- [ ] Given a frame grabbed at a scheduled time and cropped to the true score box, when read with RapidOCR, then the text matches the schedule.
- [ ] Given `--order wickets-runs`, then the score box shows `wickets/runs`.
- [ ] Given `--distractor`, then a static numeric graphic appears in a different corner for the whole video.

## Out of scope for this slice
Realistic imagery. Any pipeline stage.

## Human review required?
No.
