# SPDX-License-Identifier: MIT
"""Tests for Grippy agent evolution — new create_reviewer() parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from grippy.agent import _resolve_transport, create_reviewer, format_pr_context

# Default prompts dir for all tests
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "src" / "grippy" / "prompts_data"


# --- Backward compatibility ---


class TestCreateReviewerBackwardCompat:
    """Existing create_reviewer() API must still work unchanged."""

    def test_basic_call_returns_agent(self) -> None:
        """Calling with original params returns an Agent."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR, mode="pr_review")
        assert agent.name == "grippy"

    def test_default_no_db(self) -> None:
        """Without db_path, agent has no db configured."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR)
        assert agent.db is None

    def test_all_modes_work(self) -> None:
        """All six review modes produce valid agents."""
        for mode in (
            "pr_review",
            "security_audit",
            "governance_check",
            "surprise_audit",
            "cli",
            "github_app",
        ):
            agent = create_reviewer(prompts_dir=PROMPTS_DIR, mode=mode)
            assert agent.name == "grippy"

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False)
    def test_structured_outputs_enabled_for_openai(self) -> None:
        """OpenAI transport enables native structured outputs."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR, transport="openai")
        assert agent.structured_outputs is True

    def test_structured_outputs_disabled_for_local(self) -> None:
        """Local transport disables structured outputs (servers may not support it)."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR, transport="local")
        assert agent.structured_outputs is False


# --- Session persistence ---


class TestSessionPersistence:
    def test_db_path_creates_sqlite_session(self, tmp_path: Path) -> None:
        """Providing db_path wires up SqliteDb for session persistence."""
        db_path = tmp_path / "grippy-session.db"
        agent = create_reviewer(
            prompts_dir=PROMPTS_DIR,
            db_path=db_path,
        )
        assert agent.db is not None

    def test_session_id_passed_through(self, tmp_path: Path) -> None:
        """session_id is set on the agent for review continuity."""
        agent = create_reviewer(
            prompts_dir=PROMPTS_DIR,
            db_path=tmp_path / "session.db",
            session_id="pr-123-review",
        )
        assert agent.session_id == "pr-123-review"

    def test_num_history_runs_configured(self, tmp_path: Path) -> None:
        """num_history_runs controls how many prior runs are in context."""
        agent = create_reviewer(
            prompts_dir=PROMPTS_DIR,
            db_path=tmp_path / "session.db",
            num_history_runs=5,
        )
        assert agent.num_history_runs == 5

    def test_default_num_history_runs(self, tmp_path: Path) -> None:
        """Default num_history_runs is 3 when db is configured."""
        agent = create_reviewer(
            prompts_dir=PROMPTS_DIR,
            db_path=tmp_path / "session.db",
        )
        assert agent.num_history_runs == 3

    def test_history_disabled_with_db(self, tmp_path: Path) -> None:
        """add_history_to_context is False — unsanitized history is a poisoning vector."""
        agent = create_reviewer(
            prompts_dir=PROMPTS_DIR,
            db_path=tmp_path / "session.db",
        )
        assert agent.add_history_to_context is False

    def test_history_disabled_without_db(self) -> None:
        """add_history_to_context is unconditionally False — not gated on db_path."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR)
        assert agent.add_history_to_context is False


# --- Context injection ---


class TestContextInjection:
    def test_additional_context_passed_to_agent(self) -> None:
        """additional_context string is wired into the agent."""
        ctx = "Codebase: navi-bootstrap. Author: nelson. Conventions: use Result types."
        agent = create_reviewer(
            prompts_dir=PROMPTS_DIR,
            additional_context=ctx,
        )
        assert agent.additional_context == ctx

    def test_no_context_by_default(self) -> None:
        """Without additional_context, agent has None."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR)
        assert agent.additional_context is None


# --- Tool hooks ---


class TestToolHooks:
    def test_tool_hooks_passed_to_agent(self) -> None:
        """tool_hooks parameter is forwarded to the Agent."""

        def dummy_hook(name: str, func: Any, args: dict) -> Any:  # type: ignore[type-arg]
            return func(**args)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            agent = create_reviewer(
                transport="openai",
                model_id="gpt-4o-mini",
                tool_hooks=[dummy_hook],
            )
        assert agent.tool_hooks is not None
        assert len(agent.tool_hooks) == 1

    def test_no_tool_hooks_by_default(self) -> None:
        """Without tool_hooks, agent has None."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR)
        assert agent.tool_hooks is None


