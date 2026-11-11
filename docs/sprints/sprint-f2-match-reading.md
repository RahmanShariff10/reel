# Sprint F2 — Reading the match

**Dates:** 23 November–6 December 2026 · **Weeks:** 3–4

## Goal
For a real match, the pipeline finds the score graphic, reads goals and halves, labels camera shots, and produces excitement that isn't fooled by constant crowd noise.

## Slices in this sprint
- [x] `slice-39-clock-scorebox-locate` (Dev A)
- [x] `slice-40-score-clock-read` (Dev A)
- [x] `slice-41-goal-state` (Dev A)
- [ ] `slice-42-football-shots` (Dev B)
- [ ] `slice-43-excitement-football` (Dev B)

## Human tasks
- [ ] Dev A: run stages 1–4 on the dev matches; record detection results, OCR calls and time per stage here.
- [ ] Dev B: train the shot classifier from camera labels on an approved laptop; record macro-F1 here.

## Depends on
Sprint F1.

## Results

### Slice 39: score graphic located on the dev matches (10 November)
`locate_scorebox` with default config (80 sampled frames) on each half of the 3 dev games already downloaded. Each half is a separate 45-minute file. The sample reading was checked against SoccerNet's labels: the score against the goals labelled before that moment, and the clock against the labelled game time. Second-half clocks show 45:00 onwards while SoccerNet restarts at 0, so they read 2,700 s "ahead"; that is expected.

| Half | Found | Confidence | Clock presence | Linearity | Score matches labels | Clock matches labels | Time |
|---|---|---|---|---|---|---|---|
| AC Milan v Empoli, 1st | yes | 0.975 | 98% | 100% | yes (0-0) | yes | 37 s |
| AC Milan v Empoli, 2nd | yes | 0.988 | 99% | 100% | yes (1-1) | yes (+1 s) | 40 s |
| Elche v Real Madrid, 1st | yes | 0.988 | 99% | 100% | yes (0-0) | yes | 43 s |
| Elche v Real Madrid, 2nd | yes | 0.938 | 94% | 100% | yes (0-1) | yes | 39 s |
| Marseille v PSG, 1st | yes | 0.800 | 80% | 100% | yes (1-1) | yes | 37 s |
| Marseille v PSG, 2nd | yes | 0.837 | 89% | 94% | yes (2-3) | yes | 38 s |

- Layouts differ: Elche v Real Madrid shows the clock left of the score; the others show it on the right.
- Marseille v PSG's first half was missed at first. Its font makes OCR read 0-0 as `OO`, `0 O`, a single `O` or nothing, so a readable score sat beside the clock in under 40% of samples. Fixed by reading the letter-O forms and requiring a score in only 20% of the clock's samples.
- Preview images with the box (green) and clock box (orange) are in `data/soccernet/locate-check/` on the approved laptop, for a human to look at. They weren't viewed by any AI tool.

### Slice 40: score and clock read on the dev matches (11 November)
Stages 1–4 (up to `read_score`) on three 45-minute halves, each about 5,400 crops at 2 per second. Readings were checked against SoccerNet's labels: the score most often read 1–3 minutes after each labelled goal, every readable score away from goals, and the clock against the labelled game time.

| Half | OCR calls | `read_score` time | Visible | Readable score when visible | Wrong score | Goals right | Clock within 5 s |
|---|---|---|---|---|---|---|---|
| AC Milan v Empoli, 1st | 402 (7% of crops) | 41 s | 99% | 98% | 0.4% | 1 of 1 | 99% |
| AC Milan v Empoli, 2nd | 390 (7%) | 35 s | 99% | 99% | 1.2% | 1 of 1 | 97% |
| Marseille v PSG, 1st | 1,232 (23%) | 160 s | 81% | 97% | 3.7% | 3 of 3 | 99% |

Other stages on one half: ingest 2 s, `locate_scorebox` 43 s, scan 61 s.

The first version needed 1,747–3,592 OCR calls and 13–25 minutes per half, with only 27% of Milan's first-half readings readable. Three causes, all fixed:
- RapidOCR's default detector enlarges a 30 px crop about 24 times. That took ~0.4 s per call and misread zeros. Enlarging the crop 3 times with the detector's longest side capped read 173 of 180 sampled crops right, none wrong, at ~0.09 s. The default is now the fallback for unreadable crops.
- Compression flicker around small text counted as a change. Crops are now blurred and the pixel threshold is 60 (was 40); the padding border, which shows live video, is ignored.
- Items on one line were grouped by pixel row, so a 1 px offset put `OEMP` before `MIL` and read 0-1. Lines are now grouped by vertical overlap.

Marseille's graphic is see-through, so its crops keep changing and OCR runs at the 2-second cap. The longest run of one misread score was 19 crops (9.5 s), such as `7-0` for `1-0`; slice 41 must not accept a score that briefly.

### Slice 41: goals and halves on the dev matches (11 November)
The goal state machine on slice 40's readings: each half alone, and AC Milan v Empoli's halves joined into one match as `eval` prepares it. Goals were matched to SoccerNet's `Goal` labels on the same side within 3 minutes.

| Readings | Goals labelled | Found | Score graphic updated after the label | False goals | Halves found |
|---|---|---|---|---|---|
| AC Milan v Empoli, 1st | 1 | 1 | 4 s | 0 | 1 |
| AC Milan v Empoli, 2nd | 1 | 1 | 5 s | 0 | 1 |
| AC Milan v Empoli, joined | 2 | 2 | 4 s, 5 s | 0 | 2, split at the join |
| Marseille v PSG, 1st | 3 | 3 | 83 s, 62 s, 85 s | 0 | 1 |

Each run took under 0.2 s.

- Every misread that looked like a goal (0-0 read as 0-1 or 1-0, 16 of them) was one OCR result copied to 4–9 readings. "3 consecutive readings" would have accepted them all, so a new score now needs 2 separate OCR results.
- The first version found 4 false halves: it compared each clock reading with the one before, so a misread clock just before the graphic hid made the next reading look like a jump. Readings are now compared with the half's clock line.
- SoccerNet cuts each half at 45:00, so joined halves have no break and a continuous clock. They are split where the clock passes 45:00 and runs on.
- Marseille's graphic updated over a minute after each goal. Slice 44 looks for the goal moment up to `goal_lookback_s` (90 s) before the update, which only just covers 85 s.

## Notes for next time
