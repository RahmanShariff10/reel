# Slice 34 — Setup docs and demo script

**Owner:** Dev A + Dev B · **Sprint:** 08 · **Target week:** 14–15 · **Depends on:** all core slices

## Module
Docs (`README.md`, `docs/demo.md`)

## What to build
- **README "Getting started":** exact, tested commands to install dependencies, download the models once, start the API, the worker and the frontend, and process a match. Plus a short troubleshooting section (ffmpeg missing, model download, port in use).
- **`.env.example`:** checked against the variables the code actually reads.
- **`docs/demo.md`:** the demo script, covering which match to show, the pre-processed job, the live short-segment run, and the talking points for each screen.

## Acceptance criteria
- [ ] Given a fresh clone on the other dev's laptop, when following the README exactly, then the app runs and processes the synthetic video with no extra steps.
- [ ] Given `.env.example`, then every variable the code reads is listed, and no listed variable is unused.
- [ ] Given `docs/demo.md`, then a person who didn't build the app can run the demo from it.

## Out of scope for this slice
Docker, CI or deployment (only if explicitly requested later).

## Human review required?
Yes: it touches `.env.example` (environment variables).
