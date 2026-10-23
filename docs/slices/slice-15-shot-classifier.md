# Slice 15 — Shot classifier and labelling tool

**Owner:** Dev B · **Sprint:** 03 · **Target week:** 6–7 · **Depends on:** 14

## Module
`shots`

## What to build
- **Labelling tool** `uv run python -m reel.shots.label --job <job_id>`: an OpenCV window shows each keyframe. Keys `1`–`5` set the class, `s` skips, `u` undoes, `q` quits. Labels are saved to `eval/labels/shots_<match_id>.csv` (job id, shot id, label; no images), and the tool resumes where it left off.
- **Training script** `uv run python -m reel.shots.train`:
  - trains logistic regression on CLIP embeddings of all labelled shots (fixed seed);
  - saves it to `{REEL_MODELS_DIR}/shot_classifier.joblib`;
  - writes a report with per-class precision / recall and a confusion matrix, using leave-one-match-out validation, for both the classifier and zero-shot.
- **Pipeline:** `classify_shots` uses the classifier when the model file exists (`label_source: "classifier"`), otherwise zero-shot.

## Acceptance criteria
- [ ] Given the labelling tool, then keys 1–5 / s / u / q behave as described, and reopening resumes at the first unlabelled shot.
- [ ] Given ≥ 500 labels, when training, then the model file and the report (classifier vs zero-shot) are written.
- [ ] Given the same labels and seed, then training produces identical predictions.
- [ ] Given the model file exists, then `shots.json` uses `label_source: "classifier"`; without it, `"zero_shot"`.
- [ ] Target (reported, not a test): `run_up` precision ≥ 0.95 and recall ≥ 0.90 on a held-out match.

## Out of scope for this slice
Fine-tuning CLIP itself. Using the FPV dataset unless its licence allows it.

## Human review required?
No.
