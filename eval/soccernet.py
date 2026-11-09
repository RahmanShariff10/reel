"""SoccerNet label loading, time translation, and manifest handling."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

KEY_ACTIONS: set[str] = {
    "Goal",
    "Penalty",
    "Red card",
    "Yellow->red card",
    "Shots on target",
}

REQUIRED_MANIFEST_FIELDS = ("game", "split", "commentary_language")


def _is_replay(val: Any) -> bool:
    """Return True if replay field indicates a replay row."""
    if isinstance(val, str):
        return val.strip().lower() == "replay"
    if isinstance(val, bool):
        return val
    return False


@dataclass(frozen=True)
class Label:
    """Ground-truth SoccerNet annotation."""

    half: int
    game_time: str
    position_ms: int
    label: str
    team: str | None = None
    visibility: str | None = None

    @property
    def is_key_action(self) -> bool:
        """Return True if this label is in KEY_ACTIONS."""
        return self.label in KEY_ACTIONS


@dataclass(frozen=True)
class CameraLabel(Label):
    """SoccerNet camera shot label with replay indicator."""

    replay: bool = False


SoccerNetLabel = Label
SoccerNetCameraLabel = CameraLabel


def _parse_row(row: dict[str, Any], force_camera: bool = False) -> Label:
    """Parse a single JSON row into a Label or CameraLabel."""
    gt = str(row.get("game_time") or row.get("gameTime") or "")

    if "half" in row and row["half"] is not None:
        half = int(row["half"])
    elif "-" in gt:
        prefix = gt.split("-")[0].strip()
        try:
            half = int(prefix)
        except ValueError:
            half = 1
    else:
        half = 1

    pos = row.get("position_ms")
    if pos is None:
        pos = row.get("position", 0)
    position_ms = int(pos)

    label_str = str(row.get("label", ""))
    team = row.get("team")
    if team is not None:
        team = str(team)
    visibility = row.get("visibility")
    if visibility is not None:
        visibility = str(visibility)

    has_replay = "replay" in row
    replay = _is_replay(row.get("replay"))

    if force_camera or has_replay:
        return CameraLabel(
            half=half,
            game_time=gt,
            position_ms=position_ms,
            label=label_str,
            team=team,
            visibility=visibility,
            replay=replay,
        )

    return Label(
        half=half,
        game_time=gt,
        position_ms=position_ms,
        label=label_str,
        team=team,
        visibility=visibility,
    )


def load_labels(path: Path | str) -> list[Label]:
    """Load SoccerNet Labels-v2.json or Labels-cameras.json into dataclasses."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("annotations", data.get("predictions", [])) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"Expected list of annotations in {path}")

    is_camera_file = "camera" in p.name.lower()
    return [_parse_row(r, force_camera=is_camera_file) for r in rows]


def load_camera_labels(path: Path | str) -> list[CameraLabel]:
    """Load SoccerNet Labels-cameras.json into CameraLabel dataclasses."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("annotations", data.get("predictions", [])) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"Expected list of annotations in {path}")

    labels: list[CameraLabel] = []
    for r in rows:
        parsed = _parse_row(r, force_camera=True)
        if isinstance(parsed, CameraLabel):
            labels.append(parsed)
        else:
            labels.append(
                CameraLabel(
                    half=parsed.half,
                    game_time=parsed.game_time,
                    position_ms=parsed.position_ms,
                    label=parsed.label,
                    team=parsed.team,
                    visibility=parsed.visibility,
                    replay=_is_replay(r.get("replay")),
                )
            )
    return labels


def to_match_time(label: Label | Any, first_half_s: float) -> float:
    """Calculate seconds in the joined match file for a label.

    First half labels are positioned relative to start of first half.
    Second half labels are offset by first_half_s.
    """
    if isinstance(label, dict):
        half = int(label.get("half", 1))
        pos_ms = int(label.get("position_ms", label.get("position", 0)))
    else:
        half = int(getattr(label, "half", 1))
        pos_ms = int(getattr(label, "position_ms", getattr(label, "position", 0)))

    time_s = pos_ms / 1000.0
    if half == 1:
        return float(time_s)
    return float(first_half_s) + float(time_s)


def key_actions(labels: Sequence[Label]) -> list[Label]:
    """Filter labels to only include the five key actions."""
    return [lbl for lbl in labels if lbl.label in KEY_ACTIONS]


def get_key_actions(labels: Sequence[Label]) -> list[Label]:
    """Filter labels to only include the five key actions (alias for key_actions)."""
    return key_actions(labels)


def is_key_action(label: Label | str) -> bool:
    """Check if a label or label name is a key action."""
    name = label if isinstance(label, str) else label.label
    return name in KEY_ACTIONS


@dataclass(frozen=True)
class ManifestEntry:
    """A match entry in eval/manifests/matches.yaml."""

    game: str
    split: str
    commentary_language: str
    job_id: str | None = None  # the Reel job that processed this match, once it has been run


MatchManifest = ManifestEntry


def load_manifest(path: Path | str) -> list[ManifestEntry]:
    """Load and validate eval/manifests/matches.yaml.

    Raises ValueError naming the game and field if any required field is missing.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")

    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if raw is None:
        return []

    items = raw.get("matches", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError(f"Manifest '{path}' must contain a list of matches")

    entries: list[ManifestEntry] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Manifest entry #{idx} is not a dictionary")

        game_name = (
            item.get("game")
            or item.get("game_id")
            or item.get("match_id")
            or f"<entry {idx}>"
        )

        for req in REQUIRED_MANIFEST_FIELDS:
            val = item.get(req)
            if val is None or (isinstance(val, str) and not val.strip()):
                raise ValueError(
                    f"Match '{game_name}' missing required field '{req}'"
                )

        entries.append(
            ManifestEntry(
                game=str(item["game"]),
                split=str(item["split"]),
                commentary_language=str(item["commentary_language"]),
                job_id=str(item["job_id"]) if item.get("job_id") else None,
            )
        )
    return entries
