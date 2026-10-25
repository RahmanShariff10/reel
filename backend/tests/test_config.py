"""Tests for slice-01-backend-scaffold: config loader and package imports.

Acceptance criteria from docs/slices/slice-01-backend-scaffold.md:
- load_config() with no arguments returns values from default.yaml
- REEL_DATA_DIR env var overrides data_dir
- overrides={"signals": {"audio": False}} deep-merges correctly
- Invalid values raise a validation error naming the offending field
- Every reel.<module> subpackage imports successfully
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from reel.common.config import ReelConfig, _deep_merge, load_config

# ---- AC: load_config() with no args returns values from default.yaml ----


class TestLoadConfigDefaults:
    def test_returns_reel_config(self):
        cfg = load_config()
        assert isinstance(cfg, ReelConfig)

    def test_data_dir_default(self):
        cfg = load_config()
        assert cfg.data_dir == Path("./data")

    def test_models_dir_default(self):
        cfg = load_config()
        assert cfg.models_dir == Path("./data/models")

    def test_signals_all_true_by_default(self):
        cfg = load_config()
        assert cfg.signals.score is True
        assert cfg.signals.shots is True
        assert cfg.signals.audio is True
        assert cfg.signals.replays is True

    def test_scoreboard_sample_frames(self):
        cfg = load_config()
        assert cfg.scoreboard.sample_frames == 80

    def test_highlights_modes(self):
        cfg = load_config()
        assert cfg.highlights.modes == ["3min", "5min", "10min", "all"]


# ---- AC: REEL_DATA_DIR=/tmp/x → data_dir is /tmp/x ----


class TestEnvVarOverrides:
    def test_reel_data_dir(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REEL_DATA_DIR", "/tmp/x")
        cfg = load_config()
        assert cfg.data_dir == Path("/tmp/x")

    def test_reel_models_dir(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("REEL_MODELS_DIR", "/tmp/models")
        cfg = load_config()
        assert cfg.models_dir == Path("/tmp/models")

    def test_env_overrides_yaml_and_programmatic(self, monkeypatch: pytest.MonkeyPatch):
        """Env vars take priority over both the file and programmatic overrides."""
        monkeypatch.setenv("REEL_DATA_DIR", "/tmp/env")
        cfg = load_config(overrides={"data_dir": "/tmp/prog"})
        assert cfg.data_dir == Path("/tmp/env")


# ---- AC: overrides={"signals": {"audio": False}} deep-merges ----


class TestOverridesMerge:
    def test_audio_false_rest_unchanged(self):
        cfg = load_config(overrides={"signals": {"audio": False}})
        assert cfg.signals.audio is False
        # All other signal values must be unchanged
        assert cfg.signals.score is True
        assert cfg.signals.shots is True
        assert cfg.signals.replays is True

    def test_nested_override(self):
        cfg = load_config(overrides={"highlights": {"base_importance": {"wicket": 0.9}}})
        assert cfg.highlights.base_importance.wicket == 0.9
        # Other importance values unchanged
        assert cfg.highlights.base_importance.six == 0.85

    def test_deep_merge_helper(self):
        base = {"a": {"b": 1, "c": 2}, "d": 3}
        override = {"a": {"b": 10}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": 10, "c": 2}, "d": 3}
        # Original is not mutated
        assert base["a"]["b"] == 1


# ---- AC: Invalid value → validation error naming the offending field ----


class TestValidationErrors:
    def test_negative_sample_rate(self):
        with pytest.raises(ValidationError) as exc_info:
            load_config(overrides={"ingest": {"audio_sample_rate": -1}})
        errors = exc_info.value.errors()
        field_locs = [e["loc"] for e in errors]
        # The error must reference 'audio_sample_rate'
        assert any("audio_sample_rate" in loc for loc in field_locs)

    def test_negative_frame_count(self):
        with pytest.raises(ValidationError) as exc_info:
            load_config(overrides={"scoreboard": {"sample_frames": 0}})
        errors = exc_info.value.errors()
        field_locs = [e["loc"] for e in errors]
        assert any("sample_frames" in loc for loc in field_locs)

    def test_invalid_resolution(self):
        with pytest.raises(ValidationError):
            load_config(overrides={"render": {"output_resolution": [0, 720]}})

    def test_plausibility_ratio_above_one(self):
        with pytest.raises(ValidationError) as exc_info:
            load_config(overrides={"scoreboard": {"plausibility_ratio": 1.5}})
        errors = exc_info.value.errors()
        field_locs = [e["loc"] for e in errors]
        assert any("plausibility_ratio" in loc for loc in field_locs)


# ---- AC: All reel.<module> subpackages import successfully ----


class TestSubpackageImports:
    MODULES = [
        "reel",
        "reel.common",
        "reel.common.config",
        "reel.common.logging",
        "reel.jobs",
        "reel.api",
        "reel.ingest",
        "reel.scoreboard",
        "reel.shots",
        "reel.audio",
        "reel.deliveries",
        "reel.highlights",
        "reel.render",
    ]

    @pytest.mark.parametrize("module_name", MODULES)
    def test_import(self, module_name: str):
        import importlib

        mod = importlib.import_module(module_name)
        assert mod is not None


# ---- Logging ----


class TestLogging:
    def test_get_logger_prepends_reel(self):
        from reel.common.logging import get_logger

        log = get_logger("scoreboard")
        assert log.name == "reel.scoreboard"

    def test_get_logger_already_prefixed(self):
        from reel.common.logging import get_logger

        log = get_logger("reel.common.config")
        assert log.name == "reel.common.config"

    def test_setup_logging_is_idempotent(self):
        from reel.common.logging import setup_logging

        # Should not raise on repeated calls
        setup_logging()
        setup_logging()
