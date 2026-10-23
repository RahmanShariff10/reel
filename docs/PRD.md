# PRD — Reel: Automatic Cricket Highlight Generator

## Goal
Given a full T20 cricket match video, Reel automatically produces a captioned highlight reel (every wicket and boundary, or the best N minutes) and an explained list of key events. It runs locally on a laptop CPU, with no manual editing. This replaces the 45–60+ minutes of manual scrubbing and trimming it takes to make highlights today, and the proprietary tools that only large broadcasters can afford.

## Users
- **Primary: the digital/social team at a small rights-holder, state T20 league or regional streaming platform.** They have the full broadcast file but no editor free to cut highlights quickly. Today they either edit by hand in a video editor (slow, often skipped) or don't publish highlights at all.
- **Secondary: independent cricket content creators** making recap videos, and **fans** who missed a match and want the key moments.
- **What we expect from the user:** only that they can pick a video file. No settings to fill in, no video-editing skills, no AI/ML knowledge. The app must not ask the user anything technical.

## Main user flow
Upload and wait. Nothing else is required.
1. **Upload a match:** pick a video file, or point to a file already on the machine.
2. **Wait while it processes:** a progress screen shows the current stage and percent complete. Everything happens automatically, including finding where the score is shown on screen.
3. **Review results:** watch the reel (5 minutes by default), browse the events, check match stats, download outputs. Optionally switch the reel to 3 or 10 minutes, or "all wickets and boundaries".

## Core features (v1 must-haves)
- **Add a match video:** upload a full T20 broadcast (mp4 or mkv, 720p or 1080p, up to ~4 hours), or choose a file already on disk instead of uploading.
- **Automatic score detection:** the app finds the on-screen score box (e.g. `IND 145/3  16.2 ov`) by itself, with no input from the user, and reads it throughout the match. The results page shows where the score box was found and a sample reading, so the user can see it worked.
- **Reel length:** a 5-minute reel by default. On the results page the user can switch to 3 or 10 minutes, or "all wickets and boundaries", and the reel is re-cut without analysing the match again.
- **Processing progress:** see the current stage (e.g. finding the score, finding deliveries, analysing audio, rendering) with percent complete. The page can be left and reopened without losing the job.
- **Watch the highlight reel:**
  - clips in match order with smooth transitions;
  - each clip captioned with event, over.ball and score, e.g. `SIX · 16.2 ov · IND 151/3`;
  - a title card with the teams and the result or final scores.
- **Browse key events:**
  - a list of every detected event with its type (wicket / six / four), over.ball, score, confidence, and the reasons it was picked (e.g. "score +6, crowd excitement high, 2 replays");
  - clicking an event jumps to that moment.
- **Match summary:** fours, sixes and wickets per innings, the number of deliveries found, and processing time.
- **Download outputs:** the reel (mp4), the event list (JSON), and individual clips.
- **Results are kept:** processed matches stay on disk and can be reopened later from their link.

## Should-have (after v1 core works)
- **Near-miss moments:** balls with no score change but high crowd excitement and replays (dropped catches, big appeals, edges past the stumps) included as a lower-priority event type.
- **Edit the reel:** remove clips from the result and re-render.
- **Excitement chart:** excitement over the whole match, with markers for wickets and boundaries; clicking it jumps to that moment.
- **Past matches list:** a page listing processed matches.
- **DRS reversals:** a wicket overturned on review is detected and left out of the reel.
- **Score-box fallback:** if the score box can't be found automatically, the results page says so (the reel is still made from audio and video only), and the user can draw a box around the score once and re-run.

## Stretch (only if time allows)
- **Commentary speech-to-text:** commentary keywords ("six!", "gone!", "what a catch") from short transcripts around candidate moments, used as an extra excitement signal.
- **Batter milestones:** 50s and 100s detected and included.
- **Vertical 9:16 export** for Shorts/Reels.
- **Player reel:** highlights for one chosen batter or bowler.

## Out of scope
- **Live streams.** Reel processes a finished match file only; there are no real-time or near-live highlights.
- **Other formats and sports.** ODIs, Tests, The Hundred and non-cricket sports are not supported or tested. Broadcasts without an on-screen score graphic fall back to a lower-accuracy mode with no guarantees.
- **Accounts, sharing and cloud.** Single user, local machine only: no login, no deployment, no publishing to YouTube or social media.
- **Ball and player tracking.** No ball trajectories, player identification or analytics. The "player reel" stretch would use on-screen text only.
- **Professional editing.** No timeline editor, music, voice-over or custom graphics beyond the fixed caption and title-card style.

## Success criteria
Accuracy targets are measured on 2–3 held-out test matches (T20, English commentary) and reported in the final evaluation. They are targets to aim for, not guarantees.

**Product**
- A first-time user goes from upload to a finished reel with no input beyond choosing the file.
- A full T20 match (~3.5 h, 720p) is processed in **≤ 60 minutes** on a laptop CPU.
- The reel fits the chosen length within ±15 seconds, or contains every detected wicket and boundary in "all" mode.

**Accuracy (compared with Cricsheet ball-by-ball data and our timestamp annotations)**
- The score box is found automatically on **every** test match, and on at least **3 of 5** sample clips from other broadcasters.
- **≥ 90%** of boundaries and wickets are found, with **≥ 90%** of detected events being real.
- **≥ 85%** of reel clips contain the actual moment (delivery through outcome), not cut short or mistimed.
- **≥ 90%** of deliveries bowled are found as deliveries.
- Clear overlap between the balls in our reel and those in the broadcaster's official highlights for the same match. The overlap is reported as a percentage; there is no fixed threshold.
- In a viewer survey (10–15 people), our reel is rated clearly higher than a reel of randomly picked clips of the same length.
- An ablation (removing one signal at a time) shows each signal's contribution: audio only → + camera shots → + score reading.

## Open questions
None open. The questions raised here (score-box detection, clip-length rules, OCR engine, shot classifier, uploads, replay signal) are settled in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

**Exit check:** Could someone else read this and know exactly what to build and what NOT to build, without asking you a follow-up question?
