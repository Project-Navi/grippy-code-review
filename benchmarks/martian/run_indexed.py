# SPDX-License-Identifier: MIT
"""Step 2b: Run Grippy indexed reviews (with codebase tools + graph context).

Same as run_grippy.py but builds CodebaseIndex + SQLiteGraphStore for each
repo clone, then passes CodebaseToolkit + graph context to the reviewer agent.
This mirrors the production review pipeline (review.py) as closely as possible.

Requires repo clones at BENCH_REPOS_DIR (default: /tmp/grippy-bench-repos/).
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.martian.config import BenchConfig
from benchmarks.martian.fetch_diffs import parse_golden_prs
from benchmarks.martian.run_grippy import (
    _format_rules_for_agent,
    format_finding_as_comment,
    is_inline_finding,
)

BENCH_REPOS_DIR = Path("/tmp/grippy-bench-repos")


def _extract_touched_files(diff_text: str) -> list[str]:
    """Extract file paths from diff headers."""
    return re.findall(r"^diff --git a/.+ b/(.+)$", diff_text, re.MULTILINE)


def _repo_name_from_slug(slug: str) -> str:
    """Extract repo name from slug like 'keycloak_PR32918'."""
    return slug.rsplit("_PR", 1)[0]


def _build_lite_toolkit(repo_root: Path) -> list:
    """Create a filesystem-only toolkit (grep, read, list) without embeddings.

    Used when the embedding model is unavailable (e.g. VRAM contention).
    This still provides the agent with codebase access for context-aware review,
    just without semantic search_code.
    """
    from agno.tools.function import Function
    from agno.tools.toolkit import Toolkit

    from grippy.codebase import _make_grep_code, _make_list_files, _make_read_file

    tk = Toolkit(name="codebase")
    for fn in [_make_grep_code(repo_root), _make_read_file(repo_root), _make_list_files(repo_root)]:
        func = Function.from_callable(fn)
        tk.functions[func.name] = func
    return [tk]


def _probe_embedding_model(base_url: str, api_key: str) -> bool:
    """Quick probe to check if the embedding model is available."""
    import httpx

    try:
        resp = httpx.post(
            f"{base_url}/embeddings",
            json={"model": "text-embedding-qwen3-embedding-4b", "input": "test"},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5.0,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _build_codebase_tools(
    repo_root: Path,
    data_dir: Path,
    config: BenchConfig,
) -> list:
    """Build CodebaseToolkit. Falls back to lite (filesystem-only) on failure.

    Probes the embedding model first to avoid slow retry loops when the model
    is unavailable (e.g. VRAM contention with the review model).
    """
    if not _probe_embedding_model(config.base_url, config.api_key):
        print("  Embedding model unavailable — using lite toolkit (grep/read/list)")
        return _build_lite_toolkit(repo_root)

    try:
        from agno.vectordb.lancedb import LanceDb
        from agno.vectordb.search import SearchType

        from grippy.codebase import CodebaseIndex, CodebaseToolkit
        from grippy.embedder import create_embedder

        cb_embedder = create_embedder(
            transport=config.transport,
            model="text-embedding-qwen3-embedding-4b",
            base_url=config.base_url,
            api_key=config.api_key,
        )
        lance_dir = data_dir / "lance"
        lance_dir.mkdir(parents=True, exist_ok=True)

        vector_db = LanceDb(
            uri=str(lance_dir),
            table_name="codebase_chunks",
            search_type=SearchType.hybrid,
            use_tantivy=False,
            embedder=cb_embedder,
        )
        cb_index = CodebaseIndex(
            repo_root=repo_root,
            vector_db=vector_db,
            embedder=cb_embedder,
            data_dir=data_dir,
        )
        chunk_count = cb_index.build(force=False)
        if chunk_count > 0:
            print(f"  Indexed {chunk_count} chunks")
        else:
            print("  Codebase index up-to-date (cached)")

        return [CodebaseToolkit(index=cb_index, repo_root=repo_root)]
    except Exception as exc:
        print(f"  WARNING: Full index failed ({exc}), falling back to lite toolkit")
        return _build_lite_toolkit(repo_root)


def _build_graph(repo_root: Path, data_dir: Path) -> "SQLiteGraphStore | None":
    """Build import graph from .py files. Returns None if no Python files found."""
    from grippy.graph_store import SQLiteGraphStore
    from grippy.imports import extract_imports

    graph = SQLiteGraphStore(db_path=data_dir / "navi-graph.db")
    py_files = list(itertools.islice(repo_root.rglob("*.py"), 5000))
    if not py_files:
        print("  No Python files — graph skipped")
        return graph

    for py_f in py_files:
        try:
            rel = str(py_f.relative_to(repo_root))
        except ValueError:
            continue
        try:
            imports = extract_imports(py_f)
        except Exception:
            continue
        for imp in imports:
            graph.add_edge(
                src_type="FILE",
                src_id=rel,
                rel="IMPORTS",
                dst_type="FILE",
                dst_id=imp,
                data={},
            )
    print(f"  Graph: {len(py_files)} Python files scanned")
    return graph


def review_single_pr_indexed(
    *,
    diff_text: str,
    pr_title: str,
    repo_root: Path,
    data_dir: Path,
    config: BenchConfig,
) -> dict:
    """Run indexed Grippy review on a single diff."""
    from grippy.agent import create_reviewer, format_pr_context
    from grippy.codebase import sanitize_tool_hook
    from grippy.graph_context import build_context_pack, format_context_for_llm
    from grippy.retry import run_review
    from grippy.rules import load_profile, run_rules

    # Deterministic rules
    profile_cfg = load_profile(cli_profile=config.profile)
    rule_findings = run_rules(diff_text, profile_cfg)
    rule_text = ""
    if rule_findings and config.profile != "general":
        rule_text = _format_rules_for_agent(rule_findings)

    # Build codebase tools (full index or lite filesystem fallback)
    tools = _build_codebase_tools(repo_root, data_dir, config)

    # Build graph + context
    graph_context_text = ""
    try:
        graph = _build_graph(repo_root, data_dir)
        if graph:
            touched = _extract_touched_files(diff_text)
            pack = build_context_pack(graph, touched_files=touched, author_login="benchmark")
            graph_context_text = format_context_for_llm(pack)
            if graph_context_text:
                print(f"  Graph context: {len(graph_context_text)} chars")
    except Exception as exc:
        print(f"  WARNING: Graph build failed: {exc}")

    agent = create_reviewer(
        model_id=config.model_id,
        base_url=config.base_url,
        api_key=config.api_key,
        transport=config.transport,
        mode=config.mode,
        tools=tools or None,
        tool_call_limit=10 if tools else None,
        tool_hooks=[sanitize_tool_hook] if tools else None,
        include_rule_findings=bool(rule_text),
    )
    message = format_pr_context(
        title=pr_title,
        author="benchmark",
        branch="feature → main",
        diff=diff_text,
        rule_findings=rule_text,
        file_context=graph_context_text,
    )
    review = run_review(agent, message)
    return review.model_dump()


def run_all_indexed(config: BenchConfig | None = None, resume: bool = False) -> None:
    """Run indexed Grippy reviews on all fetched diffs."""
    config = config or BenchConfig.from_env()
    prs = parse_golden_prs(config.golden_dir)

    diff_dir = config.output_dir / "diffs"
    review_dir = config.output_dir / "reviews"
    comment_dir = config.output_dir / "comments"
    review_dir.mkdir(parents=True, exist_ok=True)
    comment_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i, pr in enumerate(prs, 1):
        slug = f"{pr['repo']}_PR{pr['pr_number']}"
        review_path = review_dir / f"{slug}.json"
        comment_path = comment_dir / f"{slug}.json"

        if resume and review_path.exists() and comment_path.exists():
            print(f"[{i}/{len(prs)}] {slug} — skipped (resume)")
            continue

        diff_path = diff_dir / f"{slug}.diff"
        if not diff_path.exists():
            # Try shared diff dir (output/ parent)
            shared_diff_dir = config.output_dir.parent / "output" / "diffs"
            diff_path = shared_diff_dir / f"{slug}.diff"

        if not diff_path.exists():
            print(f"[{i}/{len(prs)}] {slug} — ERROR: diff not found", file=sys.stderr)
            manifest.append({"pr": slug, "status": "failed", "reason": "diff_not_found"})
            continue

        repo_name = _repo_name_from_slug(slug)
        repo_root = BENCH_REPOS_DIR / repo_name
        if not repo_root.exists():
            print(f"[{i}/{len(prs)}] {slug} — ERROR: repo clone not found at {repo_root}")
            manifest.append({"pr": slug, "status": "failed", "reason": "repo_not_found"})
            continue

        diff_text = diff_path.read_text()
        data_dir = config.output_dir / "data" / repo_name
        data_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{i}/{len(prs)}] {slug} — indexed review ({len(diff_text)} chars)")

        ts = datetime.now(UTC).isoformat()
        try:
            review_data = review_single_pr_indexed(
                diff_text=diff_text,
                pr_title=pr["pr_title"],
                repo_root=repo_root,
                data_dir=data_dir,
                config=config,
            )

            output = {"provenance": config.stamp(), "timestamp": ts, "review": review_data}
            review_path.write_text(json.dumps(output, indent=2))

            findings = review_data.get("findings", [])
            inline_comments = []
            general_comments = []
            for f in findings:
                body = format_finding_as_comment(f)
                if is_inline_finding(f):
                    inline_comments.append(
                        {"path": f["file"], "line": f["line_start"], "body": body}
                    )
                else:
                    general_comments.append(body)

            comment_path.write_text(
                json.dumps({"inline": inline_comments, "general": general_comments}, indent=2)
            )
            manifest.append({"pr": slug, "status": "ok", "findings": len(findings)})
        except Exception as e:
            print(f"[{i}/{len(prs)}] {slug} — ERROR: {e}", file=sys.stderr)
            manifest.append({"pr": slug, "status": "failed", "reason": str(e)})

    manifest_path = config.output_dir / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"provenance": config.stamp(), "timestamp": datetime.now(UTC).isoformat(), "results": manifest},
            indent=2,
        )
    )
    ok = sum(1 for m in manifest if m["status"] == "ok")
    fail = sum(1 for m in manifest if m["status"] == "failed")
    print(f"Done. {ok} reviewed, {fail} failed, {len(prs) - ok - fail} skipped.")


if __name__ == "__main__":
    import os

    output_dir = Path(os.environ.get("BENCH_OUTPUT_DIR", str(Path(__file__).parent / "output-devstral-indexed")))
    model_id = os.environ.get("GRIPPY_MODEL_ID", "devstral-small-2-24b-instruct-2512")
    config = BenchConfig(
        model_id=model_id,
        output_dir=output_dir,
    )
    resume = "--resume" in sys.argv
    run_all_indexed(config=config, resume=resume)
