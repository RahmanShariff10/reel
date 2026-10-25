"""Camera-shot labels with CLIP (pipeline stage 5: ``classify_shots``).

Every keyframe is embedded with CLIP (cached in ``shot_embeddings.npy``) and labelled
zero-shot by comparing it with text prompts per class from config. The embedder sits
behind a small interface so tests can use a stub.
"""

from __future__ import annotations

import os
import typing
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

import numpy as np

from reel.common.config import ShotsConfig
from reel.common.logging import get_logger
from reel.common.models import Shot, is_valid, read_model, write_model

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("shots.classify")


class Embedder(Protocol):
    def embed_images(self, paths: Sequence[Path]) -> np.ndarray: ...
    def embed_texts(self, texts: Sequence[str]) -> np.ndarray: ...


@contextmanager
def _offline_first():
    """Try loading cached weights without network access first."""
    old = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = old


class ClipEmbedder:
    """OpenCLIP image/text embedder (CPU), weights cached in ``models_dir``."""

    def __init__(self, cfg: ShotsConfig, models_dir: Path) -> None:
        import open_clip
        import torch

        self._torch = torch
        self.batch_size = cfg.batch_size
        models_dir.mkdir(parents=True, exist_ok=True)
        kwargs = dict(pretrained=cfg.clip_pretrained, cache_dir=str(models_dir))
        try:
            with _offline_first():
                model, _, preprocess = open_clip.create_model_and_transforms(
                    cfg.clip_model, **kwargs
                )
        except Exception:
            log.info(
                "CLIP weights not cached; downloading %s/%s", cfg.clip_model, cfg.clip_pretrained
            )
            model, _, preprocess = open_clip.create_model_and_transforms(cfg.clip_model, **kwargs)
        self.model = model.eval()
        self.preprocess = preprocess
        self.tokenizer = open_clip.get_tokenizer(cfg.clip_model)

    def _normalise(self, x) -> np.ndarray:
        x = x / x.norm(dim=-1, keepdim=True)
        return x.float().cpu().numpy()

    def embed_images(self, paths: Sequence[Path]) -> np.ndarray:
        from PIL import Image

        out = []
        with self._torch.no_grad():
            for i in range(0, len(paths), self.batch_size):
                batch = [
                    self.preprocess(Image.open(p).convert("RGB"))
                    for p in paths[i : i + self.batch_size]
                ]
                out.append(self._normalise(self.model.encode_image(self._torch.stack(batch))))
        return np.concatenate(out) if out else np.zeros((0, 512), np.float32)

    def embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        with self._torch.no_grad():
            return self._normalise(self.model.encode_text(self.tokenizer(list(texts))))


def zero_shot(
    embeddings: np.ndarray, prompts: dict[str, list[str]], embedder: Embedder
) -> tuple[list[str], list[dict[str, float]]]:
    """Label each embedding with the class whose (averaged) prompts match best."""
    classes = list(prompts)
    class_vecs = []
    for c in classes:
        vec = embedder.embed_texts(prompts[c]).mean(axis=0)
        class_vecs.append(vec / np.linalg.norm(vec))
    logits = 100.0 * embeddings @ np.stack(class_vecs).T
    logits -= logits.max(axis=1, keepdims=True)
    probs = np.exp(logits)
    probs /= probs.sum(axis=1, keepdims=True)
    labels = [classes[i] for i in probs.argmax(axis=1)]
    return labels, [{c: round(float(p), 4) for c, p in zip(classes, row)} for row in probs]


def load_or_embed(shots: list[Shot], root: Path, cache: Path, embedder_factory) -> np.ndarray:
    """Embeddings for every shot keyframe, reusing ``cache`` when it matches the shots."""
    if cache.is_file():
        cached = np.load(cache)
        if cached.shape[0] == len(shots):
            return cached
    embeddings = embedder_factory().embed_images([root / s.keyframe_path for s in shots])
    np.save(cache, embeddings)
    return embeddings


def is_valid_classify_shots(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    if not (paths.shot_embeddings_npy.is_file() and is_valid(paths.shots_json, list[Shot])):
        return False
    shots = read_model(paths.shots_json, list[Shot])
    return all(s.label is not None for s in shots)


def run_classify_shots(
    ctx: PipelineContext,
    progress_cb: ProgressCallback | None = None,
    embedder: Embedder | None = None,
) -> None:
    paths, cfg = ctx.paths, ctx.config.shots
    shots = read_model(paths.shots_json, list[Shot])
    cache: dict[str, Embedder] = {}

    def factory() -> Embedder:
        if "e" not in cache:
            cache["e"] = embedder or ClipEmbedder(cfg, Path(ctx.config.models_dir))
        return cache["e"]

    embeddings = load_or_embed(shots, paths.root, paths.shot_embeddings_npy, factory)
    if progress_cb:
        progress_cb(0.8)
    labels, probs = zero_shot(embeddings, cfg.prompts, factory()) if shots else ([], [])
    labelled = [
        s.model_copy(update={"label": lab, "probabilities": p, "label_source": "zero_shot"})
        for s, lab, p in zip(shots, labels, probs)
    ]
    write_model(paths.shots_json, labelled)
    log.info("Labelled %d shots (zero-shot)", len(labelled))
    if progress_cb:
        progress_cb(1.0)
