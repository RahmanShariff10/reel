# Slice 42 — Football camera shots

**Owner:** Dev B · **Sprint:** F2 · **Target week:** 3–4 · **Depends on:** 36; 38 for the training part

## Module
`shots`

## What to build
- Football CLIP prompts for `wide`, `medium`, `close_up`, `crowd`, `graphic`.
- `python -m reel.shots.train --from-soccernet <games>`: builds training labels from `Labels-cameras.json` by mapping each camera class to a `ShotLabel` (mapping in config) and taking the shot at each keyframe's time. Replay rows are skipped.
- Report comparing zero-shot and trained classifier using leave-one-match-out validation.

## Acceptance criteria
- [x] Given stub embeddings, then zero-shot labels use the new classes.
- [x] Given a cameras file, then "Main camera center" maps to `wide`, "Close-up player or field referee" to `close_up` and "Public" to `crowd`.
- [x] Given a `replay` row, then it isn't used for training.
- [x] Given stub data, then the classifier trains and writes `shot_classifier.joblib`.
- [ ] Human: on dev matches the better method is kept, and macro-F1 is recorded in the sprint notes.

## Out of scope for this slice
Hand labelling.

## Human review required?
No.
