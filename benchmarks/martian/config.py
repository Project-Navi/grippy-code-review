# SPDX-License-Identifier: MIT
"""Benchmark run configuration — frozen for headline score."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

MARTIAN_COMMIT_SHA = "012d68202e56280855b85abb956410086008a7b2"

_HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class BenchConfig:
    """Immutable benchmark run configuration."""

    model_id: str = "nemotron-3-nano-30b-a3b"
    transport: str = "local"
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"
    profile: str = "security"
    mode: str = "pr_review"
    extract_model: str = "claude-sonnet-4-5-20250929"
    judge_model: str = "claude-sonnet-4-5-20250929"
    golden_dir: Path = field(default_factory=lambda: _HERE / "golden_comments")
    output_dir: Path = field(default_factory=lambda: _HERE / "output")

    @classmethod
    def from_env(cls) -> BenchConfig:
        """Build config from GRIPPY_* environment variables."""
        return cls(
            model_id=os.environ.get("GRIPPY_MODEL_ID", cls.model_id),
            transport=os.environ.get("GRIPPY_TRANSPORT", cls.transport),
            base_url=os.environ.get("GRIPPY_BASE_URL", cls.base_url),
            api_key=os.environ.get("GRIPPY_API_KEY", cls.api_key),
            profile=os.environ.get("GRIPPY_PROFILE", cls.profile),
            mode=os.environ.get("GRIPPY_MODE", cls.mode),
        )

    def stamp(self) -> dict:
        """Return full provenance dict for embedding in output files.

        Includes everything needed to reproduce this run: Grippy version,
        harness git SHA, vendored prompt checksums, judge/extract model IDs,
        and all config values. Two runs with identical stamps produce
        identical results (modulo LLM non-determinism).
        """
        import hashlib
        import subprocess

        # Grippy package version
        try:
            from importlib.metadata import version as pkg_version

            grippy_ver = pkg_version("grippy-mcp")
        except Exception:
            grippy_ver = "unknown"

        # Harness git SHA (full, not truncated)
        try:
            harness_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=_HERE,
                text=True,
                timeout=5,
            ).strip()
        except Exception:
            harness_sha = "unknown"

        # Vendored prompt checksums (full SHA-256, not truncated)
        prompt_checksums = {}
        prompts_dir = _HERE / "prompts"
        for p in sorted(prompts_dir.glob("*.txt")):
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            prompt_checksums[p.name] = h

        return {
            "grippy_version": grippy_ver,
            "harness_git_sha": harness_sha,
            "model_id": self.model_id,
            "transport": self.transport,
            "profile": self.profile,
            "mode": self.mode,
            "martian_commit": MARTIAN_COMMIT_SHA,
            "extract_model": self.extract_model,
            "judge_model": self.judge_model,
            "prompt_checksums": prompt_checksums,
        }
