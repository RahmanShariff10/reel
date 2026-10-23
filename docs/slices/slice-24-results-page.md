# Slice 24 — Results page

**Owner:** Dev B · **Sprint:** 05 · **Target week:** 10 · **Depends on:** 10, 23

## Module
`frontend`

## What to build
`/jobs/[id]` when the job is `done`:
- **Reel player:** HTML5 video showing the 5-minute reel.
- **Length switcher:** 3 / 5 / 10 min / All. Choosing one requests that reel, shows "Rendering…", and swaps the video in when it's done, without reloading the page.
- **Event list:** type badge, over.ball, score, importance, and reason chips.
  - Clicking an event that is in the reel seeks the reel to it.
  - Clicking an event that isn't in the reel switches the player to the full match at that moment.
- **Summary cards:** per innings runs/wickets/overs, fours, sixes, deliveries found, processing time.
- **Score box:** the detected score-box preview image, or a notice if it wasn't found ("Highlights were picked from crowd audio and replays only").
- **Downloads:** reel MP4, `events.json`, and each clip.

## Acceptance criteria
- [ ] Given a finished job, then the 5-minute reel loads and plays.
- [ ] Given an event in the reel, when clicked, then the reel seeks to that clip's start (±0.5 s).
- [ ] Given an event not in the reel, when clicked, then the full match plays from that event's moment.
- [ ] Given a click on "10 min", then "Rendering…" is shown and the new reel replaces the old one when ready, with no page reload.
- [ ] Given the summary, then all listed numbers are shown and match `/result`.
- [ ] Given `scorebox.found: false`, then the notice is shown instead of the preview.
- [ ] Given the downloads section, then reel, events JSON and individual clips download correctly.
- [ ] Given a 768 px wide window, then there's no horizontal scrolling.

## Mockup / reference
```
┌─────────────────────────────────────────┬───────────────────────┐
│                                         │ Summary               │
│            [ reel player ]              │ IND 182/6 (20)        │
│                                         │ AUS 176/9 (20)        │
│  Length: (3) [5] (10) (All)             │ 4s: 24  6s: 13  W: 15 │
├─────────────────────────────────────────┤ 241 deliveries · 34m  │
│ Events                                  ├───────────────────────┤
│ [W]  4.3  IND 31/2   0.97  score W ·…   │ Score box found       │
│ [6]  6.1  IND 52/2   0.91  score +6 ·…  │ [preview image]       │
│ [4]  9.4  IND 78/3   0.74  score +4     ├───────────────────────┤
│ ...                                     │ Downloads             │
└─────────────────────────────────────────┴───────────────────────┘
```

## Out of scope for this slice
Excitement chart (slice 29), removing clips (slice 30), past matches page (slice 31).

## Human review required?
No.
