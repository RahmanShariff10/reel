# Build order — read this before starting any slice

For coding agents and developers. This file says what is left, what order to do it in, and what needs real footage. **Where it disagrees with a slice doc or `docs/sprints/README.md`, this file wins.** Dates stay as in the sprint plan: web-app MVP 10 January 2027, final delivery 14 February 2027.

Read in this order: `CLAUDE.md`, this file, the slice doc, then the relevant parts of `docs/ARCHITECTURE.md`.

## What is left
50 slices in total: 12 done and still in use, 10 cricket slices replaced, **28 to do**.

- **Done, don't redo:** 01, 02, 03, 04, 07, 09, 14, 15, 16, 20, 21, 22. Some are adapted by later slices.
- **Replaced, don't build:** 08, 11, 12, 13, 17, 18, 19, 25, 27, 32.
- **To do:** the 28 slices in the tables below.

The code on `main` is still the cricket pipeline. The specs are football. The last cricket version is commit `a71b5bc`.

## How to pick and do a slice
1. Do **one slice per session**. If told "next", take the first row below with status `[ ]` whose dependencies are `[x]`.
2. Stop at a **gate** (G1 to G4). Gates are human decisions. Don't pass one on your own.
3. Start from the latest `main`: `git switch main && git pull --ff-only && git switch -c slice-NN-short-name`. If a dependency isn't merged yet, stop and tell the human.
4. Treat the slice's acceptance criteria as the test plan. Skip the `Human:` criteria and report them as still open.
5. Run the tests: `cd backend && uv run pytest -q ../backend/tests ../eval/tests` (about 11 minutes; on a fresh clone run `uv sync --extra dev` first), then `uv run ruff check .`.
6. Update the slice's status in this file in the same branch: `[x]` if finished, `[~]` if only a real-match check is left.
7. Commit with the slice ID (`slice-36-football-models: add Moment model`) and no AI attribution, then push the branch.
8. **Don't open or merge PRs. The humans do that.** This overrides "open a PR" in `CLAUDE.md`.

Stop and ask if something is ambiguous, if a slice needs a change outside its scope, or if a test can only pass by weakening it.

## Footage rules
SoccerNet videos are under an NDA that is personal to each approved Hugging Face account ([ADR-006](decisions/ADR-006-soccernet-eval-and-footage-rules.md)).

- Footage lives only at `data/soccernet/videos-720p/` on the laptop of the person whose account was approved.
- **If that folder is missing or empty, footage isn't available on this machine.** Finish what doesn't need it and tell the human. Never substitute footage from YouTube or anywhere else.
- Never ask for, print or copy a Hugging Face token.
- Never put videos, frames, crops or generated reels in git, PRs, Colab, shared drives or reports.
- **Never open SoccerNet video or images derived from it with your own tools** (keyframes, score crops, previews, clips). That sends protected footage to an external AI service. Work from numbers, logs and JSON that contain no images.
- Tests only ever use synthetic video.
- SoccerNet **labels** are public and fine to use: `SoccerNet/SN-Labels` on Hugging Face.

## Phase 1: before footage
All of this can be done now, in this order.

| Step | Slice | Module | Depends on | Real footage? | Status |
|---|---|---|---|---|---|
| 1 | [35 soccernet-loader](slices/slice-35-soccernet-loader.md) | eval | — | No | `[x]` |
| 2 | [36 football-models](slices/slice-36-football-models.md) (see fix A) | common | — | No | `[x]` |
| 3 | [37 football-fixtures](slices/slice-37-football-fixtures.md) (see fix B) | tests | 36 | No | `[x]` |
| 4 | [38 real-match-check](slices/slice-38-real-match-check.md) | eval | 35, 37 | Yes, run at G1 | `[x]` |
| 5 | [50 football-metrics](slices/slice-50-football-metrics.md) (see fix C) | eval | 35, 36 | No | `[x]` |
| 6 | [42 football-shots](slices/slice-42-football-shots.md) | shots | 36 | Final check only | `[~]` |
| 7 | [05 api-core](slices/slice-05-api-core.md) | api | done slices only | No | `[x]` |
| 8 | [06 frontend-scaffold](slices/slice-06-frontend-scaffold.md) | frontend | 05 | No | `[x]` |
| 9 | [10 progress-page](slices/slice-10-progress-page.md) | frontend | 05, 06 | No | `[x]` |

Slice 36 needs agreement from both developers before it is merged.

### Gate G1: real-footage go/no-go (human)
**Status: passed on 10 November.**

