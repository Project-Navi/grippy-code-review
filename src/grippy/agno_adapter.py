# SPDX-License-Identifier: MIT
"""Agno adapter -- wraps Agno Agent behind ReviewerPort.

Transitional shim for Phase 0 of the Agno-to-LiteLLM migration.
Removed in Phase 4 when Agno is dropped entirely.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from grippy.ports import ReviewResponse, SanitizedPRContext


class _AgnoResponse:
    """Wraps Agno's RunResponse to satisfy the ReviewResponse protocol."""

    __slots__ = ("_raw",)

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    @property
    def content(self) -> str | dict[str, Any] | BaseModel | None:
        return self._raw.content  # type: ignore[no-any-return]

    @property
    def reasoning_content(self) -> str | None:
        return getattr(self._raw, "reasoning_content", None)  # type: ignore[no-any-return]


class AgnoAdapter:
    """Wraps an Agno Agent to satisfy ReviewerPort.

    Delegates run() and model_id to the underlying Agno agent so that
    consumers coding against ReviewerPort are decoupled from Agno internals.
    """

    __slots__ = ("_agent",)

    def __init__(self, agent: Any) -> None:
        self._agent = agent

    def run(self, message: SanitizedPRContext) -> ReviewResponse:
        raw = self._agent.run(message.content)
        return _AgnoResponse(raw)

    @property
    def model_id(self) -> str | None:
        return getattr(getattr(self._agent, "model", None), "id", None)  # type: ignore[no-any-return]


def create_agno_reviewer(**kwargs: Any) -> AgnoAdapter:
    """Create a ReviewerPort-compatible reviewer using the Agno backend.

    Passes all keyword arguments through to agent.create_reviewer(),
    then wraps the resulting Agno Agent in AgnoAdapter.
    """
    from grippy.agent import create_reviewer

    agent = create_reviewer(**kwargs)
    return AgnoAdapter(agent)
