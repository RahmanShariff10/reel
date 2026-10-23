# Slice 21 — Render reel

**Owner:** Dev B · **Sprint:** 04 · **Target week:** 8–9 · **Depends on:** 20

## Module
`render`

## What to build
The `render` stage for a given mode:
- **Title card:** `title.png` generated with Pillow. It shows team names (if known, otherwise "Match highlights"), each innings' score from the summary, and the reel mode. It is turned into a 3 s clip with silent audio, encoded exactly like the other clips.
- **Joining:** the title clip plus the event clips in plan order, joined with the ffmpeg concat demuxer (stream copy) into `reel_<mode>.mp4` with `+faststart`, so browsers can start playing before the whole file loads.
- **Atomic write:** write to a temp file, then rename, so a re-render never leaves a broken reel.

## Acceptance criteria
- [ ] Given a plan, then the reel contains the title followed by the clips in plan order, and its duration is within ±0.5 s of the planned total.
- [ ] Given the output, then it is H.264 `yuv420p` + AAC with the moov atom at the start (verified with ffprobe).
- [ ] Given known team names, then the title card shows them; otherwise it shows "Match highlights".
- [ ] Given a re-render of an existing mode, then the old file is replaced only when the new one is complete.
- [ ] Human check: rendering a 5-minute reel on a laptop takes ≤ 3 min; record it in the sprint 04 notes.

## Out of scope for this slice
Vertical export (slice 33). Music, transitions other than fades.

## Human review required?
No.
