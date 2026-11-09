# Build plan — Reel (football)

14 weeks · 2 developers (**Dev A**, **Dev B**) · 6 sprints. Starts Monday 9 November 2026.

**Final delivery: Sunday 14 February 2027.** Web-app MVP: Sunday 10 January 2027.

The cricket sprints are in [`archive-cricket/`](archive-cricket/). Code at that point is git tag `cricket-final`.

## Ownership
| | Dev A — match understanding + plumbing | Dev B — media + product |
|---|---|---|
| Modules | `common`, `jobs`, `ingest`, `scoreboard`, `moments`, `highlights`, `eval` | `shots`, `audio`, `render`, `api`, `frontend`, test fixtures |

## Timeline
| Sprint | Dates | Weeks | Milestone at the end |
|---|---|---|---|
| [F1. Pivot foundations](sprint-f1-pivot-foundations.md) | 9–22 Nov | 1–2 | Models and fixtures are football; real-match assumptions checked |
| [F2. Reading the match](sprint-f2-match-reading.md) | 23 Nov–6 Dec | 3–4 | Goals, halves, shot labels and excitement produced for a real match |
| [F3. Highlights](sprint-f3-highlights.md) | 7–20 Dec | 5–6 | **A real match becomes a reel through the CLI; cricket code is gone** |
| [F4. Web-app MVP](sprint-f4-mvp.md) | 21 Dec–10 Jan | 7–9 | **A real match becomes a reel through the web app** |
| [F5. Evaluation and should-haves](sprint-f5-evaluation.md) | 11–31 Jan | 10–12 | Final numbers on 10 test matches; should-haves done |
| [F6. Delivery](sprint-f6-delivery.md) | 1–14 Feb | 13–14 | Report, slides, demo; this sprint is also the schedule buffer |

F4 is three weeks because it spans the holidays.

## Rules
- The MVP is the priority. If time runs short, cut should-haves and stretch, never the core.
- A slice is one coding-agent session. Non-coding work is listed as **human tasks** in each sprint.
- Commits and PRs reference the slice ID, e.g. `slice-39-clock-scorebox-locate: add linearity check`.
- No match footage in git, ever. Tests use synthetic videos only. SoccerNet rules are in [ADR-006](../decisions/ADR-006-soccernet-eval-and-footage-rules.md).
- **Schedule check:** if SoccerNet access hasn't arrived by 30 November, email soccernet.dataset@gmail.com and re-plan F2.

## Status of every slice
Slices marked *done* were built for cricket and are unaffected or adapted by a later slice. *Replaced* slices are kept for history.

