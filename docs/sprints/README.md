# Build plan — Reel

15 weeks · 2 developers (**Dev A**, **Dev B**) · 8 sprints · 34 slices.

## Ownership
| | Dev A — match understanding + plumbing | Dev B — media + product |
|---|---|---|
| Modules | `common`, `jobs`, `ingest`, `scoreboard`, `deliveries`, `highlights`, `eval` | `shots`, `audio`, `render`, `api`, `frontend`, test fixtures |
| Human tasks | Replay-signal check, timestamp annotations, config tuning | Keyframe labelling (~500), viewer survey |

`common` (shared data models) is agreed by both in sprint 1. After that, each dev builds against saved stage files and the API contract, not against the other's unfinished code.

## Timeline
| Sprint | Weeks | Milestone at the end |
|---|---|---|
| [1. Foundations](sprint-01-foundations.md) | 1–2 | A file uploaded in the UI creates a job; the worker runs placeholder stages; progress updates |
| [2. Ingest and score box](sprint-02-ingest-scorebox.md) | 3–4 | Score box found automatically on a real match; full scan time measured |
| [3. Signals](sprint-03-signals.md) | 5–7 | Score events, shot labels and crowd excitement produced for a real match |
| [4. Deliveries and highlights](sprint-04-deliveries-highlights.md) | 7–9 | A reel can be rendered from saved stage files |
| [5. End-to-end MVP](sprint-05-mvp.md) | 9–10 | **A real match becomes a reel through the web app** |
| [6. Evaluation](sprint-06-evaluation.md) | 11–12 | First full set of evaluation numbers |
| [7. Should-haves](sprint-07-should-haves.md) | 12–14 | All should-haves done; final evaluation run |
| [8. Stretch and delivery](sprint-08-delivery.md) | 14–15 | Report, slides, demo match processed in advance |

Sprints 3/4 and 6/7 overlap by a week on purpose: the two devs finish at slightly different times.

## Rules
- The MVP (end of week 10) is the priority. If time runs short, cut should-haves and stretch, never the core.
- A slice is one coding-agent session. Non-coding work is listed as **human tasks** in each sprint.
- Commits and PRs reference the slice ID, e.g. `slice-08-scorebox-locate: add position clustering`.
- No match footage in git, ever. Tests use synthetic videos only (slice 03).

## All slices
| # | Slice | Module | Owner | Week |
|---|---|---|---|---|
| 01 | [backend-scaffold](../slices/slice-01-backend-scaffold.md) | common | A | 1 |
| 02 | [common-models](../slices/slice-02-common-models.md) | common | A (B reviews) | 1–2 |
| 03 | [synthetic-fixtures](../slices/slice-03-synthetic-fixtures.md) | tests | B | 1–2 |
| 04 | [job-store-worker](../slices/slice-04-job-store-worker.md) | jobs | A | 2 |
| 05 | [api-core](../slices/slice-05-api-core.md) | api | B | 2 |
| 06 | [frontend-scaffold](../slices/slice-06-frontend-scaffold.md) | frontend | B | 2 |
| 07 | [ingest](../slices/slice-07-ingest.md) | ingest | A | 3 |
| 08 | [scorebox-locate](../slices/slice-08-scorebox-locate.md) | scoreboard | A | 3–4 |
| 09 | [scan-pass](../slices/slice-09-scan-pass.md) | ingest | B | 3–4 |
| 10 | [progress-page](../slices/slice-10-progress-page.md) | frontend | B | 4 |
| 11 | [score-read](../slices/slice-11-score-read.md) | scoreboard | A | 5 |
| 12 | [match-state](../slices/slice-12-match-state.md) | scoreboard | A | 5–6 |
| 13 | [eval-foundation](../slices/slice-13-eval-foundation.md) | eval | A | 6–7 |
| 14 | [shot-clip-zeroshot](../slices/slice-14-shot-clip-zeroshot.md) | shots | B | 5 |
| 15 | [shot-classifier](../slices/slice-15-shot-classifier.md) | shots | B | 6–7 |
| 16 | [audio-excitement](../slices/slice-16-audio-excitement.md) | audio | B | 6–7 |
| 17 | [deliveries](../slices/slice-17-deliveries.md) | deliveries | A | 7–8 |
| 18 | [highlight-rating](../slices/slice-18-highlight-rating.md) | highlights | A | 8 |
| 19 | [clip-selection](../slices/slice-19-clip-selection.md) | highlights | A | 8–9 |
| 20 | [render-clips](../slices/slice-20-render-clips.md) | render | B | 7–8 |
| 21 | [render-reel](../slices/slice-21-render-reel.md) | render | B | 8–9 |
| 22 | [pipeline-wiring](../slices/slice-22-pipeline-wiring.md) | jobs | A | 9–10 |
| 23 | [result-api](../slices/slice-23-result-api.md) | api | B | 9–10 |
| 24 | [results-page](../slices/slice-24-results-page.md) | frontend | B | 10 |
| 25 | [eval-metrics](../slices/slice-25-eval-metrics.md) | eval | A | 11–12 |
| 26 | [eval-ablation](../slices/slice-26-eval-ablation.md) | eval | B | 11–12 |
| 27 | [near-miss](../slices/slice-27-near-miss.md) | highlights | A | 12–13 |
| 28 | [scorebox-fallback](../slices/slice-28-scorebox-fallback.md) | api + frontend | A | 12–13 |
| 29 | [excitement-chart](../slices/slice-29-excitement-chart.md) | frontend | B | 12–13 |
| 30 | [edit-reel](../slices/slice-30-edit-reel.md) | frontend | B | 13 |
| 31 | [past-matches](../slices/slice-31-past-matches.md) | frontend | B | 13–14 |
| 32 | [commentary-asr](../slices/slice-32-commentary-asr.md) *(stretch)* | audio | A | 14 |
| 33 | [vertical-export](../slices/slice-33-vertical-export.md) *(stretch)* | render | B | 14 |
| 34 | [setup-docs](../slices/slice-34-setup-docs.md) | docs | A + B | 14–15 |
