# Slice 24 — Results page

**Owner:** Dev B · **Sprint:** F4 · **Target week:** 8–9 · **Depends on:** 10, 23

## Module
`frontend`

## What to build
`/jobs/[id]` when the job is `done`:
- **Reel player:** HTML5 video showing the 5-minute reel.
- **Length switcher:** 3 / 5 / 10 min / All. Choosing one requests that reel, shows "Rendering…", and swaps the video in when it's done, without reloading the page.
- **Event list:** type badge, match minute, score, importance, and reason chips.
  - Clicking an event that is in the reel seeks the reel to it.
  - Clicking an event that isn't in the reel switches the player to the full match at that moment.
- **Summary cards:** final score, goals per half, moments found, processing time.
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
│            [ reel player ]              │ ARS 2-1 CHE           │
│                                         │ HT 1-0                │
│  Length: (3) [5] (10) (All)             │ Goals: 3              │
├─────────────────────────────────────────┤ 41 moments · 22m      │
│ Events                                  ├───────────────────────┤
│ [G]  12'  ARS 1-0    0.97  score +1 ·…  │ Score box found       │
│ [C]  31'  ARS 1-0    0.78  what a save… │ [preview image]       │
│ [G]  67'  ARS 2-1    0.96  score +1     ├───────────────────────┤
│ ...                                     │ Downloads             │
└─────────────────────────────────────────┴───────────────────────┘
```

## Out of scope for this slice
Excitement chart (slice 29), removing clips (slice 30), past matches page (slice 31).

## Human review required?
No.