| # | Slice | Module | Owner | Sprint | Week | Status |
|---|---|---|---|---|---|---|
| 01 | [backend-scaffold](../slices/slice-01-backend-scaffold.md) | common | A | — | — | done |
| 02 | [common-models](../slices/slice-02-common-models.md) | common | A | — | — | done, extended by 36 |
| 03 | [synthetic-fixtures](../slices/slice-03-synthetic-fixtures.md) | tests | B | — | — | done, replaced by 37 |
| 04 | [job-store-worker](../slices/slice-04-job-store-worker.md) | jobs | A | — | — | done |
| 07 | [ingest](../slices/slice-07-ingest.md) | ingest | A | — | — | done |
| 08 | [scorebox-locate](../slices/slice-08-scorebox-locate.md) | scoreboard | A | — | — | replaced by 39 |
| 09 | [scan-pass](../slices/slice-09-scan-pass.md) | ingest | B | — | — | done |
| 11 | [score-read](../slices/slice-11-score-read.md) | scoreboard | A | — | — | replaced by 40 |
| 12 | [match-state](../slices/slice-12-match-state.md) | scoreboard | A | — | — | replaced by 41 |
| 13 | [eval-foundation](../slices/slice-13-eval-foundation.md) | eval | A | — | — | replaced by 35, 50 |
| 14 | [shot-clip-zeroshot](../slices/slice-14-shot-clip-zeroshot.md) | shots | B | — | — | done, adapted by 42 |
| 15 | [shot-classifier](../slices/slice-15-shot-classifier.md) | shots | B | — | — | done, adapted by 42 |
| 16 | [audio-excitement](../slices/slice-16-audio-excitement.md) | audio | B | — | — | done, adapted by 43 |
| 17 | [deliveries](../slices/slice-17-deliveries.md) | deliveries | A | — | — | replaced by 44 |
| 18 | [highlight-rating](../slices/slice-18-highlight-rating.md) | highlights | A | — | — | replaced by 46 |
| 19 | [clip-selection](../slices/slice-19-clip-selection.md) | highlights | A | — | — | replaced by 47 |
| 20 | [render-clips](../slices/slice-20-render-clips.md) | render | B | — | — | done |
| 21 | [render-reel](../slices/slice-21-render-reel.md) | render | B | — | — | done, adapted by 48 |
| 22 | [pipeline-wiring](../slices/slice-22-pipeline-wiring.md) | jobs | A | — | — | done, adapted by 49 |
| 25 | [eval-metrics](../slices/slice-25-eval-metrics.md) | eval | A | — | — | replaced by 50 |
| 27 | [near-miss](../slices/slice-27-near-miss.md) | highlights | A | — | — | replaced by 46 |
| 32 | [commentary-asr](../slices/slice-32-commentary-asr.md) | audio | A | — | — | replaced by 45 |
| 35 | [soccernet-loader](../slices/slice-35-soccernet-loader.md) | eval | A | F1 | 1 | todo |
| 36 | [football-models](../slices/slice-36-football-models.md) | common | A (B reviews) | F1 | 1 | todo |
| 37 | [football-fixtures](../slices/slice-37-football-fixtures.md) | tests | B | F1 | 1–2 | todo |
| 38 | [real-match-check](../slices/slice-38-real-match-check.md) | eval | A | F1 | 2 | todo, needs footage |
| 39 | [clock-scorebox-locate](../slices/slice-39-clock-scorebox-locate.md) | scoreboard | A | F2 | 3 | todo |
| 40 | [score-clock-read](../slices/slice-40-score-clock-read.md) | scoreboard | A | F2 | 3–4 | todo |
| 41 | [goal-state](../slices/slice-41-goal-state.md) | scoreboard | A | F2 | 4 | todo |
| 42 | [football-shots](../slices/slice-42-football-shots.md) | shots | B | F2 | 3–4 | todo |
| 43 | [excitement-football](../slices/slice-43-excitement-football.md) | audio | B | F2 | 4 | todo |
| 44 | [moments](../slices/slice-44-moments.md) | moments | A | F3 | 5 | todo |
| 45 | [commentary](../slices/slice-45-commentary.md) | audio | A | F3 | 5–6 | todo |
| 46 | [football-rating](../slices/slice-46-football-rating.md) | highlights | A | F3 | 6 | todo |
| 47 | [football-clips-selection](../slices/slice-47-football-clips-selection.md) | highlights | A | F3 | 6 | todo |
| 48 | [football-render](../slices/slice-48-football-render.md) | render | B | F3 | 6 | todo |
| 49 | [football-wiring](../slices/slice-49-football-wiring.md) | jobs | A | F3 | 6 | todo |
| 05 | [api-core](../slices/slice-05-api-core.md) | api | B | F4 | 7 | todo |
| 06 | [frontend-scaffold](../slices/slice-06-frontend-scaffold.md) | frontend | B | F4 | 7 | todo |
| 10 | [progress-page](../slices/slice-10-progress-page.md) | frontend | B | F4 | 7–8 | todo |
| 23 | [result-api](../slices/slice-23-result-api.md) | api | B | F4 | 8 | todo |
| 24 | [results-page](../slices/slice-24-results-page.md) | frontend | B | F4 | 8–9 | todo |
| 50 | [football-metrics](../slices/slice-50-football-metrics.md) | eval | A | F5 | 10–11 | todo |
| 26 | [eval-ablation](../slices/slice-26-eval-ablation.md) | eval | B | F5 | 11–12 | todo |
| 28 | [scorebox-fallback](../slices/slice-28-scorebox-fallback.md) | api + frontend | A | F5 | 11 | todo |
| 29 | [excitement-chart](../slices/slice-29-excitement-chart.md) | frontend | B | F5 | 12 | todo |
| 30 | [edit-reel](../slices/slice-30-edit-reel.md) | frontend | B | F5 | 12 | todo |
| 31 | [past-matches](../slices/slice-31-past-matches.md) | frontend | B | F5 | 12 | todo |
| 34 | [setup-docs](../slices/slice-34-setup-docs.md) | docs | A + B | F6 | 13–14 | todo |
| 33 | [vertical-export](../slices/slice-33-vertical-export.md) *(stretch)* | render | B | F6 | 13 | todo |