- [x] Downloaded games and labels, and ran `python -m eval.check_assumptions` on 5 matches from 5 competitions (`eval/manifests/assumption_games.yaml`). Results are in [eval/reports/assumptions.md](../eval/reports/assumptions.md).
- [x] Go/no-go call on each assumption:
  - **A1 clock holds.** Found on 5 of 5 matches, on screen 94–98% of the time and ticking correctly 96–100%.
  - **A2 replays fails, so replays are dropped for the MVP** ([ADR-007](decisions/ADR-007-no-replay-signal.md)). The score graphic stays on during replays: hidden in 2% of replay shots and 3% of live shots. Moments now come from goals and crowd audio only.
  - **A3 audio holds for goals but is weak for other moments.** 11 of 14 goals had a peak within ±15 s (chance level 28%), but only 22 of 52 shots on target did, and peak rates ranged from 0.22 to 0.96 per minute between broadcasts. The check used the current excitement code. Slice 43's rolling crowd baseline should help, and slice 43 must re-measure this on the dev games.
- [x] Updated `docs/ARCHITECTURE.md`, `docs/PRD.md` and slices 24, 26, 28, 43, 44 and 46 for A2 and A3.
- [x] Replaced `eval/manifests/matches.yaml` with 15 real English-commentary games: 5 dev games from SoccerNet's `train` split and 10 test games from its `test` split. Don't run the test games until config is frozen at G4.

## Phase 2: after footage
Don't start until G1 has passed.

| Step | Slice | Module | Depends on | Real footage? | Status |
|---|---|---|---|---|---|
| 10 | [39 clock-scorebox-locate](slices/slice-39-clock-scorebox-locate.md) (see fix B) | scoreboard | 36, 37, G1 | Final check only | `[x]` |
| 11 | [40 score-clock-read](slices/slice-40-score-clock-read.md) (see fixes D and H) | scoreboard | 39 | Final check only | `[x]` |
| 12 | [41 goal-state](slices/slice-41-goal-state.md) (see fix H) | scoreboard | 40 | No | `[x]` |
| 13 | [43 excitement-football](slices/slice-43-excitement-football.md) | audio | G1 | Final check only | `[ ]` |
| 14 | [44 moments](slices/slice-44-moments.md) (see fix I) | moments | 41, 42, 43 | No | `[ ]` |
| 15 | [45 commentary](slices/slice-45-commentary.md) | audio | 44 | Final check only | `[ ]` |
| 16 | [46 football-rating](slices/slice-46-football-rating.md) | highlights | 44, 45 | No | `[ ]` |
| 17 | [47 football-clips-selection](slices/slice-47-football-clips-selection.md) | highlights | 46 | No | `[ ]` |
| 18 | [48 football-render](slices/slice-48-football-render.md) | render | 44, 47 | No | `[ ]` |
| 19 | [49 football-wiring](slices/slice-49-football-wiring.md) (see fix E) | jobs | 39–48, 50 | Final check only | `[ ]` |

"Final check only" means the code and automated tests need no footage, but one `Human:` criterion must be run on a real match by the person with access. Mark those `[~]` until it's done.

**If footage is badly delayed:** steps 10–18 can be built on synthetic video, but only if a human says "build ahead without footage". Say in the commit message that it isn't verified on real footage. These slices may need rework if an assumption fails: 39–41 depend on the clock, 43–44 on crowd audio and replays.

### Gate G2: real reel from the command line (human)
Passed when one real match runs through `reel run`, the reel has been watched on the approved laptop, the timings are in the sprint notes, and every `[~]` above is resolved. Target: 20 December.

## Phase 3: web-app MVP

| Step | Slice | Module | Depends on | Real footage? | Status |
|---|---|---|---|---|---|
| 20 | [23 result-api](slices/slice-23-result-api.md) | api | 05, 49 | No | `[ ]` |
| 21 | [24 results-page](slices/slice-24-results-page.md) | frontend | 10, 23 | No | `[ ]` |

### Gate G3: MVP (human)
Passed when a real match goes through the web app. **Demo footage must be settled by 3 January:** written SoccerNet permission, or a match the team has the rights to show. Target: 10 January.

## Phase 4: evaluation tools and should-haves

| Step | Slice | Module | Depends on | Real footage? | Status |
|---|---|---|---|---|---|
| 22 | [26 eval-ablation](slices/slice-26-eval-ablation.md) | eval | 49, 50 | No (running it does) | `[ ]` |
| 23 | [28 scorebox-fallback](slices/slice-28-scorebox-fallback.md) (see fix D) | api + frontend | 39, 49, 24 | No | `[ ]` |
| 24 | [29 excitement-chart](slices/slice-29-excitement-chart.md) (see fix F) | frontend | 23, 24 | No | `[ ]` |
| 25 | [30 edit-reel](slices/slice-30-edit-reel.md) | frontend | 23, 24 | No | `[ ]` |
| 26 | [31 past-matches](slices/slice-31-past-matches.md) | frontend | 23 | No | `[ ]` |

### Gate G4: final evaluation (human)
Passed when config is tuned on the 5 development matches only, frozen, and then run on the 10 test matches with the report reviewed. Target: 31 January. Viewer survey only with permitted footage.

## Phase 5: delivery

