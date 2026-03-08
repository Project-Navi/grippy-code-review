# SPDX-License-Identifier: MIT
"""Tests for Rule 10: insecure-deserialization."""

from __future__ import annotations

from grippy.rules.base import RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.insecure_deserialization import InsecureDeserializationRule


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
    def test_yaml_unsafe_load(self) -> None:
        diff = _make_diff("config.py", ["data = yaml.load(raw, Loader=yaml.FullLoader)"])
        results = InsecureDeserializationRule().run(_ctx(diff))
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.ERROR

    def test_yaml_safe_load_ok(self) -> None:
        diff = _make_diff("config.py", ["data = yaml.safe_load(raw)"])
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
