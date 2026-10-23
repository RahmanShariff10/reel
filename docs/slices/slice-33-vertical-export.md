# Slice 33 — Vertical export (stretch)

**Owner:** Dev B · **Sprint:** 08 · **Target week:** 14 · **Depends on:** 21, 23

## Module
`render`

## What to build
An optional `aspect: "9:16"` on reel requests:
- clips are centre-cropped and scaled to 720×1280;
- the caption is moved to the bottom centre, sized for vertical video;
- the title card has a vertical layout;
- the output is `reel_<mode>_vertical.mp4`.

`POST /reels` accepts `aspect`, and the results page offers a "Vertical (9:16)" download.

## Acceptance criteria
- [ ] Given `aspect: "9:16"`, then the output is 720×1280 and the duration matches the horizontal reel within ±0.5 s.
- [ ] Given the vertical reel, then the caption is fully inside the frame.
- [ ] Given no `aspect`, then behaviour is unchanged (16:9).
- [ ] Given the results page, then the vertical reel can be requested and downloaded.

## Out of scope for this slice
Ball tracking or smart reframing (centre crop only).

## Human review required?
No.
