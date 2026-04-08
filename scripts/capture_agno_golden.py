# SPDX-License-Identifier: MIT
"""Capture the exact system messages Agno constructs for each Grippy review mode.

These golden files are critical migration ground truth — they cannot be
reconstructed after Agno is removed.

Usage:
    uv run python scripts/capture_agno_golden.py

Output:
    tests/fixtures/agno_golden_messages/{mode}.txt          — cloud transport (no JSON schema)
    tests/fixtures/agno_golden_messages/{mode}_local.txt    — local transport (with JSON schema)
    tests/fixtures/agno_golden_messages/metadata.txt        — construction metadata
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

# Ensure grippy is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Suppress any transport inference warnings
os.environ["GRIPPY_TRANSPORT"] = "local"


def main() -> None:
    from agno.agent._messages import get_system_message
    from agno.run.base import RunContext
    from agno.session.agent import AgentSession

    from grippy.agent import create_reviewer
    from grippy.prompts import MODE_CHAINS
    from grippy.schema import GrippyReview

    output_dir = (
        Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "agno_golden_messages"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    modes = list(MODE_CHAINS.keys())
    metadata_lines: list[str] = []
    metadata_lines.append("Agno Golden Message Capture Metadata")
    metadata_lines.append("=" * 50)

    for mode in modes:
        print(f"\n{'=' * 60}")
        print(f"Capturing mode: {mode}")
        print(f"{'=' * 60}")

        # Create the agent using grippy's factory — local transport, no LLM call
        agent = create_reviewer(
            mode=mode,
            model_id="capture-dummy",
            base_url="http://localhost:9999/v1",
            api_key="dummy-key",  # pragma: allowlist secret
            transport="local",
        )

        # Build minimal session and run_context required by get_system_message
        session = AgentSession(session_id=str(uuid4()))

        # --- Variant 1: Cloud transport (no JSON schema injection) ---
        # Simulate a cloud provider where output_schema is NOT set on the agent
        # and structured_outputs=True, so no JSON prompt is appended.
        run_context_cloud = RunContext(
            run_id=str(uuid4()),
            session_id=session.session_id,
            output_schema=None,  # Cloud: no JSON schema in system prompt
        )

        msg_cloud = get_system_message(
            agent=agent,
            session=session,
            run_context=run_context_cloud,
            tools=None,
        )

        if msg_cloud is None:
            print(f"  WARNING: Cloud system message is None for mode={mode}")
            continue

        cloud_content = msg_cloud.content
        cloud_path = output_dir / f"{mode}.txt"
        cloud_path.write_text(cloud_content, encoding="utf-8")
        print(f"  Cloud message: {len(cloud_content)} chars -> {cloud_path.name}")

        # --- Variant 2: Local transport (JSON schema injected) ---
        # For local transport, output_schema=GrippyReview is set and
        # supports_native_structured_outputs=False, so Agno injects
        # the JSON output prompt.
        run_context_local = RunContext(
            run_id=str(uuid4()),
            session_id=session.session_id,
            output_schema=GrippyReview,  # Local: JSON schema appended
        )

        msg_local = get_system_message(
            agent=agent,
            session=session,
            run_context=run_context_local,
            tools=None,
        )

        if msg_local is None:
            print(f"  WARNING: Local system message is None for mode={mode}")
            continue

        local_content = msg_local.content
        local_path = output_dir / f"{mode}_local.txt"
        local_path.write_text(local_content, encoding="utf-8")
        print(f"  Local message: {len(local_content)} chars -> {local_path.name}")

        # --- Metadata ---
        delta = len(local_content) - len(cloud_content)
        metadata_lines.append(f"\nMode: {mode}")
        metadata_lines.append(f"  Cloud message length: {len(cloud_content)} chars")
        metadata_lines.append(f"  Local message length: {len(local_content)} chars")
        metadata_lines.append(f"  JSON schema delta: +{delta} chars")
        metadata_lines.append(f"  Message role: {msg_cloud.role}")
        metadata_lines.append(f"  Instruction count: {len(agent.instructions)}")

        # Report what's in the system message structurally
        has_description = agent.description is not None
        has_instructions = agent.instructions is not None and len(agent.instructions) > 0
        metadata_lines.append(f"  Has description (identity): {has_description}")
        metadata_lines.append(f"  Has instructions: {has_instructions}")
        metadata_lines.append(f"  use_instruction_tags: {agent.use_instruction_tags}")
        metadata_lines.append(f"  markdown: {agent.markdown}")
        metadata_lines.append(f"  add_history_to_context: {agent.add_history_to_context}")
        metadata_lines.append(f"  structured_outputs: {agent.structured_outputs}")
        metadata_lines.append(
            f"  model.supports_native_structured_outputs: "
            f"{agent.model.supports_native_structured_outputs}"
        )

    # Write metadata
    metadata_path = output_dir / "metadata.txt"
    metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")
    print(f"\nMetadata written to {metadata_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Golden files written to: {output_dir}")
    print(f"Modes captured: {len(modes)}")
    print("Files per mode: 2 (cloud + local)")
    print(f"Total files: {len(modes) * 2 + 1} (including metadata)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
