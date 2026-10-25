"""Train the shot classifier on labelled keyframes.

    uv run python -m reel.shots.train [--labels eval/labels] [--data-dir data]

Logistic regression on the CLIP embeddings (``shot_embeddings.npy``) of every labelled
shot. Saves ``{models_dir}/shot_classifier.joblib`` and a report comparing it with
zero-shot labels, using leave-one-match-out validation (5-fold if only one match).
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from reel.common.config import load_config
from reel.common.logging import get_logger
from reel.common.paths import JobPaths
from reel.shots.classify import ClipEmbedder, Embedder, zero_shot
from reel.shots.label import CLASSES, LABELS_DIR, SKIP

log = get_logger("shots.train")
REPORT_PATH = Path(__file__).resolve().parents[3] / "eval" / "reports" / "shot_classifier.md"
SEED = 42
MIN_LABELS = 500


@dataclass
class Dataset:
    X: np.ndarray
    y: np.ndarray
    groups: np.ndarray  # match id per row


def load_dataset(labels_dir: Path, data_dir: Path) -> Dataset:
    """Join label CSVs with each job's cached CLIP embeddings (skips are ignored)."""
    X, y, groups = [], [], []
    cache: dict[str, np.ndarray] = {}
    for path in sorted(labels_dir.glob("shots_*.csv")):
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                if row["label"] == SKIP:
                    continue
                job = row["job_id"]
                if job not in cache:
                    cache[job] = np.load(JobPaths(job, data_dir=data_dir).shot_embeddings_npy)
                X.append(cache[job][int(row["shot_id"])])
                y.append(row["label"])
                groups.append(row["match_id"])
    if not X:
        raise ValueError(f"No labels found in {labels_dir}")
    return Dataset(np.stack(X), np.array(y), np.array(groups))


def _new_model():
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SEED)


def _folds(ds: Dataset):
    from sklearn.model_selection import LeaveOneGroupOut, StratifiedKFold

    if len(set(ds.groups)) > 1:
        return "leave-one-match-out", LeaveOneGroupOut().split(ds.X, ds.y, ds.groups)
    k = min(5, min(Counter(ds.y).values()))
    if k < 2:
        return "training set (too few labels per class to cross-validate)", [
            (np.arange(len(ds.y)), np.arange(len(ds.y)))
        ]
    return f"{k}-fold", StratifiedKFold(k, shuffle=True, random_state=SEED).split(ds.X, ds.y)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

    labels = [c for c in CLASSES if c in set(y_true) | set(y_pred)]
    p, r, f, n = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        "labels": labels,
        "per_class": {c: (p[i], r[i], f[i], int(n[i])) for i, c in enumerate(labels)},
        "accuracy": float((y_true == y_pred).mean()),
        "confusion": confusion_matrix(y_true, y_pred, labels=labels),
    }


def _table(title: str, m: dict) -> list[str]:
    lines = [
        f"### {title}",
        "",
        f"Accuracy: {m['accuracy']:.3f}",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for c, (p, r, f, n) in m["per_class"].items():
        lines.append(f"| {c} | {p:.3f} | {r:.3f} | {f:.3f} | {n} |")
    lines += [
        "",
        "Confusion matrix (rows = true, columns = predicted):",
        "",
        "| | " + " | ".join(m["labels"]) + " |",
        "|---" * (len(m["labels"]) + 1) + "|",
    ]
    for c, row in zip(m["labels"], m["confusion"]):
        lines.append(f"| **{c}** | " + " | ".join(str(v) for v in row) + " |")
    return lines + [""]


def train(
    labels_dir: Path,
    data_dir: Path,
    model_out: Path,
    report_out: Path,
    embedder: Embedder | None = None,
    prompts: dict[str, list[str]] | None = None,
) -> dict:
    """Validate, fit on all labels, save the model and the report. Returns metrics."""
    import joblib

    ds = load_dataset(labels_dir, data_dir)
    if len(ds.y) < MIN_LABELS:
        log.warning("Only %d labels; at least %d are recommended", len(ds.y), MIN_LABELS)

    scheme, folds = _folds(ds)
    pred = np.empty(len(ds.y), dtype=object)
    for train_idx, test_idx in folds:
        model = _new_model().fit(ds.X[train_idx], ds.y[train_idx])
        pred[test_idx] = model.predict(ds.X[test_idx])
    clf = _metrics(ds.y, pred.astype(str))

    cfg = load_config()
    if embedder is None:
        embedder = ClipEmbedder(cfg.shots, Path(cfg.models_dir))
    zs_labels, _ = zero_shot(ds.X, prompts or cfg.shots.prompts, embedder)
    zs = _metrics(ds.y, np.array(zs_labels))

    final = _new_model().fit(ds.X, ds.y)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final, model_out)

    report = [
        "# Shot classifier report",
        "",
        f"{len(ds.y)} labelled shots from {len(set(ds.groups))} match(es); validation: {scheme}.",
        "",
        *_table("Trained classifier", clf),
        *_table("Zero-shot CLIP (baseline)", zs),
    ]
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text("\n".join(report))
    log.info("Saved %s and %s", model_out, report_out)
    return {"classifier": clf, "zero_shot": zs, "scheme": scheme}


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Train the shot classifier")
    parser.add_argument("--labels", type=Path, default=LABELS_DIR)
    parser.add_argument("--data-dir", type=Path, default=Path(cfg.data_dir))
    parser.add_argument(
        "--out", type=Path, default=Path(cfg.models_dir) / cfg.shots.classifier_file
    )
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    result = train(args.labels, args.data_dir, args.out, args.report)
    print(
        f"Classifier accuracy {result['classifier']['accuracy']:.3f} "
        f"vs zero-shot {result['zero_shot']['accuracy']:.3f} ({result['scheme']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
