# PRD — Reel: Automatic Football Highlight Generator

> Reel was first specified for T20 cricket. It was re-scoped to football in November 2026; the cricket version is preserved at git tag `cricket-final`.

## Goal
Given a full football match broadcast, Reel automatically produces a captioned highlight reel (every goal plus the best chances, or the best N minutes) and an explained list of key events. It runs locally on a laptop CPU, with no manual editing. This replaces the manual scrubbing and trimming it takes to make highlights today, and the proprietary tools that only large broadcasters can afford.

## Users
- **Primary: the digital/social team at a small club, regional league or streaming platform.** They have the full broadcast file but no editor free to cut highlights quickly. Today they either edit by hand (slow, often skipped) or don't publish highlights at all.
- **Secondary: independent football content creators** making recap videos, and **fans** who missed a match and want the key moments.
- **What we expect from the user:** only that they can pick a video file. No settings to fill in, no video-editing skills, no AI/ML knowledge. The app must not ask the user anything technical.

## Main user flow
Upload and wait. Nothing else is required.
1. **Upload a match:** pick a video file, or point to a file already on the machine.
2. **Wait while it processes:** a progress screen shows the current stage and percent complete. Everything happens automatically, including finding where the score and clock are shown on screen.
3. **Review results:** watch the reel (5 minutes by default), browse the events, check the match summary, download outputs. Optionally switch the reel to 3 or 10 minutes, or "all goals and key moments".

## Core features (v1 must-haves)
- **Add a match video:** upload one full-match broadcast file (mp4 or mkv, 720p or 1080p, up to ~3 hours), or choose a file already on disk instead of uploading.
- **Automatic score and clock detection:** the app finds the on-screen score graphic (e.g. `ARS 1-0 CHE  34:12`) by itself, with no input from the user, and reads it throughout the match. The results page shows where it was found and a sample reading.
- **Reel length:** a 5-minute reel by default. On the results page the user can switch to 3 or 10 minutes, or "all goals and key moments", and the reel is re-cut without analysing the match again.
- **Processing progress:** see the current stage with percent complete. The page can be left and reopened without losing the job.
- **Watch the highlight reel:**
  - clips in match order with smooth transitions;
  - each clip captioned with event, match minute and score, e.g. `GOAL · 67' · ARS 2-1 CHE`;
  - a title card with the teams and the final score.
- **Browse key events:**
  - a list of every detected event with its type (goal / penalty / red card / chance / yellow card / moment), match minute, score, confidence, and the reasons it was picked (e.g. "score +1, crowd excitement high, commentary: what a goal");
  - clicking an event jumps to that moment.
- **Match summary:** final score, goals per half, the number of moments found, and processing time.
- **Download outputs:** the reel (mp4), the event list (JSON), and individual clips.
- **Results are kept:** processed matches stay on disk and can be reopened later from their link.

## Should-have (after v1 core works)
- **Disallowed goals:** a goal removed from the score graphic after review is detected and left out of the reel.
- **Edit the reel:** remove clips from the result and re-render.
- **Excitement chart:** excitement over the whole match, with markers for events; clicking it jumps to that moment.
- **Past matches list:** a page listing processed matches.
- **Score-box fallback:** if the score graphic can't be found automatically, the results page says so (the reel is still made from audio and video only), and the user can draw a box around it once and re-run.

## Stretch (only if time allows)
- **Vertical 9:16 export** for Shorts/Reels.
- **Player reel:** highlights for one chosen player, from on-screen text only.
- **Non-English commentary keywords.**

## Out of scope
- **Live streams.** Finished match files only.
- **Other sports.** Cricket is no longer supported; other sports were never tested.
- **Penalty shoot-outs.** A shoot-out shows no running clock, so it gets no special handling. Extra time is handled as long as the clock keeps running.
- **Accounts, sharing and cloud.** Single user, local machine only: no login, no deployment, no publishing.
- **Ball and player tracking.** No trajectories, player identification or analytics.
- **Professional editing.** No timeline editor, music, voice-over or custom graphics beyond the fixed caption and title-card style.

## Data and rights
- Development and evaluation use **SoccerNet** broadcast videos and labels ([ADR-006](decisions/ADR-006-soccernet-eval-and-footage-rules.md)).
- SoccerNet videos are NDA-protected: each person needs their own approved access, and footage, frames and clips made from it are never shared, published, committed, shown to others or uploaded to cloud notebooks.
- **The public demo and any viewer survey therefore need separate footage or written permission from SoccerNet.** This is a tracked human task in sprint F4.

## Success criteria
Accuracy targets are measured on **10 held-out matches with English commentary** from SoccerNet's test split, against SoccerNet-v2 labels. They are targets to aim for, not guarantees, and are **provisional until the real-match check in slice 38**.

**Product**
- A first-time user goes from upload to a finished reel with no input beyond choosing the file.
- A full match (~2 h, 720p) is processed in **≤ 60 minutes** on a laptop CPU.
- The reel fits the chosen length within ±15 seconds, or contains every detected goal and key moment in "all" mode.

**Accuracy**
- The score graphic is found on **≥ 9 of 10** test matches.
- **≥ 95%** of goals are found, with **≥ 95%** of detected goals being real.
- **≥ 70%** of key actions (penalties, red cards, shots on target) appear among detected events in "all" mode.
- **≥ 85%** of goal clips contain the actual goal, with at least 3 s before and after it.
- **≥ 60%** of clips in the 5-minute reel contain a labelled key action, and this is clearly higher than for a reel of randomly picked clips of the same length.
- An ablation (removing one signal at a time) shows each signal's contribution: audio only, then + camera shots, then + commentary, then + score reading.
- If footage rights allow it: in a viewer survey (10–15 people), our reel is rated clearly higher than a random reel of the same length.

## Timeline
Final delivery **Sunday 14 February 2027**; web-app MVP **Sunday 10 January 2027**. Plan in [`sprints/README.md`](sprints/README.md).

---

**Exit check:** Could someone else read this and know exactly what to build and what NOT to build, without asking you a follow-up question?
