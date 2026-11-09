# Slice 29 — Excitement chart

**Owner:** Dev B · **Sprint:** F5 · **Target week:** 12 · **Depends on:** 23, 24

## Module
`frontend`

## What to build
On the results page, a Recharts area chart of excitement over match time from `GET /excitement`:
- downsampled to ≤ 2,000 points for performance;
- event markers coloured by type (goal, penalty, red card, chance, yellow card, moment);
- a vertical line at half-time;
- tooltips showing time, match minute and score for markers;
- clicking anywhere switches the player to the full match at that time.

## Acceptance criteria
- [ ] Given a full match (~12,600 values), then the chart renders with ≤ 2,000 points and stays responsive.
- [ ] Given events, then each has a marker in its type's colour, with a legend.
- [ ] Given a half-time break in the summary, then a vertical line marks it.
- [ ] Given a click at time t, then the full match plays from t (±1 s).
- [ ] Given hovering a marker, then a tooltip shows match minute and score.

## Out of scope for this slice
Zooming and panning.

## Human review required?
No.
