# SPDX-License-Identifier: MIT
"""Tests for Rule 8: weak-crypto."""

from __future__ import annotations

import signal
from collections.abc import Generator
from contextlib import contextmanager

from grippy.rules.base import RuleSeverity
from grippy.rules.config import PROFILES
from grippy.rules.context import RuleContext, parse_diff
from grippy.rules.weak_crypto import _WEAK_PATTERNS, WeakCryptoRule


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


class TestCryptoReDoS:
    def test_redos_random_pattern(self) -> None:
        """100K-char adversarial input against the random pattern completes quickly."""
        adversarial = "random." + "x" * 100_000
        _, pattern = _WEAK_PATTERNS[6]
        with _timeout(5):
            pattern.search(adversarial)

    def test_extremely_long_line(self) -> None:
        """>1MB added line through full rule.run() produces no crash or findings."""
        long_line = "x" * 1_100_000
        diff = _make_diff("crypto.py", [long_line])
        results = WeakCryptoRule().run(_ctx(diff))
        assert results == []


# -- SR-01: Pattern coverage tests (closes untested entries) ------------------


class TestCryptoPatternCoverage:
    def test_rc4_cipher(self) -> None:
        diff = _make_diff("crypto.py", ["cipher = RC4.new(key)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1
        assert "RC4" in results[0].message

    def test_arc4_cipher(self) -> None:
        diff = _make_diff("crypto.py", ["cipher = ARC4.new(key)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1
        assert "RC4" in results[0].message or "ARC4" in results[0].message

    def test_blowfish_cipher(self) -> None:
        diff = _make_diff("crypto.py", ["cipher = Blowfish.new(key, Blowfish.MODE_ECB)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) >= 1
        assert any("Blowfish" in r.message for r in results)

    def test_random_random(self) -> None:
        diff = _make_diff("token.py", ["x = random.random()"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1

    def test_random_choice(self) -> None:
        diff = _make_diff("token.py", ["c = random.choice(charset)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1

    def test_random_getrandbits(self) -> None:
        diff = _make_diff("token.py", ["bits = random.getrandbits(128)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert len(results) == 1


# -- SR-09: Safe-negative specificity anchors ---------------------------------


class TestCryptoSafeNegatives:
    def test_aes_gcm_safe(self) -> None:
        """Modern AES-GCM should NOT be flagged."""
        diff = _make_diff("crypto.py", ["cipher = AES.new(key, AES.MODE_GCM)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert results == []

    def test_secrets_token_bytes_safe(self) -> None:
        """secrets module should NOT be flagged."""
        diff = _make_diff("crypto.py", ["token = secrets.token_bytes(32)"])
        results = WeakCryptoRule().run(_ctx(diff))
        assert results == []
