# SPDX-License-Identifier: MIT
"""End-to-end tests for the Grippy MCP server over stdio transport.

These tests spawn ``python -m grippy serve`` as a subprocess and communicate
with it using the ``mcp`` Python SDK client (``StdioServerParameters`` +
``ClientSession``).  They exercise the real wire protocol — no mocking.

Requirements:
    - The ``mcp`` package must be installed (``pip install mcp``).
    - ``scan_diff`` tests do NOT require an LLM / API key.
    - ``audit_diff`` tests are skipped unless the right env vars are set.

Run:
    uv run pytest -m e2e tests/test_e2e_mcp_stdio.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import pytest

from tests.e2e_fixtures import LLM_BASE_URL, LLM_MODEL_ID, llm_reachable

mcp_mod = pytest.importorskip("mcp", reason="mcp package required for MCP e2e tests")

from mcp.client.session import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIMEOUT_SECONDS = 15


def _server_params() -> StdioServerParameters:
    """Return ``StdioServerParameters`` that launch the Grippy MCP server."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "grippy", "serve"],
        env=None,  # inherit full environment
    )


async def _open_session() -> tuple[Any, Any, ClientSession, Any]:
    """Open a stdio connection and initialised ``ClientSession``.

    Returns the context-manager objects so the caller can clean up.
    The caller is responsible for ``__aexit__`` on the returned contexts.
    """
    server = _server_params()
    # We return the raw async context managers so that the caller can manage
    # their lifecycle inside a single ``asyncio.run`` invocation.
    transport_ctx = stdio_client(server)
    read_stream, write_stream = await transport_ctx.__aenter__()
    session_ctx = ClientSession(read_stream, write_stream)
    session: ClientSession = await session_ctx.__aenter__()
    await session.initialize()
    return transport_ctx, session_ctx, session, (read_stream, write_stream)


async def _close_session(
    transport_ctx: Any,
    session_ctx: Any,
) -> None:
    """Tear down the session and transport contexts."""
    try:
        await session_ctx.__aexit__(None, None, None)
    except Exception:
        pass
    try:
        await transport_ctx.__aexit__(None, None, None)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.e2e


