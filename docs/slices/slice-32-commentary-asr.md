# Slice 32 — Commentary keywords (stretch)

**Owner:** Dev A · **Sprint:** 08 · **Target week:** 14 · **Depends on:** 22

## Module
`audio`

## What to build
An optional commentary signal, `signals.commentary` (default false):
- **Transcription:** faster-whisper (`base.en` or `small.en`, int8, CPU) transcribes only the windows [`t_hit − 5 s`, `t_hit + 15 s`] of candidate deliveries (all events plus the top-N most exciting deliveries).
- **Keywords:** keyword matching (list in config, e.g. "six", "four", "gone", "bowled", "caught", "what a shot", "maximum") gives a commentary score. The result is saved to `commentary.json`.
- **Rating:** when enabled, the rating adds a bonus (config) and a reason such as `commentary: "what a shot"`.

## Acceptance criteria
- [ ] Given `signals.commentary: false`, then nothing is transcribed and outputs are unchanged.
- [ ] Given a short test audio clip containing "that's a huge six", then the keyword "six" is detected.
- [ ] Given enabled, then only candidate windows are transcribed (never the full audio).
- [ ] Given enabled, then affected events have a commentary reason.
- [ ] Human check: on a full real match, the stage takes ≤ 10 min.

## Out of scope for this slice
Full-match transcripts, non-English commentary.

## Human review required?
No.
