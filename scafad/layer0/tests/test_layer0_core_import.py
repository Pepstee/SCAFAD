"""
T-026b -- Layer 0 core import-safety regression (Phase 1, ADR-4)
=================================================================

Permanent regression guard for the module-level ``logger`` ordering bug in
``scafad/layer0/layer0_core.py`` (Risk R1 in plan_c33fece9-*.md).

Historical bug
--------------
``layer0_core.py`` imported ``formal_memory_bounds_analysis`` inside a
``try/except ImportError`` block and called ``logger.warning(...)`` from the
``except`` branch.  The module-level ``logger = logging.getLogger(__name__)``
assignment lived *below* that block, so if the optional dependency was
unavailable (or surfaced as an ImportError for any reason) importing
``layer0_core`` raised ``NameError: name 'logger' is not defined`` and took
the entire Layer-0 boot path down with it.

What this test does
-------------------
1. Purge every cached ``layer0_core`` and ``formal_memory_bounds_analysis``
   module key (bare, ``scafad.layer0.*``, and ``layer0.*`` variants).
2. Install a ``sys.meta_path`` finder that forces
   ``formal_memory_bounds_analysis`` to look unavailable (raises
   ``ImportError`` on any attempt to import it).  This is the same failure
   mode the original bug walked into.
3. Re-import ``layer0_core`` from a clean module cache and assert that
   (a) no ``NameError`` is raised, and
   (b) ``MEMORY_BOUNDS_AVAILABLE`` is ``False`` -- proving the fallback
       branch actually executed, i.e. we really exercised the path that
       used to crash.
4. Always restore the original ``sys.meta_path`` / ``sys.modules`` state
   in a ``finally`` so the rest of the test session is unaffected.

DL: Phase 1 (task ccd6f772-05b4-48d5-8f23-3c616974a599) -- initial guard.
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
import unittest
from typing import List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FMBA_BASENAMES = (
    "formal_memory_bounds_analysis",
    "layer0.formal_memory_bounds_analysis",
    "scafad.layer0.formal_memory_bounds_analysis",
)

_L0_CORE_BASENAMES = (
    "layer0_core",
    "layer0.layer0_core",
    "scafad.layer0.layer0_core",
)


class _BlockFMBAFinder(importlib.abc.MetaPathFinder):
    """A ``sys.meta_path`` finder that makes ``formal_memory_bounds_analysis``
    look unavailable by raising ``ImportError`` whenever it is looked up.

    We raise from ``find_spec`` rather than returning ``None`` so that no
    other finder (the regular path-based importer, pkgutil namespace
    finders, the ``conftest.py`` alias loader, etc.) can satisfy the
    import behind our back.
    """

    _TARGETS = frozenset(_FMBA_BASENAMES)

    def find_spec(
        self,
        fullname: str,
        path: object = None,  # noqa: ARG002
        target: object = None,  # noqa: ARG002
    ) -> Optional[importlib.machinery.ModuleSpec]:
        if fullname in self._TARGETS:
            raise ImportError(
                f"formal_memory_bounds_analysis is forcibly unavailable "
                f"(blocked by {type(self).__name__} during "
                f"test_layer0_core_import)"
            )
        return None


def _purge(names: "tuple[str, ...]") -> "dict[str, object]":
    """Remove ``names`` from ``sys.modules`` and return what was evicted so
    it can be restored in a finally block."""
    evicted: "dict[str, object]" = {}
    for name in names:
        if name in sys.modules:
            evicted[name] = sys.modules.pop(name)
    return evicted


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLayer0CoreImportSafety(unittest.TestCase):
    """Phase-1 invariant: ``layer0_core`` must import even when its optional
    ``formal_memory_bounds_analysis`` dependency is unavailable."""

    def setUp(self) -> None:
        # Snapshot state we are about to mutate.
        self._saved_meta_path: List[importlib.abc.MetaPathFinder] = list(
            sys.meta_path
        )
        self._evicted_fmba = _purge(_FMBA_BASENAMES)
        self._evicted_core = _purge(_L0_CORE_BASENAMES)

        # Install the blocker at the head of the meta-path so it wins over
        # every other finder (including the conftest alias hook).
        self._blocker = _BlockFMBAFinder()
        sys.meta_path.insert(0, self._blocker)

    def tearDown(self) -> None:
        # Restore meta_path first so subsequent imports behave normally.
        sys.meta_path[:] = self._saved_meta_path

        # Purge anything the test pulled in under the block, then restore
        # pre-test entries.  This keeps other tests in the same session
        # seeing a clean, unfrozen ``layer0_core``.
        _purge(_L0_CORE_BASENAMES)
        _purge(_FMBA_BASENAMES)
        for name, mod in self._evicted_fmba.items():
            sys.modules[name] = mod
        for name, mod in self._evicted_core.items():
            sys.modules[name] = mod

    def test_import_succeeds_when_formal_memory_bounds_unavailable(self) -> None:
        """Importing ``scafad.layer0.layer0_core`` must not raise NameError
        (or anything else) when the optional dependency is missing."""
        try:
            layer0_core = importlib.import_module("scafad.layer0.layer0_core")
        except NameError as exc:  # pragma: no cover - explicit regression signal
            self.fail(
                "Importing scafad.layer0.layer0_core raised NameError when "
                "formal_memory_bounds_analysis was unavailable -- the "
                "module-level logger ordering regression has returned. "
                f"Original error: {exc!r}"
            )
        except Exception as exc:  # pragma: no cover - any other crash is a fail
            self.fail(
                "Importing scafad.layer0.layer0_core raised unexpectedly "
                f"({type(exc).__name__}): {exc!r}"
            )

        # The module object must exist and expose its public engine.
        self.assertIsNotNone(layer0_core)
        self.assertTrue(
            hasattr(layer0_core, "AnomalyDetectionEngine"),
            "layer0_core must still expose AnomalyDetectionEngine after a "
            "fallback import",
        )

        # And we must have genuinely exercised the fallback branch.
        self.assertTrue(
            hasattr(layer0_core, "MEMORY_BOUNDS_AVAILABLE"),
            "layer0_core must export MEMORY_BOUNDS_AVAILABLE",
        )
        self.assertFalse(
            layer0_core.MEMORY_BOUNDS_AVAILABLE,
            "MEMORY_BOUNDS_AVAILABLE must be False when "
            "formal_memory_bounds_analysis is blocked -- otherwise the "
            "regression path under test was never entered",
        )

    def test_logger_is_configured_before_fallback_branch(self) -> None:
        """Belt-and-braces: after the fallback import the module must expose
        a real ``logging.Logger`` instance at module scope."""
        import logging

        layer0_core = importlib.import_module("scafad.layer0.layer0_core")
        self.assertTrue(
            hasattr(layer0_core, "logger"),
            "layer0_core must define a module-level `logger`",
        )
        self.assertIsInstance(
            layer0_core.logger,
            logging.Logger,
            "layer0_core.logger must be a logging.Logger instance",
        )


if __name__ == "__main__":
    unittest.main()
