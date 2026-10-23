# Slice 30 — Edit reel

**Owner:** Dev B · **Sprint:** 07 · **Target week:** 13 · **Depends on:** 23, 24

## Module
`frontend`

## What to build
An "Edit reel" mode on the results page:
- events in the current reel get a remove/restore toggle;
- a "Re-render" button sends `POST /reels {mode, exclude_event_ids}`, shows "Rendering…", and swaps in the new reel when it's done;
- exclusions are loaded from `GET /reels/{mode}`, so they survive a page reload.

## Acceptance criteria
- [ ] Given edit mode, then each event in the reel has a remove/restore toggle, and removed events are visibly marked.
- [ ] Given two removed events and "Re-render", then the new reel doesn't contain them.
- [ ] Given a page reload, then the removed events are still shown as removed for that mode.
- [ ] Given no changes, then "Re-render" is disabled.

## Out of scope for this slice
Adding events that weren't selected, or reordering clips.

## Human review required?
No.
