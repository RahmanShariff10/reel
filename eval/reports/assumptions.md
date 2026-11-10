# Real-match assumption check

5 match(es). Numbers only: no frames or broadcast text.

## Recommendation

- **A1 clock:** Holds: clock found on 5 of 5 matches.
- **A2 replays:** Does not hold: box hidden in 2% of replay shots and 3% of live shots. Change replay detection in slice 44, for example to transition detection.
- **A3 audio:** Does not hold: 79% of goals have a peak nearby (chance level 28%). Tune or change excitement in slice 43.

## A1: clock

| Match | Found | Presence | Linearity | Frames read |
|---|---|---|---|---|
| 2015-02-21 - 18-00 Chelsea 1 - 1 Burnley | yes | 95% | 96% | 80 |
| 2014-11-04 - 22-45 Dortmund 4 - 1 Galatasaray | yes | 94% | 97% | 80 |
| 2015-04-11 - 16-30 Bayern Munich 3 - 0 Eintracht Frankfurt | yes | 98% | 96% | 80 |
| 2015-02-15 - 14-30 AC Milan 1 - 1 Empoli | yes | 98% | 100% | 80 |
| 2015-02-22 - 23-00 Elche 0 - 2 Real Madrid | yes | 98% | 100% | 80 |

## A2: score graphic during replays

| Match | Hidden in replay shots | Hidden in live shots | Replay shots | Live shots |
|---|---|---|---|---|
| 2015-02-21 - 18-00 Chelsea 1 - 1 Burnley | 5% | 8% | 40 | 40 |
| 2014-11-04 - 22-45 Dortmund 4 - 1 Galatasaray | 2% | 0% | 40 | 39 |
| 2015-04-11 - 16-30 Bayern Munich 3 - 0 Eintracht Frankfurt | 0% | 0% | 40 | 40 |
| 2015-02-15 - 14-30 AC Milan 1 - 1 Empoli | 2% | 3% | 40 | 39 |
| 2015-02-22 - 23-00 Elche 0 - 2 Real Madrid | 0% | 5% | 40 | 40 |

## A3: excitement peaks within ±15 s

| Match | Goals with peak | Shots on target with peak | Peaks per minute | Chance level |
|---|---|---|---|---|
| 2015-02-21 - 18-00 Chelsea 1 - 1 Burnley | 2/2 (100%) | 2/8 (25%) | 0.22 | 12% |
| 2014-11-04 - 22-45 Dortmund 4 - 1 Galatasaray | 4/5 (80%) | 7/9 (78%) | 0.86 | 44% |
| 2015-04-11 - 16-30 Bayern Munich 3 - 0 Eintracht Frankfurt | 3/3 (100%) | 11/15 (73%) | 0.96 | 49% |
| 2015-02-15 - 14-30 AC Milan 1 - 1 Empoli | 1/2 (50%) | 1/12 (8%) | 0.30 | 15% |
| 2015-02-22 - 23-00 Elche 0 - 2 Real Madrid | 1/2 (50%) | 1/8 (12%) | 0.38 | 20% |

## Commentary language

| Match | Language |
|---|---|
| 2015-02-21 - 18-00 Chelsea 1 - 1 Burnley | es |
| 2014-11-04 - 22-45 Dortmund 4 - 1 Galatasaray | de |
| 2015-04-11 - 16-30 Bayern Munich 3 - 0 Eintracht Frankfurt | de |
| 2015-02-15 - 14-30 AC Milan 1 - 1 Empoli | en |
| 2015-02-22 - 23-00 Elche 0 - 2 Real Madrid | en |
