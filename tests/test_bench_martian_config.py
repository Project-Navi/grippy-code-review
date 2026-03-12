# SPDX-License-Identifier: MIT
"""Tests for benchmarks/martian/config.py."""

from benchmarks.martian.config import MARTIAN_COMMIT_SHA, BenchConfig


def test_martian_commit_sha_is_pinned():
    assert len(MARTIAN_COMMIT_SHA) == 40
    assert MARTIAN_COMMIT_SHA == "012d68202e56280855b85abb956410086008a7b2"


def test_default_config():
    cfg = BenchConfig()
    assert cfg.profile == "security"
    assert cfg.golden_dir.name == "golden_comments"
    assert cfg.output_dir.name == "output"


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("GRIPPY_MODEL_ID", "test-model")
    monkeypatch.setenv("GRIPPY_TRANSPORT", "openai")
    cfg = BenchConfig.from_env()
    assert cfg.model_id == "test-model"
    assert cfg.transport == "openai"


def test_config_is_frozen():
    cfg = BenchConfig()
    try:
        cfg.model_id = "changed"  # type: ignore[misc]
        raise AssertionError("Should raise FrozenInstanceError")
    except AttributeError:
        pass


def test_stamp_has_required_fields():
    cfg = BenchConfig()
    stamp = cfg.stamp()
    assert "grippy_version" in stamp
    assert "harness_git_sha" in stamp
    assert "model_id" in stamp
    assert "martian_commit" in stamp
    assert "extract_model" in stamp
    assert "judge_model" in stamp
    assert "prompt_checksums" in stamp
    assert stamp["extract_model"] == cfg.extract_model
    assert stamp["judge_model"] == cfg.judge_model


def test_stamp_prompt_checksums_are_full_sha256():
    """Prompt checksums must be full 64-char SHA-256, not truncated."""
    cfg = BenchConfig()
    stamp = cfg.stamp()
    for name, checksum in stamp["prompt_checksums"].items():
        assert len(checksum) == 64, f"Checksum for {name} is truncated: {len(checksum)} chars"
