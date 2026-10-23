# Slice 14 — Shot labels with CLIP (zero-shot)

**Owner:** Dev B · **Sprint:** 03 · **Target week:** 5 · **Depends on:** 09

## Module
`shots`

## What to build
The `classify_shots` stage, first version:
- **Model:** load CLIP ViT-B/32 with `open_clip`, cached in `REEL_MODELS_DIR` (downloaded once).
- **Embeddings:** embed every keyframe in batches and cache them to `shot_embeddings.npy`. A re-run reuses the cache.
- **Zero-shot labels:** compare embeddings with text prompts per class from config (`run_up`, `close_up`, `crowd`, `field`, `graphic`). Write `label`, per-class `probs` and `label_source: "zero_shot"` into `shots.json`.

The embedder sits behind an interface so tests can use a stub.

## Acceptance criteria
- [ ] Given a stub embedder, when the stage runs, then every shot in `shots.json` has a label and probabilities that sum to 1 (±0.001).
- [ ] Given an existing valid `shot_embeddings.npy`, when the stage re-runs, then the embedder is not called.
- [ ] Given the model already downloaded, when running with no network, then the stage works.
- [ ] Given prompts changed in config, then labels change with no code change.
- [ ] Human check: on a laptop CPU, throughput ≥ 15 keyframes/s; record it in the sprint 03 notes.

## Out of scope for this slice
The trained classifier and labelling tool (slice 15).

## Human review required?
No.
