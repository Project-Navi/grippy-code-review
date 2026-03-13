# SPDX-License-Identifier: MIT
"""Step 4: Judge candidates against golden comments.

Uses Martian's judge prompt verbatim. Greedy best-confidence matching.
Prompt vendored from Martian @ 012d682.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from benchmarks.martian.config import BenchConfig
from benchmarks.martian.fetch_diffs import parse_golden_prs

# --- Vendored Martian prompt (loaded from file, not inline) ---
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

JUDGE_PROMPT = (_PROMPTS_DIR / "judge.txt").read_text().strip()

# --- End vendored prompt ---


def judge_pair(
    golden_comment: str,
    candidate_text: str,
    *,
    judge_fn: Callable[[str, str], dict] | None = None,
) -> dict:
    """Judge whether a candidate matches a golden comment.

    Returns: {reasoning, match, confidence}
    """
    if judge_fn is not None:
        return judge_fn(golden_comment, candidate_text)
    return _llm_judge(golden_comment, candidate_text)


def _llm_judge(golden_comment: str, candidate_text: str) -> dict:
    """Default judge using Claude."""
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=512,
        temperature=0.0,
        messages=[
            {
                "role": "user",
                "content": JUDGE_PROMPT.format(
                    golden_comment=golden_comment,
                    candidate=candidate_text,
                ),
            }
        ],
    )
    content = resp.content[0].text.strip()
    # Strip markdown code fences if present (Claude sometimes wraps JSON)
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    return json.loads(content)


def match_candidates_to_golden(
    verdicts: list[dict],
    n_golden: int,
    n_candidates: int,
) -> dict[int, int | None]:
    """Greedy assignment: each golden matches its highest-confidence candidate.

    Each candidate can only be assigned to one golden (first-come).
    Returns: {golden_idx: candidate_idx or None}
    """
    # Sort by confidence descending
    matches_by_golden: dict[int, list] = {i: [] for i in range(n_golden)}
    for v in verdicts:
        if v["match"]:
            matches_by_golden[v["golden_idx"]].append(v)

    # Sort each golden's matches by confidence
    for g in matches_by_golden:
        matches_by_golden[g].sort(key=lambda x: x["confidence"], reverse=True)

    # Greedy assignment
    assigned_candidates: set[int] = set()
    result: dict[int, int | None] = {}

    # Process goldens by their best available confidence
    golden_order = sorted(
        range(n_golden),
        key=lambda g: matches_by_golden[g][0]["confidence"] if matches_by_golden[g] else -1,
        reverse=True,
    )

    for g in golden_order:
        result[g] = None
        for v in matches_by_golden[g]:
            if v["candidate_idx"] not in assigned_candidates:
                result[g] = v["candidate_idx"]
                assigned_candidates.add(v["candidate_idx"])
                break

    return result


def compute_metrics(
    tp: int,
    total_candidates: int,
    total_golden: int,
) -> dict:
    """Compute precision, recall, F1."""
    precision = tp / total_candidates if total_candidates > 0 else 0.0
    recall = tp / total_golden if total_golden > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp}


def judge_all(config: BenchConfig | None = None) -> None:
    """Judge all candidates against golden comments."""
    config = config or BenchConfig()
    prs = parse_golden_prs(config.golden_dir)
    cand_dir = config.output_dir / "candidates"
    score_dir = config.output_dir / "scores"
    score_dir.mkdir(parents=True, exist_ok=True)

    all_results = []
    total_tp = 0
    total_candidates = 0
    total_golden = 0

    for pr in prs:
        slug = f"{pr['repo']}_PR{pr['pr_number']}"
        cand_path = cand_dir / f"{slug}.json"

        if not cand_path.exists():
            print(f"{slug}: no candidates — recording as missing")
            all_results.append(
                {
                    "pr": slug,
                    "golden_url": pr["golden_url"],
                    "n_candidates": 0,
                    "n_golden": len(pr["golden_comments"]),
                    "status": "missing_candidates",
                    "metrics": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": 0},
                }
            )
            total_golden += len(pr["golden_comments"])
            continue

        candidates = json.loads(cand_path.read_text())
        golden = pr["golden_comments"]

        print(f"{slug}: {len(candidates)} candidates vs {len(golden)} golden")

        # All-pairs judging
        verdicts = []
        for gi, g in enumerate(golden):
            for ci, c in enumerate(candidates):
                v = judge_pair(g["comment"], c["text"])
                v["golden_idx"] = gi
                v["candidate_idx"] = ci
                verdicts.append(v)

        # Greedy matching
        matches = match_candidates_to_golden(verdicts, len(golden), len(candidates))
        tp = sum(1 for v in matches.values() if v is not None)

        metrics = compute_metrics(tp, len(candidates), len(golden))
        print(f"  → P={metrics['precision']:.2f} R={metrics['recall']:.2f} F1={metrics['f1']:.2f}")

        all_results.append(
            {
                "pr": slug,
                "golden_url": pr["golden_url"],
                "n_candidates": len(candidates),
                "n_golden": len(golden),
                "verdicts": verdicts,
                "matches": {str(k): v for k, v in matches.items()},
                "metrics": metrics,
            }
        )
        total_tp += tp
        total_candidates += len(candidates)
        total_golden += len(golden)

    # Aggregate
    overall = compute_metrics(total_tp, total_candidates, total_golden)
    output = {
        "provenance": config.stamp(),
        "overall": overall,
        "per_pr": all_results,
    }

    score_path = score_dir / "judge_results.json"
    score_path.write_text(json.dumps(output, indent=2))
    print(
        f"\nOverall: P={overall['precision']:.2f} R={overall['recall']:.2f} F1={overall['f1']:.2f}"
    )
    print(f"Saved to {score_path}")


if __name__ == "__main__":
    judge_all()
