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
| 3 | [37 football-fixtures](slices/slice-37-football-fixtures.md) (see fix B) | tests | 36 | No | `[ ]` |
| 4 | [38 real-match-check](slices/slice-38-real-match-check.md), **script and synthetic tests only** | eval | 35, 37 | Script no; running it yes (G1) | `[ ]` |
| 5 | [50 football-metrics](slices/slice-50-football-metrics.md) (see fix C) | eval | 35, 36 | No | `[ ]` |
| 6 | [42 football-shots](slices/slice-42-football-shots.md) | shots | 36 | Final check only | `[ ]` |
| 7 | [05 api-core](slices/slice-05-api-core.md) | api | done slices only | No | `[ ]` |
| 8 | [06 frontend-scaffold](slices/slice-06-frontend-scaffold.md) | frontend | 05 | No | `[ ]` |
| 9 | [10 progress-page](slices/slice-10-progress-page.md) | frontend | 05, 06 | No | `[ ]` |

Slice 36 needs agreement from both developers before it is merged.

### Gate G1: real-footage go/no-go (human)
Passed when the person with approved access has:
- downloaded 5–8 games and run `python -m eval.check_assumptions` on 3–5 of them;
- reviewed `eval/reports/assumptions.md` and made the go/no-go call on the clock, replay and audio assumptions;
- updated `docs/ARCHITECTURE.md` and the affected slices for any assumption that failed;
- filled in `eval/manifests/matches.yaml` with English-commentary games.

Check on 30 November: if access still hasn't arrived, email soccernet.dataset@gmail.com and re-plan.

## Phase 2: after footage
Don't start until G1 has passed.

| Step | Slice | Module | Depends on | Real footage? | Status |
|---|---|---|---|---|---|
| 10 | [39 clock-scorebox-locate](slices/slice-39-clock-scorebox-locate.md) (see fix B) | scoreboard | 36, 37, G1 | Final check only | `[ ]` |
| 11 | [40 score-clock-read](slices/slice-40-score-clock-read.md) (see fix D) | scoreboard | 39 | Final check only | `[ ]` |
| 12 | [41 goal-state](slices/slice-41-goal-state.md) | scoreboard | 40 | No | `[ ]` |
| 13 | [43 excitement-football](slices/slice-43-excitement-football.md) | audio | G1 | Final check only | `[ ]` |
| 14 | [44 moments](slices/slice-44-moments.md) | moments | 41, 42, 43 | No | `[ ]` |
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
- Slice 28 adds `source: "auto" | "manual"` to `Scorebox`, since the model doesn't have it.

**E. Slice 49 also removes** the names and keys kept under fix A, the cricket `make_synthetic.py` and `test_synthetic_fixtures.py`, and the `reel.deliveries` entry in `test_config.py` (replace it with `reel.moments`). Update the fixture path in `docs/ARCHITECTURE.md`. `eval/` is already clean by then.

**F. Small corrections.** Slice 29's criterion should say about 7,200 values for a two-hour match, not 12,600. Slice 28's mockup shows a cricket score; use `ARS 1-0 CHE  34:12`.
