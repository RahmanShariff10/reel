# Slice 08 — Score-box detection

**Owner:** Dev A · **Sprint:** 02 · **Target week:** 3–4 · **Depends on:** 03, 07

## Module
`scoreboard`

## What to build
The `locate_scorebox` stage, as specified in ARCHITECTURE.md "Score-box detection":
1. **Sample frames:** seek to N frames (config, default 80) spread evenly across the match, skipping the first and last 5 minutes. For videos shorter than 15 minutes, skip the first and last 5% instead.
2. **Read text:** run full-frame RapidOCR (detection + recognition) on each sampled frame.
3. **Filter:** keep text matching score patterns (`\d{1,3}[/-]\d{1,2}`) and overs patterns (`\d{1,2}\.\d`).
4. **Group by position:** cluster candidates by position and merge an adjacent score region and overs region into one box.
5. **Validate:** a box needs presence in ≥ 40% of samples and plausible ordering in ≥ 90% of consecutive readings (thresholds in config).
6. **Choose:** pick the box with the most valid readings, and infer the runs/wickets order (the faster-growing number is runs).
7. **Write output:** `scorebox.json` (box padded by a small margin, confidence, number order, sample reading) or `found: false`, plus `scorebox_preview.jpg` (a sample frame, with the box drawn if found). The preview is always saved.

A missing score box must never fail the job.

## Acceptance criteria
- [ ] Given the synthetic video, then the box is found with IoU ≥ 0.7 against the true rectangle and the sample reading matches the schedule at that time.
- [ ] Given the `--order wickets-runs` video, then the stored order is `wickets-runs`.
- [ ] Given the `--distractor` video, then the static number graphic is not chosen.
- [ ] Given the `--no-scorebox` video, then `found: false`, `scorebox_preview.jpg` still exists, and the job continues.
- [ ] Given a config change to the thresholds, then behaviour follows the config with no code change.
- [ ] Human check: on every collected real match, the box is found and the preview is correct; runtime on a full match is ≤ 3 min. Record results in the sprint 02 notes.

## Out of scope for this slice
Reading the score through the match (slice 11). Manual box fallback (slice 28).

## Human review required?
No.
