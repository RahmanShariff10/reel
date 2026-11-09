# Reel

**Automatic highlight reels from full football broadcasts. Upload a match, wait, get the reel.**

![Status](https://img.shields.io/badge/status-in%20development-orange)
![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-frontend-000000?logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![ffmpeg](https://img.shields.io/badge/ffmpeg-video-007808?logo=ffmpeg&logoColor=white)
![CPU only](https://img.shields.io/badge/runs%20on-CPU%20only-lightgrey)
![License](https://img.shields.io/badge/license-MIT-blue)

Reel takes a full football match video (~2 hours) and produces a captioned highlight reel of the goals and best chances, plus an explained list of every key event. It runs locally on a laptop CPU, with no manual editing and no cloud services.

> **Status:** being re-scoped from T20 cricket to football. The specs are football; the code is being moved over slice by slice. The last cricket version is git tag `cricket-final`. See [`docs/sprints/README.md`](docs/sprints/README.md) for the plan.

## How it works

1. **Find the score graphic.** Reel locates the on-screen score and running clock (e.g. `ARS 1-0 CHE  34:12`) automatically and reads them throughout the match.
2. **Read the goals.** A score change is a goal; the clock gives the match minute and the halves.
3. **Find other key moments.** Peaks in crowd excitement and replays mark chances, saves and cards.
4. **Listen to the commentary.** Short transcripts around each candidate tell a save from a penalty.
5. **Build the reel.** The top moments are captioned and joined into a 3, 5 or 10-minute reel, or one with every goal and key moment.

Every selected clip comes with its reasons, e.g. *score +1 · crowd excitement high · 2 replays*.

## Features

- Upload a match video, or use a file already on disk
- Score-graphic detection with no user input
- Live processing progress
- Highlight reel with per-clip captions and a title card
- Event list with minute, score, confidence and reasons; click an event to jump to it
- Match summary: final score and goals per half
- Re-cut the reel to a different length without re-analysing the match
- Download the reel (MP4), the events (JSON) and individual clips

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Backend | Python 3.11, FastAPI, Pydantic, SQLite, separate worker process |
| Video and audio | ffmpeg, PySceneDetect, librosa |
| Models (pretrained, CPU) | RapidOCR (PP-OCR), CLIP ViT-B/32 + a small trained classifier, PANNs CNN14, faster-whisper |
| Evaluation | SoccerNet-v2 labels, pytest |

## Project structure

```
backend/     FastAPI server, worker and processing pipeline (Python)
frontend/    Web app (Next.js)
eval/        Evaluation scripts and reports
data/        Local videos, job outputs and models (not committed)
docs/        Research, PRD, architecture, decisions, sprints and slices
```

## Getting started

> Setup commands will be added in slice 34.

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

Reel is evaluated on 10 held-out matches against [SoccerNet](https://www.soccer-net.org/) labels. Targets are provisional until checked on real footage.

| Metric | Target |
|---|---|
| Goals detected | ≥ 95% |
| Key actions found | ≥ 70% |
| Goal clips containing the full moment | ≥ 85% |
| 5-minute reel clips containing a key action | ≥ 60%, and clearly above random |
| Processing time, full match on a laptop CPU | ≤ 60 min |

## Scope

Supported: finished football match files with an on-screen score graphic. Commentary keywords work in English only.
Not supported: live streams, other sports, cloud deployment, user accounts.

## Data and copyright

Match footage is copyrighted. Videos and job outputs stay in `data/`, which is excluded from version control, and are never uploaded anywhere. SoccerNet footage is used under its NDA; see [ADR-006](docs/decisions/ADR-006-soccernet-eval-and-footage-rules.md).

## Development workflow

Work is planned as sprints and slices in [`docs/`](docs/), and each slice has testable acceptance criteria. Commits and pull requests reference their slice ID (e.g. `slice-39-clock-scorebox-locate: …`). Rules for AI coding agents are in [`CLAUDE.md`](CLAUDE.md) and [`AGENTS.md`](AGENTS.md).

## Acknowledgements

- [SoccerNet](https://www.soccer-net.org/) for broadcast data and labels
- [PANNs](https://github.com/qiuqiangkong/audioset_tagging_cnn), [OpenCLIP](https://github.com/mlfoundations/open_clip), [RapidOCR](https://github.com/RapidAI/RapidOCR) and [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for pretrained models

## License

[MIT](LICENSE)
