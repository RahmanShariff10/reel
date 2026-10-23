# Slice 31 — Past matches

**Owner:** Dev B · **Sprint:** 07 · **Target week:** 13–14 · **Depends on:** 23

## Module
`frontend`

## What to build
A `/matches` page listing jobs from `GET /api/jobs`, newest first: filename, date, video duration, status, and number of events (for done jobs). Each row links to `/jobs/{id}`. There's a header link "Past matches" and an empty state that links to upload.

## Acceptance criteria
- [ ] Given three jobs, then they're listed newest first with all columns.
- [ ] Given a click on a row, then the job page opens (progress or results, depending on status).
- [ ] Given no jobs, then the empty state with an upload link is shown.
- [ ] Given a running job, then its status shows as running.

## Out of scope for this slice
Deleting jobs (data deletion needs human review and is not in the PRD).

## Human review required?
No.
