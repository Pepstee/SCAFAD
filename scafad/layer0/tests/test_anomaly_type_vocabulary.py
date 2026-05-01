"""
scafad/layer0/tests/test_anomaly_type_vocabulary.py
====================================================

T-030 — `AnomalyType` enum contract-completeness invariant.

Closes the bug class surfaced by the Phase-4 coverage retrofit: production
code referencing `AnomalyType.X` symbols that do not exist in the enum
definition. See `docs/PHASE_4_COVERAGE_AUDIT.md` §8 for the five
missing-member discoveries that motivated this test.

Method: at test time, scan every `*.py` file under `scafad/` (excluding
the test tree itself), extract every `AnomalyType.X` literal via regex,
and assert that each `X` is a member of `AnomalyType`. The test fails
loudly the moment a new dangling reference is added — no tooling, no
linter rule, no CI hook required.

This is a *vocabulary* test, not a *behavioural* test: it does not call
any detector. It checks that the symbols the codebase uses exist. The
companion behavioural tests in `test_layer0_detectors.py` and
`test_layer0_detectors_behavioural.py` exercise the trigger paths that
would otherwise hide the bugs this test catches at lint speed.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from layer0.app_telemetry import AnomalyType


_SCAFAD_ROOT = Path(__file__).resolve().parents[2]  # .../scafad/
_REF_PATTERN = re.compile(r"AnomalyType\.([A-Z][A-Z0-9_]*)")


def _scan_anomaly_type_references() -> dict:
    """Return {symbol_name: [(file, lineno), ...]} for every AnomalyType.X
    reference found anywhere under scafad/ (excluding the tests/ directories
    themselves, which would create a chicken-and-egg situation if a test
    file referenced the very symbol whose absence it was asserting)."""
    refs: dict = {}
    for py in _SCAFAD_ROOT.rglob("*.py"):
        # Skip test directories — they are allowed to reference symbols
        # only via the enum object itself, not via .X dotted access that
        # would pre-empt this scan.
        if "/tests/" in py.as_posix() or "\\tests\\" in str(py):
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in _REF_PATTERN.finditer(line):
                refs.setdefault(m.group(1), []).append((py, lineno))
    return refs


class TestAnomalyTypeVocabularyCompleteness(unittest.TestCase):
    """Every `AnomalyType.X` symbol referenced anywhere in scafad/ must
    correspond to an actual `AnomalyType` enum member."""

    def test_every_reference_resolves_to_an_enum_member(self) -> None:
        defined = {member.name for member in AnomalyType}
        refs = _scan_anomaly_type_references()
        self.assertGreater(
            len(refs), 0,
            "Sanity: scan should find at least one AnomalyType.X reference",
        )
        missing = {sym: sites for sym, sites in refs.items() if sym not in defined}
        if missing:
            details = []
            for sym, sites in sorted(missing.items()):
                first = sites[0]
                details.append(
                    f"  AnomalyType.{sym} — referenced at "
                    f"{first[0].relative_to(_SCAFAD_ROOT.parent)}:{first[1]} "
                    f"(+{len(sites) - 1} more)"
                )
            self.fail(
                "AnomalyType vocabulary contract violated. The following "
                "symbols are used in production code but do not exist in "
                "the AnomalyType enum:\n" + "\n".join(details)
            )

    def test_scan_finds_known_canonical_references(self) -> None:
        """Sanity: the scan must find a handful of well-known references
        (BENIGN, COLD_START, EXECUTION_FAILURE) to prove the regex and
        path-walk are wired correctly. If this assertion fails the scan
        is silently broken and the completeness assertion above is
        meaningless."""
        refs = _scan_anomaly_type_references()
        for canonical in ("BENIGN", "COLD_START", "EXECUTION_FAILURE"):
            self.assertIn(
                canonical, refs,
                f"Scan failed to find canonical reference AnomalyType.{canonical}",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
