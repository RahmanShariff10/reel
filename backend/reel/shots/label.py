"""Keyframe labelling tool for the shot classifier.

    uv run python -m reel.shots.label --job <job_id> [--match-id <id>]

Shows each keyframe of a job in a window. Keys: 1 run_up · 2 close_up · 3 crowd ·
4 field · 5 graphic · s skip · u undo · q quit. Labels are saved after every key to
``eval/labels/shots_<match_id>.csv`` (job id, shot id, label — no images), and the tool
resumes at the first shot without a label.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from reel.common.config import load_config
from reel.common.models import Shot, read_model
from reel.common.paths import JobPaths

CLASSES = ["run_up", "close_up", "crowd", "field", "graphic"]
SKIP = "skip"
LABELS_DIR = Path(__file__).resolve().parents[3] / "eval" / "labels"
FIELDS = ["job_id", "match_id", "shot_id", "label"]


class LabelSession:
    """Keyboard-driven labelling state, persisted to a CSV after every change."""

    def __init__(self, job_id: str, match_id: str, shot_ids: list[int], csv_path: Path) -> None:
        self.job_id, self.match_id = job_id, match_id
        self.shot_ids = shot_ids
        self.csv_path = csv_path
        self.labels: dict[int, str] = {}
        self.history: list[int] = []
        if csv_path.is_file():
            with open(csv_path, newline="") as fh:
                for row in csv.DictReader(fh):
                    if row["job_id"] == job_id:
                        self.labels[int(row["shot_id"])] = row["label"]

    @property
    def current(self) -> int | None:
        """First shot without a label (skips count as handled), or None when done."""
        return next((s for s in self.shot_ids if s not in self.labels), None)

    def key(self, ch: str) -> bool:
        """Handle one key; returns False when the session should stop."""
        if ch == "q":
            return False
        if ch == "u":
            if self.history:
                self.labels.pop(self.history.pop(), None)
                self._save()
            return True
        shot = self.current
        if shot is None:
            return False
        if ch in "12345" and len(ch) == 1:
            self.labels[shot] = CLASSES[int(ch) - 1]
        elif ch == "s":
            self.labels[shot] = SKIP
        else:
            return True
        self.history.append(shot)
        self._save()
        return self.current is not None

    def _save(self) -> None:
        rows: list[dict[str, str]] = []
        if self.csv_path.is_file():
            with open(self.csv_path, newline="") as fh:
                rows = [r for r in csv.DictReader(fh) if r["job_id"] != self.job_id]
        rows += [
            {"job_id": self.job_id, "match_id": self.match_id, "shot_id": str(s), "label": lab}
            for s, lab in sorted(self.labels.items())
        ]
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.csv_path.with_suffix(".tmp")
        with open(tmp, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(self.csv_path)


def main(argv: list[str] | None = None) -> int:
    import cv2

    parser = argparse.ArgumentParser(description="Label shot keyframes for the classifier")
    parser.add_argument("--job", required=True)
    parser.add_argument("--match-id", default=None, help="defaults to the job id")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    paths = JobPaths(args.job, data_dir=args.data_dir or load_config().data_dir)
    shots = read_model(paths.shots_json, list[Shot])
    match_id = args.match_id or args.job
    out = args.out or LABELS_DIR / f"shots_{match_id}.csv"
    session = LabelSession(args.job, match_id, [s.id for s in shots], out)
    by_id = {s.id: s for s in shots}
    window = "Reel labelling: 1 run_up 2 close_up 3 crowd 4 field 5 graphic | s skip u undo q quit"

    while (shot_id := session.current) is not None:
        img = cv2.imread(str(paths.root / by_id[shot_id].keyframe_path))
        caption = f"shot {shot_id}  ({len(session.labels)}/{len(shots)} done)"
        cv2.putText(img, caption, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow(window, img)
        ch = chr(cv2.waitKey(0) & 0xFF)
        if not session.key(ch):
            break
    cv2.destroyAllWindows()
    print(f"{len(session.labels)} of {len(shots)} shots labelled → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
