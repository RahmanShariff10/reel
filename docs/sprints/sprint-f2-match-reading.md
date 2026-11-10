# Sprint F2 — Reading the match

**Dates:** 23 November–6 December 2026 · **Weeks:** 3–4

## Goal
For a real match, the pipeline finds the score graphic, reads goals and halves, labels camera shots, and produces excitement that isn't fooled by constant crowd noise.

## Slices in this sprint
- [x] `slice-39-clock-scorebox-locate` (Dev A)
- [ ] `slice-40-score-clock-read` (Dev A)
- [ ] `slice-41-goal-state` (Dev A)
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

## Notes for next time
