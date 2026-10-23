# Slice 10 — Progress page

**Owner:** Dev B · **Sprint:** 02 · **Target week:** 4 · **Depends on:** 05, 06

## Module
`frontend`

## What to build
`/jobs/[id]` while a job is queued or running:
- polls `GET /api/jobs/{id}` every 2 s;
- shows all 9 stages with friendly names ("Reading video", "Finding the score", "Scanning video", "Reading the score", "Recognising camera shots", "Analysing crowd audio", "Finding deliveries", "Picking highlights", "Rendering reel"), each marked done, current or pending;
- shows an overall progress bar and the elapsed time;
- stops polling when the job is `done` (shows a results placeholder until slice 24) or `failed` (shows the error message and a link back to upload);
- reopening the URL later shows the current state.

## Acceptance criteria
- [ ] Given a running job, then the page updates stage and progress at least every 2 s without reloading.
- [ ] Given stage `scan`, then earlier stages show as done, `scan` as current, later ones as pending.
- [ ] Given the job finishes, then polling stops and the done state is shown.
- [ ] Given the job fails, then the error message and a "Back to upload" link are shown.
- [ ] Given the page is closed and reopened, then it shows the job's current state.
- [ ] Given the API is unreachable, then the page shows "Reconnecting…" and recovers when the API returns.

## Mockup / reference
```
Processing match_final.mp4                      12:41 elapsed
[██████████████░░░░░░░░░░░░] 48%

 ✓ Reading video
 ✓ Finding the score
 ● Scanning video          ← current
 ○ Reading the score
 ○ Recognising camera shots
 ○ ...
```

## Out of scope for this slice
The results view (slice 24).

## Human review required?
No.
