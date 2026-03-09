# SPDX-License-Identifier: MIT
"""Tests for Rule 8: weak-crypto."""

from __future__ import annotations

from grippy.rules.base import RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.weak_crypto import WeakCryptoRule


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


class TestWeakCryptoRule:
    def test_md5_hash(self) -> None:
        diff = _make_diff("auth.py", ["h = hashlib.md5(password.encode())"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1
        assert results[0].severity == RuleSeverity.WARN
        assert "MD5" in results[0].message

    def test_sha1_hash(self) -> None:
        diff = _make_diff("auth.py", ["digest = hashlib.sha1(data).hexdigest()"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1
        assert "SHA1" in results[0].message

    def test_des_cipher(self) -> None:
        diff = _make_diff("crypto.py", ["cipher = DES.new(key, DES.MODE_ECB)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) >= 1

    def test_ecb_mode(self) -> None:
        diff = _make_diff("crypto.py", ["cipher = AES.new(key, AES.MODE_ECB)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1
        assert "ECB" in results[0].message

    def test_random_for_crypto(self) -> None:
        diff = _make_diff("token.py", ["token = random.randint(0, 999999)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1
        assert "random" in results[0].message.lower()

    def test_sha256_safe(self) -> None:
        diff = _make_diff("auth.py", ["h = hashlib.sha256(data).hexdigest()"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 0

    def test_secrets_module_safe(self) -> None:
        diff = _make_diff("token.py", ["token = secrets.token_urlsafe(32)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 0

    def test_non_python_ignored(self) -> None:
        diff = _make_diff("app.js", ["const h = crypto.createHash('md5')"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 0

    def test_comment_ignored(self) -> None:
        diff = _make_diff("auth.py", ["# h = hashlib.md5(password)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 0

    def test_random_sample_flagged(self) -> None:
        diff = _make_diff("token.py", ["chars = random.sample(alphabet, 16)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1

    def test_random_shuffle_flagged(self) -> None:
        diff = _make_diff("token.py", ["random.shuffle(deck)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1

    def test_tests_dir_ignored(self) -> None:
        """Files under tests/ should not trigger weak-crypto findings."""
        diff = _make_diff("tests/test_auth.py", ["h = hashlib.md5(b'test')"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 0

    def test_nested_tests_dir_ignored(self) -> None:
        diff = _make_diff("src/app/tests/conftest.py", ["random.randint(1, 10)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 0

    def test_rule_metadata(self) -> None:
        rule = WeakCryptoRule()
        assert rule.id == "weak-crypto"
        assert rule.default_severity == RuleSeverity.WARN
