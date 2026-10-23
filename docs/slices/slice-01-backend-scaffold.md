# Slice 01 — Backend scaffold

**Owner:** Dev A · **Sprint:** 01 · **Target week:** 1 · **Depends on:** —

## Module
`common`

## What to build
Create `backend/` as a Python 3.11 project managed by `uv`, with the package `reel` and empty subpackages for every module in ARCHITECTURE.md (`common`, `jobs`, `api`, `ingest`, `scoreboard`, `shots`, `audio`, `deliveries`, `highlights`, `render`).

Add `backend/config/default.yaml` with one section per module (values can be placeholders) plus `signals.{score,shots,audio,replays}: true`. Add a config loader `reel.common.config.load_config(path=None, overrides=None)` that returns a typed Pydantic settings object. `REEL_DATA_DIR` and `REEL_MODELS_DIR` env vars override the data and model paths. Set up logging (`reel.common.logging`), pytest and ruff.

## Acceptance criteria
- [ ] Given a fresh clone, when running `uv sync` then `uv run pytest` in `backend/`, then all tests pass.
- [ ] Given no arguments, when `load_config()` is called, then it returns the values from `default.yaml`.
- [ ] Given `REEL_DATA_DIR=/tmp/x`, when `load_config()` is called, then `data_dir` is `/tmp/x`.
- [ ] Given `overrides={"signals": {"audio": False}}`, when `load_config(overrides=...)` is called, then `signals.audio` is false and every other value is unchanged (deep merge).
- [ ] Given an invalid value (e.g. a negative frame rate), when loading, then a validation error names the offending field.
- [ ] Given the package, when importing every `reel.<module>` subpackage, then all imports succeed.
- [ ] `uv run ruff check .` passes.

## Out of scope for this slice
Data models (slice 02), database, FastAPI app, any pipeline logic.

## Human review required?
No.
