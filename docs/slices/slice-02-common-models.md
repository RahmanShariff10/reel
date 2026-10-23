# Slice 02 — Common data models

**Owner:** Dev A (Dev B reviews and approves) · **Sprint:** 01 · **Target week:** 1–2 · **Depends on:** 01

## Module
`common`

## What to build
Pydantic models in `reel.common.models` for every stage file listed in ARCHITECTURE.md "Job directory":
- `Meta`, `Scorebox`, `Shot`, `ScoreReading`, `ScoreEvent`, `Delivery`, `Event`, `Reason`, `ReelPlan` (mode, clips with event id / start / end / caption / offset, total duration), `Summary`.
- Read/write helpers for `excitement.csv`.

Also add:
- `JobPaths(job_id)` in `reel.common.paths`, with one property per stage file and folder, rooted at `{data_dir}/jobs/{job_id}/`.
- `write_model(path, model)`: writes to a temp file in the same folder, then renames.
- `read_model(path, Model)` and `is_valid(path, Model)` (exists and parses).

Field names must match the API contract and data model in ARCHITECTURE.md exactly. These models are the contract between Dev A and Dev B.

## Acceptance criteria
- [ ] Given ARCHITECTURE.md's job directory list, when checking `JobPaths`, then every listed file and folder has a property with exactly that name.
- [ ] Given any model instance, when written with `write_model` and read back with `read_model`, then the result equals the original.
- [ ] Given a write that raises mid-way, when it fails, then no partial file exists at the target path.
- [ ] Given a file with invalid content, when `is_valid` is called, then it returns false (no exception).
- [ ] Given an `Event`, when serialised to JSON, then its keys match the `Event` shape in ARCHITECTURE.md (including `type` values `wicket`/`six`/`four`/`near_miss`/`moment`).
- [ ] Given `excitement.csv` helpers, when writing and reading a series, then values round-trip with one row per second.
- [ ] Dev B has reviewed the models and approved them (record in the PR).

## Out of scope for this slice
Any logic that produces these files. Database tables (slice 04).

## Human review required?
No, but Dev B must approve the PR because both devs depend on these models.
