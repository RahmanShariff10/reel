# Slice 20 — Render clips

**Owner:** Dev B · **Sprint:** 04 · **Target week:** 7–8 · **Depends on:** 02, 03

## Module
`render`

## What to build
Given a `ReelPlan` and the input video, render each clip to `clips/<event_id>.mp4`:
- **Cutting:** frame-accurate seeking with re-encoding to 1280×720 (1080p is scaled down) H.264 `yuv420p` (CRF and preset in config) with AAC 128 kbps. The fps and audio format are kept uniform across clips so they can be joined without re-encoding.
- **Caption:** drawn bottom-left on a semi-transparent bar, using a bundled open-licence font (e.g. Inter, OFL) in `backend/assets/fonts/`.
- **Fades:** 0.3 s fade in and out on video and audio.
- **No audio:** if the source has no audio, add a silent track.

Can be built before slice 19 using a hand-written plan.

## Acceptance criteria
- [ ] Given a plan clip, then the output duration is within ±0.1 s of the planned duration.
- [ ] Given a clip, then its first full-brightness frame matches the source frame at the planned start (SSIM ≥ 0.9, after the fade-in).
- [ ] Given a caption, then OCR on the caption region reads the planned text.
- [ ] Given a 1080p source, then the output is 1280×720 H.264 `yuv420p` with AAC audio.
- [ ] Given the fades, then the first and last frames are darker than the middle frame.
- [ ] Given a source without audio, then the clip still has a (silent) audio track.

## Out of scope for this slice
Title card and joining clips (slice 21).

## Human review required?
No.
