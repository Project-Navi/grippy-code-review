# SPDX-License-Identifier: MIT
"""Step 3: Extract discrete candidates from Grippy review comments.

Mirrors Martian's step2_extract_comments.py:
- Inline comments (file + line) become candidates directly.
- General comments are LLM-extracted into discrete issues.

Prompts vendored verbatim from Martian @ 012d682.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from benchmarks.martian.config import BenchConfig

# --- Vendored Martian prompts (loaded from files, not inline) ---
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

EXTRACT_SYSTEM_PROMPT = (_PROMPTS_DIR / "extract_system.txt").read_text().strip()
EXTRACT_USER_PROMPT = (_PROMPTS_DIR / "extract.txt").read_text().strip()

# --- End vendored prompts ---


def inline_to_candidate(inline: dict) -> dict:
    """Convert an inline comment to a candidate (direct, no extraction)."""
    return {
        "text": inline["body"],
        "path": inline.get("path"),
        "line": inline.get("line"),
        "source": "inline",
    }


def _llm_extract_default(text: str) -> list[str]:
    """Extract issues from general comment text using Claude."""
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        temperature=0.0,
        system=EXTRACT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": EXTRACT_USER_PROMPT.format(comment=text)}],
    )
    content = resp.content[0].text
    parsed = json.loads(content)
    return parsed.get("issues", [])


def extract_candidates_for_pr(
    comments: dict,
    llm_extract_fn: Callable[[str], list[str]] | None = _llm_extract_default,
) -> list[dict]:
    """Extract candidates from a PR's comments.

    Args:
        comments: dict with "inline" and "general" keys from run_grippy.py
        llm_extract_fn: function to extract issues from general text.
            Pass None to skip general extraction (when no general comments).
    """
    candidates = []

    # Inline findings → direct candidates
    for inline in comments.get("inline", []):
        candidates.append(inline_to_candidate(inline))

    # General findings → LLM extraction
    general_texts = comments.get("general", [])
    if general_texts and llm_extract_fn is not None:
        combined = "\n\n---\n\n".join(general_texts)
        issues = llm_extract_fn(combined)
        for issue_text in issues:
            candidates.append(
                {
                    "text": issue_text,
                    "path": None,
                    "line": None,
                    "source": "extracted",
                }
            )

    return candidates


def extract_all(config: BenchConfig | None = None) -> None:
    """Extract candidates for all reviewed PRs.

    Writes per-PR status to extract_manifest.json for unified failure accounting.
    """
    config = config or BenchConfig()
    comment_dir = config.output_dir / "comments"
    cand_dir = config.output_dir / "candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for comment_path in sorted(comment_dir.glob("*.json")):
        slug = comment_path.stem
        cand_path = cand_dir / f"{slug}.json"

        try:
            comments = json.loads(comment_path.read_text())
            n_general = len(comments.get("general", []))

            print(f"{slug}: {len(comments.get('inline', []))} inline, {n_general} general")

            extract_fn = _llm_extract_default if n_general > 0 else None
            candidates = extract_candidates_for_pr(comments, llm_extract_fn=extract_fn)

            cand_path.write_text(json.dumps(candidates, indent=2))
            print(f"  → {len(candidates)} candidates")
            manifest.append({"pr": slug, "status": "ok", "candidates": len(candidates)})
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            manifest.append({"pr": slug, "status": "failed", "reason": str(e)})

    # Write extract manifest for unified failure accounting
    manifest_path = config.output_dir / "extract_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Done. Candidates in {cand_dir}")


if __name__ == "__main__":
    extract_all()
