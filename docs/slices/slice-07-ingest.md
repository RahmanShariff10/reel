# Slice 07 — Ingest

**Owner:** Dev A · **Sprint:** 02 · **Target week:** 3 · **Depends on:** 02, 03, 04

## Module
`ingest`

## What to build
The real `ingest` stage (replacing its placeholder):
- runs ffprobe on the job's input and writes `meta.json` (duration, fps, width, height, video/audio codecs, `has_audio`);
- extracts audio to `audio.wav` as 32 kHz mono 16-bit PCM;
- for `local_path` jobs, reads the file in place and never copies it.

## Acceptance criteria
- [ ] Given the synthetic video, when the stage runs, then `meta.json` has duration within 0.1 s of the schedule, width 1280, height 720 and `has_audio: true`.
- [ ] Given the synthetic video, then `audio.wav` is 32 000 Hz, mono, with duration within 0.1 s of the video.
- [ ] Given a video with no audio (`--no-audio`), then `has_audio` is false, no `audio.wav` is written, and the stage succeeds.
- [ ] Given a file that is not a valid video, then the job fails with the message "Not a valid video file".
- [ ] Given a `local_path` job, then no copy of the input is created in the job folder.
- [ ] Given valid existing outputs, when the pipeline re-runs, then the stage is skipped.

## Out of scope for this slice
Frame extraction and the full scan (slice 09).

## Human review required?
No.
