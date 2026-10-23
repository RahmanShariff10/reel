# Slice 09 — Full scan pass

**Owner:** Dev B · **Sprint:** 02 · **Target week:** 3–4 · **Depends on:** 02, 03, 07, 08

## Module
`ingest` (camera-cut detection code lives in `shots`)

## What to build
The `scan` stage. It is the **only full decode** of the video: one ffmpeg process with two outputs.
- **(a) Low-resolution frames** at 4 fps (config), piped into Python:
  - camera-cut detection with a PySceneDetect detector fed frame by frame → shot boundaries in `shots.json`;
  - one keyframe per shot (the middle frame, ~448 px wide JPEG) in `keyframes/`.
- **(b) Full-resolution crops of the score box** at 2 fps (config) in `score_crops/`, with filenames encoding the timestamp in milliseconds. Skipped if `scorebox.json` says `found: false`.

Memory must stay bounded: stream frames, never hold the video in memory. Report progress during the scan.

## Acceptance criteria
- [ ] Given the synthetic video, then every scheduled cut is detected within ±0.5 s, with precision and recall ≥ 95%.
- [ ] Given the synthetic video, then each shot has exactly one keyframe and it comes from inside that shot.
- [ ] Given a found score box, then the number of crops is duration × 2 (±1), each crop has the box's dimensions, and each filename encodes its timestamp.
- [ ] Given `found: false`, then no crops are produced and the stage succeeds.
- [ ] Given the stage implementation, then it starts exactly one ffmpeg process that reads the full input (verified in a test by inspecting the commands issued).
- [ ] Given a long scan, then job progress updates at least every 30 s.
- [ ] Human check: on a full real match, record scan time and peak memory (target < 1.5 GB) in the sprint 02 notes.

## Out of scope for this slice
Shot type labels (slices 14–15). OCR on crops (slice 11).

## Human review required?
No.
