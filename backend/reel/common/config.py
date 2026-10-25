"""Configuration loader for Reel.

Reads ``config/default.yaml``, merges environment-variable overrides
(``REEL_DATA_DIR``, ``REEL_MODELS_DIR``) and programmatic overrides,
and returns a validated :class:`ReelConfig` Pydantic model.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Config sub-models — one per module section in default.yaml
# ---------------------------------------------------------------------------


class IngestConfig(BaseModel):
    audio_sample_rate: int = Field(32000, gt=0)
    audio_channels: int = Field(1, gt=0)


class ScoreboardConfig(BaseModel):
    sample_frames: int = Field(80, gt=0)
    skip_start_min: float = Field(5.0, ge=0)
    skip_end_min: float = Field(5.0, ge=0)
    min_valid_ratio: float = Field(0.4, gt=0, le=1)
    plausibility_ratio: float = Field(0.9, gt=0, le=1)
    consecutive_confirm: int = Field(2, gt=0)
    short_video_min: float = Field(15.0, ge=0)
    short_skip_frac: float = Field(0.05, ge=0, lt=0.5)
    box_padding_frac: float = Field(0.08, ge=0)
    crop_pixel_delta: int = Field(40, gt=0)
    crop_change_frac: float = Field(0.002, ge=0)
    max_run_jump: int = Field(13, gt=0)
    drs_window_s: float = Field(120.0, gt=0)
    new_innings_max_runs: int = Field(12, ge=0)


class ScanConfig(BaseModel):
    low_res_fps: int = Field(4, gt=0)
    score_crop_fps: int = Field(2, gt=0)
    keyframe_width: int = Field(448, gt=0)
    cut_threshold: float = Field(27.0, gt=0)
    min_shot_s: float = Field(0.5, ge=0)


DEFAULT_SHOT_PROMPTS: dict[str, list[str]] = {
    "run_up": [
        "a cricket broadcast view from behind the bowler showing the pitch and the batsman",
        "a bowler running in to bowl, wide television view down the cricket pitch",
    ],
    "close_up": [
        "a close-up of a cricket player's face",
        "a close-up television shot of a cricketer celebrating",
    ],
    "crowd": ["a crowd of spectators in a cricket stadium", "fans cheering in the stands"],
    "field": [
        "a wide view of cricket fielders on a green outfield",
        "a fielder chasing a cricket ball towards the boundary rope",
    ],
    "graphic": [
        "a television graphic with text and statistics",
        "a full-screen scoreboard graphic on TV",
    ],
}


class ShotsConfig(BaseModel):
    clip_model: str = "ViT-B-32-quickgelu"
    clip_pretrained: str = "openai"
    batch_size: int = Field(32, gt=0)
    classifier_file: str = "shot_classifier.joblib"
    prompts: dict[str, list[str]] = Field(default_factory=lambda: dict(DEFAULT_SHOT_PROMPTS))


class AudioConfig(BaseModel):
    excitement_window_s: float = Field(300.0, gt=0)
    panns_model: str = "Cnn14"
    use_panns: bool = True
    panns_hop_s: int = Field(1, ge=1, le=2)
    weight_loudness: float = Field(0.5, ge=0)
    weight_crowd: float = Field(0.5, ge=0)
    loudness_z_full: float = Field(3.0, gt=0)
    crowd_prob_full: float = Field(0.6, gt=0)
    mad_floor_db: float = Field(1.0, gt=0)


class DeliveriesConfig(BaseModel):
    max_merge_gap_s: float = Field(3.0, ge=0)
    last_delivery_s: float = Field(60.0, gt=0)


class BaseImportanceConfig(BaseModel):
    wicket: float = 1.0
    six: float = 0.85
    four: float = 0.7
    near_miss: float = 0.5
    moment_low: float = 0.4
    moment_high: float = 0.8


class BonusConfig(BaseModel):
    excitement_max: float = Field(0.2, ge=0)
    replay_per: float = Field(0.05, ge=0)
    replay_cap: float = Field(0.15, ge=0)
    late_overs: float = Field(0.1, ge=0)


class ClipConfig(BaseModel):
    pre_hit_s: float = Field(6.0, ge=0)
    post_hit_boundary_s: float = Field(12.0, ge=0)
    post_hit_wicket_s: float = Field(20.0, ge=0)
    gap_before_next_s: float = Field(0.5, ge=0)
    max_boundary_s: float = Field(25.0, gt=0)
    max_wicket_s: float = Field(35.0, gt=0)


class HighlightsConfig(BaseModel):
    base_importance: BaseImportanceConfig = BaseImportanceConfig()
    bonus: BonusConfig = BonusConfig()
    clip: ClipConfig = ClipConfig()
    moment_min_excitement: float = Field(0.6, ge=0, le=1)
    title_card_s: float = Field(3.0, ge=0)
    late_overs_from: float = Field(17.0, ge=0)
    close_chase_runs: int = Field(30, ge=0)
    modes: list[str] = ["3min", "5min", "10min", "all"]
    length_tolerance_s: float = Field(15.0, ge=0)


class RenderConfig(BaseModel):
    output_resolution: list[int] = [1280, 720]
    codec: str = "libx264"
    audio_codec: str = "aac"
    fade_duration_s: float = Field(0.3, ge=0)
    caption_font_size: int = Field(36, gt=0)

    @field_validator("output_resolution")
    @classmethod
    def _validate_resolution(cls, v: list[int]) -> list[int]:
        if len(v) != 2 or any(x <= 0 for x in v):
            raise ValueError("output_resolution must be [width, height] with positive values")
        return v


class SignalsConfig(BaseModel):
    score: bool = True
    shots: bool = True
    audio: bool = True
    replays: bool = True


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class ReelConfig(BaseModel):
    """Validated configuration for the entire Reel pipeline."""

    data_dir: Path = Path("./data")
    models_dir: Path = Path("./data/models")

    ingest: IngestConfig = IngestConfig()
    scoreboard: ScoreboardConfig = ScoreboardConfig()
    scan: ScanConfig = ScanConfig()
    shots: ShotsConfig = ShotsConfig()
    audio: AudioConfig = AudioConfig()
    deliveries: DeliveriesConfig = DeliveriesConfig()
    highlights: HighlightsConfig = HighlightsConfig()
    render: RenderConfig = RenderConfig()
    signals: SignalsConfig = SignalsConfig()


# ---------------------------------------------------------------------------
# Deep-merge helper
# ---------------------------------------------------------------------------


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into a copy of *base*.

    Scalar values in *override* replace those in *base*; dicts are merged
    recursively; everything else (lists, etc.) is replaced wholesale.
    """
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Resolve once: the config/ dir lives next to the reel/ package.
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "default.yaml"


def load_config(
    path: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> ReelConfig:
    """Load, merge and validate the Reel configuration.

    Parameters
    ----------
    path:
        Path to a YAML config file.  Defaults to ``backend/config/default.yaml``.
    overrides:
        A dict of values to deep-merge on top of the file values.  Nested
        keys are supported (e.g. ``{"signals": {"audio": False}}``).

    Returns
    -------
    ReelConfig
        A fully validated configuration object.

    Raises
    ------
    pydantic.ValidationError
        If any value fails validation (e.g. a negative frame rate).
    FileNotFoundError
        If the config file does not exist.
    """
    config_path = Path(path) if path is not None else _DEFAULT_CONFIG_PATH

    with open(config_path) as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    # Programmatic overrides (deep merge)
    if overrides:
        raw = _deep_merge(raw, overrides)

    # Environment-variable overrides (highest priority)
    env_data_dir = os.environ.get("REEL_DATA_DIR")
    if env_data_dir is not None:
        raw["data_dir"] = env_data_dir

    env_models_dir = os.environ.get("REEL_MODELS_DIR")
    if env_models_dir is not None:
        raw["models_dir"] = env_models_dir

    return ReelConfig(**raw)