class TestMcpStdioE2E:
    """End-to-end tests exercising the MCP server over stdio."""

    # -- Test 1: Initialize handshake ----------------------------------------

    def test_server_starts_and_responds_to_initialize(self) -> None:
        """Spawn the server, send initialize, assert capabilities are present."""

        async def _run() -> None:
            transport_ctx = session_ctx = None
            try:
                transport_ctx, session_ctx, session, _ = await asyncio.wait_for(
                    _open_session(),
                    timeout=_TIMEOUT_SECONDS,
                )
                caps = session.get_server_capabilities()
                assert caps is not None, "Server did not return capabilities"
                assert caps.tools is not None, "Server should advertise tool capabilities"
            finally:
                if transport_ctx is not None and session_ctx is not None:
                    await _close_session(transport_ctx, session_ctx)

        asyncio.run(_run())

    # -- Test 2: Tool listing ------------------------------------------------

    def test_list_tools_contains_scan_and_audit(self) -> None:
        """After initialize, tools/list must expose scan_diff and audit_diff."""

        async def _run() -> None:
            transport_ctx = session_ctx = None
            try:
                transport_ctx, session_ctx, session, _ = await asyncio.wait_for(
                    _open_session(),
                    timeout=_TIMEOUT_SECONDS,
                )
                tools_result = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=_TIMEOUT_SECONDS,
                )
                tool_names = {t.name for t in tools_result.tools}
                assert "scan_diff" in tool_names, f"scan_diff missing from {tool_names}"
                assert "audit_diff" in tool_names, f"audit_diff missing from {tool_names}"

                # Each tool must carry an inputSchema
                for tool in tools_result.tools:
                    assert tool.inputSchema is not None, f"Tool {tool.name} is missing inputSchema"
                    # inputSchema should describe scope & profile params
                    props = tool.inputSchema.get("properties", {})
                    assert "scope" in props, f"{tool.name} schema missing 'scope' property"
                    assert "profile" in props, f"{tool.name} schema missing 'profile' property"
            finally:
                if transport_ctx is not None and session_ctx is not None:
                    await _close_session(transport_ctx, session_ctx)

        asyncio.run(_run())

    # -- Test 3: scan_diff tool call -----------------------------------------

    def test_scan_diff_tool_call(self) -> None:
        """Call scan_diff with scope='staged' and verify valid JSON response.

        In a test environment there are typically no staged changes, so we
        expect an empty findings list or possibly an error about git — either
        way the response must be well-formed JSON-RPC and parseable JSON in
        the text content.
        """

        async def _run() -> None:
            transport_ctx = session_ctx = None
            try:
                transport_ctx, session_ctx, session, _ = await asyncio.wait_for(
                    _open_session(),
                    timeout=_TIMEOUT_SECONDS,
                )
                result = await asyncio.wait_for(
                    session.call_tool("scan_diff", {"scope": "staged", "profile": "security"}),
                    timeout=_TIMEOUT_SECONDS,
                )
                # The response must have content
                assert result.content, "scan_diff returned empty content"
                text_block = result.content[0]
                assert text_block.type == "text", f"Expected text content, got {text_block.type}"

                # The text must be valid JSON
                payload = json.loads(text_block.text)

                # If no error, we expect the standard scan response shape
                if "error" not in payload:
                    assert "findings" in payload, "Response missing 'findings' key"
                    assert "gate" in payload, "Response missing 'gate' key"
                    assert "profile" in payload, "Response missing 'profile' key"
                    assert "diff_stats" in payload, "Response missing 'diff_stats' key"
                    assert payload["gate"] in ("passed", "failed")
                    assert isinstance(payload["findings"], list)
            finally:
                if transport_ctx is not None and session_ctx is not None:
                    await _close_session(transport_ctx, session_ctx)

        asyncio.run(_run())

    # -- Test 4: scan_diff with commit scope ---------------------------------

    def test_scan_diff_commit_scope(self) -> None:
        """Call scan_diff with scope='commit:HEAD' — validates commit ref parsing."""

        async def _run() -> None:
            transport_ctx = session_ctx = None
            try:
                transport_ctx, session_ctx, session, _ = await asyncio.wait_for(
                    _open_session(),
                    timeout=_TIMEOUT_SECONDS,
                )
                result = await asyncio.wait_for(
                    session.call_tool("scan_diff", {"scope": "commit:HEAD", "profile": "security"}),
                    timeout=_TIMEOUT_SECONDS,
                )
                assert result.content, "scan_diff returned empty content"
                text_block = result.content[0]
                payload = json.loads(text_block.text)

                # Should succeed (repo has commits) or return a structured error
                if "error" not in payload:
                    assert "findings" in payload
                    assert isinstance(payload["findings"], list)
            finally:
                if transport_ctx is not None and session_ctx is not None:
                    await _close_session(transport_ctx, session_ctx)

        asyncio.run(_run())

    # -- Test 5: scan_diff with invalid scope --------------------------------

    def test_scan_diff_invalid_scope_returns_error(self) -> None:
        """An invalid scope string should produce a JSON error, not crash."""

        async def _run() -> None:
            transport_ctx = session_ctx = None
            try:
                transport_ctx, session_ctx, session, _ = await asyncio.wait_for(
                    _open_session(),
                    timeout=_TIMEOUT_SECONDS,
                )
                result = await asyncio.wait_for(
                    session.call_tool("scan_diff", {"scope": "bogus!!", "profile": "security"}),
                    timeout=_TIMEOUT_SECONDS,
                )
                assert result.content, "scan_diff returned empty content"
                payload = json.loads(result.content[0].text)
                assert "error" in payload, "Expected an error for invalid scope"
            finally:
                if transport_ctx is not None and session_ctx is not None:
                    await _close_session(transport_ctx, session_ctx)

        asyncio.run(_run())

    # -- Test 6: server ping -------------------------------------------------

    def test_server_responds_to_ping(self) -> None:
        """The server should respond to a ping request."""

        async def _run() -> None:
            transport_ctx = session_ctx = None
            try:
                transport_ctx, session_ctx, session, _ = await asyncio.wait_for(
                    _open_session(),
                    timeout=_TIMEOUT_SECONDS,
                )
                # send_ping returns EmptyResult on success; raises on failure
                ping_result = await asyncio.wait_for(
                    session.send_ping(),
                    timeout=_TIMEOUT_SECONDS,
                )
                assert ping_result is not None
            finally:
                if transport_ctx is not None and session_ctx is not None:
                    await _close_session(transport_ctx, session_ctx)

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# audit_diff e2e tests (requires reachable LLM)
# ---------------------------------------------------------------------------

_AUDIT_TIMEOUT_SECONDS = 180


def _audit_server_params() -> StdioServerParameters:
    """Return ``StdioServerParameters`` with LLM env vars for audit_diff."""
    import os

    # Start from the current environment so PATH, HOME, etc. are inherited
    env = dict(os.environ)
    env.update(
        {
            "GRIPPY_TRANSPORT": "local",
            "GRIPPY_BASE_URL": LLM_BASE_URL,
            "GRIPPY_MODEL_ID": LLM_MODEL_ID,
            "GRIPPY_API_KEY": "lm-studio",  # pragma: allowlist secret
        }
    )
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "grippy", "serve"],
        env=env,
    )


async def _open_audit_session() -> tuple[Any, Any, ClientSession, Any]:
    """Open a stdio session configured for audit_diff with homelab env vars."""
    server = _audit_server_params()
    transport_ctx = stdio_client(server)
    read_stream, write_stream = await transport_ctx.__aenter__()
    session_ctx = ClientSession(read_stream, write_stream)
    session: ClientSession = await session_ctx.__aenter__()
    await session.initialize()
    return transport_ctx, session_ctx, session, (read_stream, write_stream)


