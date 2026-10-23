# ADR-002 — The on-screen score graphic, found automatically, is the primary event signal

## Context
We need to know *what* happened on each ball (four, six, wicket) without training an action-recognition model, on a CPU, and with no user input.

## Decision
The app automatically locates the score box (score-like text in a stable position, validated over time), reads it with OCR at 2 fps, and turns the readings into a validated match-state timeline. Score changes determine event types. Audio and camera shots provide timing and excitement, not event type. If the box can't be found, the pipeline falls back to audio + video signals only.

## Why
- Score changes are near-ground-truth: +4 = four, +6 = six, wickets +1 = wicket. Prior work reports F1 ≈ 0.98 for scoreboard-OCR event detection (Guntuboina et al. 2021) and 98% scoreboard-parsing accuracy (Amazon 2026).
- Cheap on CPU: after locating the box, only a small crop is recognised, and only when it changes.
- Automatic location keeps the PRD's "upload and wait" promise and doesn't depend on any one broadcaster's graphic style.
- The box being hidden doubles as a cheap replay signal on many broadcasts.

## Alternatives considered
- **User draws the box:** most reliable, but breaks "upload and wait". Kept only as a should-have fallback.
- **Trained scoreboard detector (YOLO):** needs labelled data per broadcaster; unnecessary since text patterns + position stability work without training.
- **Audio/visual-only event detection:** can't tell a four from a wicket; kept as the fallback mode and as the ablation baseline.
