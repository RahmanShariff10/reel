# Slice 16 — Crowd excitement from audio

**Owner:** Dev B · **Sprint:** 03 · **Target week:** 6–7 · **Depends on:** 07

## Module
`audio`

## What to build
The `audio` stage writes `excitement.csv`, one row per second, with columns `t, loudness_db, loudness_z, p_cheer, p_applause, p_crowd, excitement`:
- **Loudness:** RMS loudness in dB per second (librosa), and a z-score against a rolling 5-minute median / MAD.
- **Crowd sounds:** PANNs CNN14 (`panns_inference`) on 2 s windows with a 1 s hop. Take the probabilities of the AudioSet classes Cheering, Applause and Crowd, looked up by name, never by hard-coded index.
- **Excitement:** a weighted combination (weights in config) scaled to [0, 1].
- **Bounded memory:** process audio in batches.
- **No audio:** if `has_audio` is false, write all-zero rows.
- **Switch:** PANNs can be turned off in config (loudness only).

## Acceptance criteria
- [ ] Given the synthetic video with PANNs off, then excitement has a local maximum within ±1 s of every scheduled burst, and the median excitement outside bursts is < 0.3.
- [ ] Given the PANNs label list, then class indices are resolved by name (a test fails if a name is missing).
- [ ] Given a video of duration d, then the CSV has ceil(d) rows.
- [ ] Given `has_audio: false`, then all values are 0 and the stage succeeds.
- [ ] Given a stub PANNs model in tests, then the combined excitement follows the configured weights.
- [ ] Human check: on a full real match, the stage takes ≤ 5 min; record it in the sprint 03 notes.

## Out of scope for this slice
Commentary speech-to-text (slice 32).

## Human review required?
No.
