# Reel

**Automatic highlight reels from full T20 cricket broadcasts. Upload a match, wait, get the reel.**

![Status](https://img.shields.io/badge/status-in%20development-orange)
![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-frontend-000000?logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![ffmpeg](https://img.shields.io/badge/ffmpeg-video-007808?logo=ffmpeg&logoColor=white)
![CPU only](https://img.shields.io/badge/runs%20on-CPU%20only-lightgrey)
![License](https://img.shields.io/badge/license-MIT-blue)

Reel takes a full T20 match video (~3.5 hours) and produces a captioned highlight reel of the wickets, sixes and fours, plus an explained list of every key event. It runs locally on a laptop CPU, with no manual editing and no cloud services.

> **Status:** design complete, implementation in progress. See [`docs/`](docs/) for the full specification.

## How it works

Cricket is played ball by ball, so Reel analyses the match one delivery at a time:

1. **Find the score box.** Reel locates the on-screen score (e.g. `IND 145/3  16.2 ov`) automatically and reads it throughout the match.
2. **Split the match into deliveries.** Camera cuts are detected, and the bowler run-up shot marks the start of each ball.
3. **Read each ball's outcome.** Score changes give the event: +4 is a four, +6 is a six, +1 wicket is a wicket.
4. **Measure excitement.** Crowd audio (cheering, applause) and the number of replays rate how big each moment was.
5. **Build the reel.** The top moments are cut from run-up to outcome, captioned, and joined into a 3, 5 or 10-minute reel, or one with every wicket and boundary.

Every selected clip comes with its reasons, e.g. *score +6 · crowd excitement high · 2 replays*.

## Features

- Upload a match video, or use a file already on disk
- Score-box detection with no user input
- Live processing progress
- Highlight reel with per-clip captions and a title card
- Event list with over, score, confidence and reasons; click an event to jump to it
- Match summary: fours, sixes and wickets per innings
- Re-cut the reel to a different length without re-analysing the match
- Download the reel (MP4), the events (JSON) and individual clips

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Backend | Python 3.11, FastAPI, Pydantic, SQLite, separate worker process |
| Video and audio | ffmpeg, PySceneDetect, librosa |
| Models (pretrained, CPU) | RapidOCR (PP-OCR), CLIP ViT-B/32 + a small trained classifier, PANNs CNN14 |
| Evaluation | Cricsheet ball-by-ball data, pytest, Google Colab |

## Project structure

```
backend/     FastAPI server, worker and processing pipeline (Python)
frontend/    Web app (Next.js)
eval/        Evaluation scripts, annotations and notebooks
data/        Local videos, job outputs and models (not committed)
docs/        Research, PRD, architecture, decisions, sprints and slices
```

## Getting started

> Setup commands will be added as the first sprints land.

**Prerequisites**
- Python 3.11 and [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- ffmpeg on your `PATH`

## Documentation

| Document | Contents |
|---|---|
| [Research](docs/research.md) | Problem, prior work, what is different here |
| [PRD](docs/PRD.md) | Users, features, scope, success criteria |
| [Architecture](docs/ARCHITECTURE.md) | Stack, pipeline, modules, API contract, data model |
| [Decisions](docs/decisions/) | Records of the non-obvious design choices |
| [Sprints](docs/sprints/) and [slices](docs/slices/) | Build plan and units of work |

## Evaluation

Reel is evaluated on held-out T20 matches against [Cricsheet](https://cricsheet.org) ball-by-ball data and hand-marked timestamps.

| Metric | Target |
|---|---|
| Wickets and boundaries detected | ≥ 90% |
| Reel clips containing the full moment | ≥ 85% |
| Deliveries detected | ≥ 90% |
| Processing time, full T20 on a laptop CPU | ≤ 60 min |

The evaluation also reports agreement with official broadcaster highlights, a viewer study, and an ablation showing how much each signal (audio, camera shots, score reading) contributes.

## Scope

Supported: finished T20 match files with English commentary and an on-screen score box.
Not supported: live streams, other formats or sports, cloud deployment, user accounts.

## Data and copyright

Match footage is copyrighted. Videos and job outputs stay in `data/`, which is excluded from version control, and are never uploaded anywhere. Only our timestamp annotations are committed.

## Development workflow

Work is planned as sprints and slices in [`docs/`](docs/), and each slice has testable acceptance criteria. Commits and pull requests reference their slice ID (e.g. `slice-03-score-locate: …`). Rules for AI coding agents are in [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md).

## Acknowledgements

- [Cricsheet](https://cricsheet.org) for open ball-by-ball cricket data
- [PANNs](https://github.com/qiuqiangkong/audioset_tagging_cnn), [OpenCLIP](https://github.com/mlfoundations/open_clip) and [RapidOCR](https://github.com/RapidAI/RapidOCR) for pretrained models
- Shukla et al., *Automatic Cricket Highlight Generation Using Event-Driven and Excitement-Based Features* (CVPR Workshops 2018), the closest prior work

## License

[MIT](LICENSE)
