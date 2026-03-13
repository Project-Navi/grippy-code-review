# SPDX-License-Identifier: MIT
"""Contract tests: verify harness dependencies are importable and shaped correctly."""


def test_grippy_imports():
    """Verify the harness can import Grippy's public API surface."""
    from grippy.agent import create_reviewer, format_pr_context
    from grippy.retry import run_review
    from grippy.rules import load_profile, run_rules
    from grippy.schema import GrippyReview

    # Verify callables
    assert callable(create_reviewer)
    assert callable(format_pr_context)
    assert callable(run_review)
    assert callable(run_rules)
    assert callable(load_profile)

    # Verify GrippyReview has expected fields
    assert hasattr(GrippyReview, "model_fields")
    assert "findings" in GrippyReview.model_fields


def test_anthropic_sdk_response_shape():
    """Verify Anthropic SDK has the response shape the harness depends on.

    The harness accesses resp.content[0].text — this test proves
    the SDK types actually expose that path without making an API call.
    """
    import anthropic
    from anthropic.types import Message, TextBlock, Usage

    assert hasattr(anthropic, "Anthropic")

    # Verify TextBlock has .text attribute (harness reads resp.content[0].text)
    block = TextBlock(type="text", text='{"reasoning": "test", "match": true, "confidence": 0.9}')
    assert hasattr(block, "text")
    assert isinstance(block.text, str)

    # Verify the text can be parsed as the judge response format
    import json

    parsed = json.loads(block.text)
    assert parsed["match"] is True
    assert isinstance(parsed["confidence"], float)
    assert "reasoning" in parsed

    # Verify Message.content is a list of ContentBlock (harness indexes [0])
    msg = Message(
        id="msg_test",
        type="message",
        role="assistant",
        content=[block],
        model="test",
        stop_reason="end_turn",
        usage=Usage(input_tokens=0, output_tokens=0),
    )
    assert isinstance(msg.content, list)
    assert len(msg.content) == 1
    assert hasattr(msg.content[0], "text")


def test_vendored_prompts_loadable():
    """Verify vendored prompt files exist and are non-empty."""
    from pathlib import Path

    prompts_dir = Path(__file__).resolve().parent.parent / "benchmarks" / "martian" / "prompts"
    for name in ("extract.txt", "extract_system.txt", "judge.txt"):
        path = prompts_dir / name
        assert path.exists(), f"Missing vendored prompt: {name}"
        content = path.read_text().strip()
        assert len(content) > 50, f"Prompt {name} is suspiciously short"


def test_vendored_prompt_checksums_match():
    """Verify nobody edited vendored prompts without updating checksums.

    If this fails, either re-vendor from Martian or update CHECKSUMS.sha256.
    Never edit prompts in place.
    """
    import hashlib
    from pathlib import Path

    prompts_dir = Path(__file__).resolve().parent.parent / "benchmarks" / "martian" / "prompts"
    checksum_file = prompts_dir / "CHECKSUMS.sha256"
    assert checksum_file.exists(), "Missing CHECKSUMS.sha256"

    expected = {}
    for line in checksum_file.read_text().strip().splitlines():
        parts = line.split()
        if len(parts) == 2:
            expected[parts[1]] = parts[0]

    for name, expected_hash in expected.items():
        path = prompts_dir / name
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, (
            f"Checksum mismatch for {name}: expected {expected_hash[:16]}..., "
            f"got {actual_hash[:16]}... — re-vendor from Martian, don't edit in place"
        )