@pytest.mark.e2e
class TestMcpAuditDiffE2E:
    """End-to-end tests for audit_diff over MCP stdio with a real LLM."""

    # -- Test 1: full audit_diff with local LLM ------------------------------

    @pytest.mark.skipif(not llm_reachable(), reason="LLM not reachable")
    def test_audit_diff_with_local_llm(self) -> None:
        """Call audit_diff with scope='commit:HEAD' against the homelab LLM.

        Validates that the response is well-formed JSON with the expected
        top-level keys: score, verdict, findings, and metadata.model.
        """

        async def _run() -> None:
            transport_ctx = session_ctx = None
            try:
                transport_ctx, session_ctx, session, _ = await asyncio.wait_for(
                    _open_audit_session(),
                    timeout=_AUDIT_TIMEOUT_SECONDS,
                )
                result = await asyncio.wait_for(
                    session.call_tool("audit_diff", {"scope": "commit:HEAD"}),
                    timeout=_AUDIT_TIMEOUT_SECONDS,
                )
                assert result.content, "audit_diff returned empty content"
                text_block = result.content[0]
                assert text_block.type == "text", f"Expected text content, got {text_block.type}"

                payload = json.loads(text_block.text)
                assert "error" not in payload, f"audit_diff returned error: {payload.get('error')}"

                # Top-level structure
                assert "score" in payload, "Response missing 'score' key"
                assert "verdict" in payload, "Response missing 'verdict' key"
                assert "findings" in payload, "Response missing 'findings' key"
                assert "metadata" in payload, "Response missing 'metadata' key"

                # Score bounds
                score_overall = payload["score"]["overall"]
                assert isinstance(score_overall, int), f"score.overall is {type(score_overall)}"
                assert 0 <= score_overall <= 100, f"score.overall={score_overall} out of range"

                # Findings is a list
                assert isinstance(payload["findings"], list)

                # Model is present in metadata
                assert "model" in payload["metadata"], "metadata missing 'model'"
                assert payload["metadata"]["model"], "metadata.model is empty"

            finally:
                if transport_ctx is not None and session_ctx is not None:
                    await _close_session(transport_ctx, session_ctx)

        asyncio.run(_run())

    # -- Test 2: deeper structural validation --------------------------------

    @pytest.mark.skipif(not llm_reachable(), reason="LLM not reachable")
    def test_audit_diff_returns_structured_json(self) -> None:
        """Validate the full audit_diff response structure in detail.

        Checks verdict.status enum, score.overall type, diff_stats presence,
        and metadata completeness. Note: the MCP serializer intentionally
        strips personality fields (opening_catchphrase, closing_line) for
        dense AI-facing output.
        """

        async def _run() -> None:
            transport_ctx = session_ctx = None
            try:
                transport_ctx, session_ctx, session, _ = await asyncio.wait_for(
                    _open_audit_session(),
                    timeout=_AUDIT_TIMEOUT_SECONDS,
                )
                result = await asyncio.wait_for(
                    session.call_tool("audit_diff", {"scope": "commit:HEAD"}),
                    timeout=_AUDIT_TIMEOUT_SECONDS,
                )
                assert result.content, "audit_diff returned empty content"
                payload = json.loads(result.content[0].text)
                assert "error" not in payload, f"audit_diff returned error: {payload.get('error')}"

                # Verdict status must be a valid enum value
                verdict_status = payload["verdict"]["status"]
                valid_statuses = {"PASS", "FAIL", "PROVISIONAL"}
                assert verdict_status in valid_statuses, (
                    f"verdict.status={verdict_status!r} not in {valid_statuses}"
                )

                # Score overall must be an int
                assert isinstance(payload["score"]["overall"], int)

                # Score breakdown fields
                score = payload["score"]
                for sub_key in ("security", "logic", "governance", "reliability", "observability"):
                    assert sub_key in score, f"score missing breakdown key {sub_key!r}"

                # diff_stats in metadata
                metadata = payload["metadata"]
                assert "diff_stats" in metadata, "metadata missing 'diff_stats'"
                diff_stats = metadata["diff_stats"]
                assert isinstance(diff_stats, dict), "diff_stats should be a dict"

                # Profile and model in metadata
                assert "profile" in metadata, "metadata missing 'profile'"
                assert "model" in metadata, "metadata missing 'model'"
                assert "diff_truncated" in metadata, "metadata missing 'diff_truncated'"

                # rule_findings key present (may be empty list)
                assert "rule_findings" in payload, "Response missing 'rule_findings'"
                assert isinstance(payload["rule_findings"], list)

            finally:
                if transport_ctx is not None and session_ctx is not None:
                    await _close_session(transport_ctx, session_ctx)

        asyncio.run(_run())
