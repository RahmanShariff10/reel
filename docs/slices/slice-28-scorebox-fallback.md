# Slice 28 — Manual score-box fallback

**Owner:** Dev A · **Sprint:** 07 · **Target week:** 12–13 · **Depends on:** 08, 22, 24

## Module
`api` + `frontend`

## What to build
- **API:** `POST /api/jobs/{id}/scorebox {x, y, w, h}` (source pixels). It:
  - checks the box lies inside the frame;
  - writes `scorebox.json` with `source: "manual"` and confidence 1.0;
  - deletes outputs from `scan` onwards (keeping `ingest` outputs);
  - re-queues the job.
- **Frontend:** when `scorebox.found` is false, the results page notice gets a "Mark the score box" button. It opens `scorebox_preview.jpg`; the user drags a rectangle (mapped from display to source pixels), confirms, and is sent to the progress page.

## Acceptance criteria
- [ ] Given a box outside the frame, then the API returns 400.
- [ ] Given a valid box, then `scorebox.json` is manual, outputs from `scan` onwards are removed, `meta.json`/`audio.wav` are kept, and the job is `queued`.
- [ ] Given the image is displayed at a different size than the source, then the submitted coordinates are correctly scaled to source pixels.
- [ ] Given the job finishes after a manual box, then score events and typed highlights appear.
- [ ] Given `scorebox.found: true`, then the button is not shown.

## Mockup / reference
```
Score box not found — highlights were picked from crowd audio and replays only.
[ Mark the score box ]

 ┌──────────────── preview frame ────────────────┐
 │                                               │
 │   ┌──────────────┐  ← user drags a rectangle  │
 │   │ IND 145/3 16.2│                           │
 │   └──────────────┘                            │
 └───────────────────────────────────────────────┘
                              [Cancel] [Re-process]
```

## Out of scope for this slice
Correcting a wrongly detected box when one was found.

## Human review required?
No.
