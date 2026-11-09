# ADR-006 — SoccerNet for evaluation, with hard limits on footage

## Context
The team has no football footage. Cricsheet no longer applies. SoccerNet offers full broadcasts with timestamped labels, but [its videos are under an NDA](https://huggingface.co/datasets/SoccerNet/SoccerNet_raw_HQ).

## Decision
Use SoccerNet-v2 labels as ground truth and SoccerNet 720p videos for development and evaluation: 5 development matches from `train`, 10 test matches from `test`, English commentary only.

## Rules (from the dataset terms; the signed NDA takes precedence)
- Access is personal. **Each developer who handles footage files their own request.** Tokens, videos, frames and clips are never shared between people.
- Videos, frames, clips and job outputs stay on the approved person's laptop, in gitignored folders. No Colab, cloud storage or shared drives.
- Reels made from SoccerNet are derivative footage: **no publishing, public screening or sharing them**, including in the report, slides or a viewer survey.
- Metrics and aggregate numbers may be published. Cite the SoccerNet papers.
- Figures in the report use synthetic frames or footage we have rights to.

## Why
- Public labels are aligned to the video, which removes hand annotation and allows 10 test matches instead of 2–3.
- Six competitions give real broadcaster variety.

## Consequences
- The demo and viewer survey need separate footage, or written permission from SoccerNet (soccernet.dataset@gmail.com).
- Training the camera-shot classifier can use `Labels-cameras.json` instead of ~500 hand-labelled keyframes, on the approved laptop only.
- Approval time is outside our control, so slices that need no footage come first.