# --- format_pr_context backward compat ---


class TestFormatPrContext:
    """format_pr_context() must continue to work unchanged."""

    def test_basic_formatting(self) -> None:
        result = format_pr_context(
            title="feat: add auth",
            author="testdev",
            branch="feature/auth → main",
            diff="diff --git a/app.py b/app.py\n+new line\n",
        )
        assert "<pr_metadata>" in result
        assert "feat: add auth" in result
        assert "<diff>" in result

    def test_with_governance_rules(self) -> None:
        result = format_pr_context(
            title="fix: null check",
            author="dev",
            branch="fix → main",
            diff="diff --git a/x.py b/x.py\n",
            governance_rules="Rule 1: always validate",
        )
        assert "<governance_rules>" in result

    def test_diff_stats(self) -> None:
        diff = "diff --git a/x.py b/x.py\n+++ b/x.py\n+added\n-removed\n--- a/x.py\n"
        result = format_pr_context(
            title="test",
            author="dev",
            branch="x → main",
            diff=diff,
        )
        assert "Changed Files: 1" in result


# --- Transport selection ---


class TestTransportSelection:
    """Tests for explicit transport selection (F2 fix)."""

    def test_explicit_local_transport(self) -> None:
        """transport='local' uses OpenAILike regardless of env."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR, transport="local")
        from agno.models.openai.like import OpenAILike

        assert isinstance(agent.model, OpenAILike)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False)
    def test_explicit_openai_transport(self) -> None:
        """transport='openai' uses OpenAIChat."""
        agent = create_reviewer(prompts_dir=PROMPTS_DIR, transport="openai")
        from agno.models.openai import OpenAIChat

        assert isinstance(agent.model, OpenAIChat)

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GRIPPY_TRANSPORT env var overrides inference."""
        monkeypatch.setenv("GRIPPY_TRANSPORT", "local")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        transport, source = _resolve_transport(None, "test-model")
        assert transport == "local"
        assert source == "env:GRIPPY_TRANSPORT"

    def test_param_precedence_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit param takes precedence over GRIPPY_TRANSPORT env var."""
        monkeypatch.setenv("GRIPPY_TRANSPORT", "openai")
        transport, source = _resolve_transport("local", "test-model")
        assert transport == "local"
        assert source == "param"

    def test_inference_warning_when_no_explicit(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Inferring from OPENAI_API_KEY prints a notice warning."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("GRIPPY_TRANSPORT", raising=False)
        transport, source = _resolve_transport(None, "test-model")
        assert transport == "openai"
        assert "inferred" in source
        captured = capsys.readouterr()
        assert "::notice::" in captured.out

    def test_default_is_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No env vars and no param defaults to local transport."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GRIPPY_TRANSPORT", raising=False)
        transport, source = _resolve_transport(None, "test-model")
        assert transport == "local"
        assert source == "default"

    def test_invalid_transport_raises(self) -> None:
        """Invalid transport value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid GRIPPY_TRANSPORT"):
            _resolve_transport("cloud", "test-model")

    def test_typo_transport_raises(self) -> None:
        """Common typos are caught and rejected."""
        for typo in ("open-ai", "remote", "gcp", "aws"):
            with pytest.raises(ValueError, match="Invalid GRIPPY_TRANSPORT"):
                _resolve_transport(typo, "test-model")

    def test_transport_normalized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Transport values are normalized (strip + lowercase)."""
        transport, _ = _resolve_transport("  OPENAI  ", "test-model")
        assert transport == "openai"

    def test_env_transport_normalized(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GRIPPY_TRANSPORT env var is normalized."""
        monkeypatch.setenv("GRIPPY_TRANSPORT", "  Local  ")
        transport, source = _resolve_transport(None, "test-model")
        assert transport == "local"
        assert source == "env:GRIPPY_TRANSPORT"

    def test_invalid_env_transport_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid GRIPPY_TRANSPORT env var raises ValueError."""
        monkeypatch.setenv("GRIPPY_TRANSPORT", "gcp")
        with pytest.raises(ValueError, match="Invalid GRIPPY_TRANSPORT"):
            _resolve_transport(None, "test-model")


class TestMultiProviderTransport:
    """Tests for multi-provider transport support."""

    @pytest.mark.parametrize("provider", ["anthropic", "google", "groq", "mistral"])
    def test_provider_transport_resolves(self, provider: str) -> None:
        """Provider names are accepted as valid transports."""
        transport, source = _resolve_transport(provider, "test-model")
        assert transport == provider
        assert source == "param"

    @pytest.mark.parametrize("provider", ["anthropic", "google", "groq", "mistral"])
    def test_provider_env_transport_resolves(
        self, provider: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Provider names work via GRIPPY_TRANSPORT env var."""
        monkeypatch.setenv("GRIPPY_TRANSPORT", provider)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        transport, source = _resolve_transport(None, "test-model")
        assert transport == provider
        assert source == "env:GRIPPY_TRANSPORT"

    @pytest.mark.parametrize(
        "provider,module_path,class_name",
        [
            ("anthropic", "agno.models.anthropic", "Claude"),
            ("google", "agno.models.google", "Gemini"),
            ("groq", "agno.models.groq", "Groq"),
            ("mistral", "agno.models.mistral", "MistralChat"),
        ],
    )
    def test_provider_creates_correct_model(
        self, provider: str, module_path: str, class_name: str
    ) -> None:
        """Each provider transport instantiates the correct agno model class."""
        from unittest.mock import MagicMock

        from agno.models.base import Model

        mock_model_instance = MagicMock(spec=Model)
        mock_cls = MagicMock(return_value=mock_model_instance)
        mock_module = MagicMock()
        setattr(mock_module, class_name, mock_cls)

        with patch("importlib.import_module", return_value=mock_module) as mock_import:
            create_reviewer(prompts_dir=PROMPTS_DIR, transport=provider, model_id="test-model")
            mock_import.assert_called_once_with(module_path)
            mock_cls.assert_called_once_with(id="test-model")

    def test_provider_structured_outputs_false(self) -> None:
        """Non-OpenAI providers have structured_outputs=False."""
        from unittest.mock import MagicMock

        from agno.models.base import Model

        mock_model_instance = MagicMock(spec=Model)
        mock_cls = MagicMock(return_value=mock_model_instance)
        mock_module = MagicMock()
        mock_module.Claude = mock_cls

        with patch("importlib.import_module", return_value=mock_module):
            agent = create_reviewer(
                prompts_dir=PROMPTS_DIR, transport="anthropic", model_id="test-model"
            )
            assert agent.structured_outputs is False

    def test_openai_structured_outputs_true(self) -> None:
        """OpenAI provider has structured_outputs=True."""
        from unittest.mock import MagicMock

        from agno.models.base import Model

        mock_model_instance = MagicMock(spec=Model)
        mock_cls = MagicMock(return_value=mock_model_instance)
        mock_module = MagicMock()
        mock_module.OpenAIChat = mock_cls

        with patch("importlib.import_module", return_value=mock_module):
            agent = create_reviewer(
                prompts_dir=PROMPTS_DIR, transport="openai", model_id="test-model"
            )
            assert agent.structured_outputs is True

    def test_local_still_uses_openai_like(self) -> None:
        """Local transport still uses OpenAILike directly (no registry)."""
        from agno.models.openai.like import OpenAILike

        agent = create_reviewer(prompts_dir=PROMPTS_DIR, transport="local")
        assert isinstance(agent.model, OpenAILike)
