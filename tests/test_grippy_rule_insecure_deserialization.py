# SPDX-License-Identifier: MIT
"""Tests for Rule 10: insecure-deserialization."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.insecure_deserialization import (
    _DESER_PATTERNS,
    InsecureDeserializationRule,
)


def _make_diff(filename: str, added_lines: list[str]) -> str:
    body = "\n".join(f"+{line}" for line in added_lines)
    return (
        f"diff --git a/{filename} b/{filename}\n"
        f"new file mode 100644\n"
        f"--- /dev/null\n"
        f"+++ b/{filename}\n"
        f"@@ -0,0 +1,{len(added_lines)} @@\n"
        f"{body}\n"
    )


def _ctx(diff: str) -> RuleContext:
    return RuleContext(diff=diff, files=parse_diff(diff), config=PROFILES["security"])


class TestInsecureDeserializationRule:
    def test_yaml_load_not_flagged(self) -> None:
        """yaml.load is handled by dangerous_sinks.py, not this rule."""
        diff = _make_diff("config.py", ["data = yaml.load(raw, Loader=yaml.FullLoader)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 0

    def test_shelve_open(self) -> None:
        diff = _make_diff("cache.py", ["db = shelve.open('data')"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 1

    def test_jsonpickle_decode(self) -> None:
        diff = _make_diff("api.py", ["obj = jsonpickle.decode(payload)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 1

    def test_dill_loads(self) -> None:
        diff = _make_diff("ml.py", ["model = dill.loads(blob)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 1

    def test_torch_load_unsafe(self) -> None:
        diff = _make_diff("model.py", ["m = torch.load('model.pt')"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 1

    def test_torch_load_safe(self) -> None:
        diff = _make_diff("model.py", ["m = torch.load('model.pt', weights_only=True)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 0

    def test_comment_ignored(self) -> None:
        diff = _make_diff("app.py", ["# data = yaml.load(raw)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 0

    def test_non_python_ignored(self) -> None:
        diff = _make_diff("app.js", ["const data = YAML.load(raw)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 0

    def test_rule_metadata(self) -> None:
        rule = InsecureDeserializationRule()
        assert rule.id == "insecure-deserialization"
        assert rule.default_severity == RuleSeverity.ERROR


# -- Timeout helper for ReDoS tests ------------------------------------------


@contextmanager
def _timeout(seconds: int) -> Generator[None, None, None]:
    """Raise TimeoutError if block takes longer than *seconds*."""

    def _handler(signum: int, frame: object) -> None:
        msg = f"ReDoS timeout: regex took >{seconds}s"
        raise TimeoutError(msg)

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# -- SR-02: ReDoS safety tests -----------------------------------------------


class TestDeserReDoS:
    def test_redos_shelve_pattern(self) -> None:
        """100K-char adversarial input against shelve pattern completes quickly."""
        adversarial = "shelve.open(" + "x" * 100_000 + ")"
        _, pattern = _DESER_PATTERNS[0]
        with _timeout(5):
            pattern.search(adversarial)

    def test_extremely_long_line(self) -> None:
        """>1MB added line through full rule.run() produces no crash or findings."""
        long_line = "x" * 1_100_000
        diff = _make_diff("app.py", [long_line])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert results == []


# -- SR-01: Pattern coverage tests (closes untested entries) ------------------


class TestDeserPatternCoverage:
    def test_cloudpickle_loads(self) -> None:
        diff = _make_diff("ml.py", ["obj = cloudpickle.loads(blob)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 1
        assert "cloudpickle" in results[0].message

    def test_dill_load_singular(self) -> None:
        """dill.load (file-based, not just dill.loads) should be flagged."""
        diff = _make_diff("ml.py", ["model = dill.load(f)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 1
        assert "dill" in results[0].message


# -- SR-09: Safe-negative specificity anchors ---------------------------------


class TestDeserSafeNegatives:
    def test_json_loads_safe(self) -> None:
        """json.loads is safe deserialization — should NOT be flagged."""
        diff = _make_diff("api.py", ["data = json.loads(response.text)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert results == []

    def test_pickle_loads_not_this_rule(self) -> None:
        """pickle.loads is owned by rule-sinks, not this rule."""
        diff = _make_diff("app.py", ["obj = pickle.loads(blob)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert results == []


class TestDeserEdgeCaseFixtures:
    """Edge-case fixture categories for insecure deserialization rule."""

    def test_binary_diff_no_crash(self) -> None:
        """Binary file diffs produce no results and no crash."""
        diff = (
            "diff --git a/image.png b/image.png\n"
            "new file mode 100644\n"
            "index 0000000..abcdef1\n"
            "Binary files /dev/null and b/image.png differ\n"
        )
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert results == []

    def test_renamed_file_still_scanned(self) -> None:
        """Insecure deserialization in renamed files is still detected."""
        diff = (
            "diff --git a/old_store.py b/new_store.py\n"
            "similarity index 90%\n"
            "rename from old_store.py\n"
            "rename to new_store.py\n"
            "--- a/old_store.py\n"
            "+++ b/new_store.py\n"
            "@@ -1,1 +1,2 @@\n"
            " existing\n"
            "+db = shelve.open('data')\n"
        )
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_deleted_line_not_flagged(self) -> None:
        """Removed deserialization lines should not trigger findings."""
        diff = (
            "diff --git a/app.py b/app.py\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,1 @@\n"
            "-db = shelve.open('data')\n"
            " other = True\n"
        )
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert results == []