| Step | Slice | Module | Depends on | Real footage? | Status |
|---|---|---|---|---|---|
| 27 | [34 setup-docs](slices/slice-34-setup-docs.md) | docs | all core slices | No | `[ ]` |
| 28 | [33 vertical-export](slices/slice-33-vertical-export.md) *(stretch, only if nothing has slipped)* | render | 48, 23 | No | `[ ]` |

Slice 34 touches `.env.example`, so it needs human review.

## Fixes to the slice docs
These correct problems found by checking the slices against the code. They override the slice docs.

**A. Slice 36: keep cricket names importable until slice 49.** `reel/jobs/__init__.py` imports the pipeline, which imports the cricket modules at load time. If `Delivery`, `InningsSummary` or `DeliveriesConfig` disappear, every `reel.jobs` import fails, including the job store that slice 05 needs.
- Keep those three names, `JobPaths.deliveries_json`, and the existing cricket config keys, marked as deprecated. Add the football fields and models as specified.
- `python -c "import reel.jobs"` must still work.
- `test_jobs`, `test_ingest`, `test_paths`, `test_config`, `test_scan`, `test_render_clips` and `test_audio_excitement` must still pass.
- Other tests that break may be skipped with a `reason` naming the slice that replaces them. Eval tests name slice 50, shot tests name slice 42.

**B. Slice 37: add a new generator; don't rewrite the old one.** About ten test files rely on the cricket `make_synthetic.py`.
- Build the football generator in `tests/fixtures/make_football.py`, with tests in `test_football_fixtures.py`.
- Slice 39 points the shared `synthetic_match` and `scanned_match` fixtures in `conftest.py` at the football generator and keeps `test_scan` passing.
- Whichever slice replaces some code also rewrites or re-enables its skipped tests. No skips may remain after slice 49.

**C. Slice 50: moved earlier, and now removes the cricket eval code.** It only needs slices 35 and 36. Slice 49 can't otherwise meet its "no cricket left, no skipped tests" criteria.
- As well as replacing `e1.py` and `metrics.py` and updating `report.py`, delete `eval/cricsheet.py`, `eval/annotations.py`, `eval/matches.example.yaml`, `eval/tests/test_eval_foundation.py`, `eval/tests/test_eval_metrics.py` and `eval/tests/fixtures/sample_t20.json`.
- Add new tests for the slice's acceptance criteria.

**D. Manual score box (slices 28 and 40).** A manually drawn box has no `clock_box`.
- Slice 40 must accept `clock_box: null`: compare the whole crop, and leave `clock_s` null when the clock can't be read.
- Slice 40 must not OCR a crop of only the clock. On the synthetic video, RapidOCR on a tightly padded clock crop split the digits (`45:03` came back as `45:0` and `3`). Read the clock from the whole score box or a generously padded crop, and test this with real OCR.
- Slice 28 adds `source: "auto" | "manual"` to `Scorebox`, since the model doesn't have it.

**E. Slice 49 also removes** the names and keys kept under fix A, the cricket `make_synthetic.py` and `test_synthetic_fixtures.py`, and the `reel.deliveries` entry in `test_config.py` (replace it with `reel.moments`). Update the fixture path in `docs/ARCHITECTURE.md`. `eval/` is already clean by then. It also removes the replay leftovers ([ADR-007](decisions/ADR-007-no-replay-signal.md)): `"replay"` in `MomentSource`, `Moment.replay_count`, `signals.replays`, the `moments.replay_*` and `highlights.bonus.replay_*` config keys, and any tests that use them.

**F. Small corrections.** Slice 29's criterion should say about 7,200 values for a two-hour match, not 12,600. Slice 28's mockup shows a cricket score; use `ARS 1-0 CHE  34:12`.

**G. Slice 45: give faster-whisper audio samples, not a file path.** With PyAV 19, faster-whisper 1.2 crashes when given a path (`open() got an unexpected keyword argument 'metadata_errors'`). Load the 16 kHz mono WAV with `soundfile` and pass the array, as `WhisperLanguageDetector` in `eval/check_assumptions.py` does.

**H. Slices 40 and 41: real OCR is imperfect.** On Marseille v PSG, OCR read the 0-0 graphic as `OO PARIS SG`, `0 O PARIS SG`, `O PARIS SG` or just `PARIS SG` (see the F2 sprint notes).
- Slice 40 (done): scores are parsed with `find_goals`, which handles the letter-O forms. A visible reading with no readable score has `home`/`away` null.
- Slice 41 must skip unreadable readings rather than treat them as a change.
- Slice 41 (done): a reading is copied to every following crop until the crop changes, so one OCR call can fill many readings, and misreads occur in 0.4–3.7% of readable readings. A new score needs 2 separate OCR results (or 45 s with a frozen clock), not 3 consecutive readings: every goal-like misread on the dev matches was one OCR result.

**I. Slice 44: the score graphic can update over a minute after a goal.** On Marseille v PSG it updated 62–85 s after the labelled goal; `goal_lookback_s` (90 s) only just covers that. Check the lag on the other dev matches, and widen the look-back if needed, before tuning anything else.
