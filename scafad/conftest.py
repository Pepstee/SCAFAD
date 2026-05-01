"""
scafad/conftest.py — path bootstrap + namespace-alias hook (DL-041)
====================================================================

This conftest fires when pytest is invoked with ``scafad/`` as rootdir
(e.g. ``python -m pytest scafad -q`` from repo root, or
``python -m pytest .`` from inside scafad/).

It mirrors the repo-root conftest.py (DL-040) so that the bare-import
test suites (T-013..T-027) work correctly regardless of invocation path.

Why both files exist
--------------------
``pytest.ini`` in ``scafad/`` takes precedence over the repo-root
``pytest.ini`` when pytest is invoked with a ``scafad/``-relative path.
When ``scafad/pytest.ini`` wins, rootdir becomes ``scafad/`` and the
repo-root ``conftest.py`` is outside rootdir — it is NOT loaded.
This file fills that gap.

Dual-identity prevention
------------------------
``pythonpath = . ..`` in ``scafad/pytest.ini`` places both ``scafad/``
(bare imports) and the repo root (``scafad.*`` absolute imports) on
sys.path.  Without the alias hook the same source file can be loaded
under two keys, breaking ``isinstance()`` checks.  The
``_ScafadNamespaceAlias`` finder fixes this by making ``scafad.layerX.*``
a transparent alias for the bare ``layerX.*`` module object.
"""
from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path bootstrap (belt-and-braces; pytest pythonpath handles this too)
# ---------------------------------------------------------------------------

_SCAFAD_DIR = Path(__file__).resolve().parent      # …/scafad-r-core/scafad/
_REPO_ROOT = _SCAFAD_DIR.parent                    # …/scafad-r-core/

for _p in (_SCAFAD_DIR, _REPO_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)


# ---------------------------------------------------------------------------
# Namespace-alias hook: prevent dual module identity (DL-040 / DL-041)
# ---------------------------------------------------------------------------

class _AliasLoader(importlib.abc.Loader):
    """Return an already-initialised module unchanged."""

    def __init__(self, module: object) -> None:
        self._module = module

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> object:  # noqa: ARG002
        return self._module

    def exec_module(self, module: object) -> None:  # noqa: ARG002
        pass  # Already fully initialised as the bare module.


class _ScafadNamespaceAlias(importlib.abc.MetaPathFinder):
    """Redirect ``scafad.layerX[.submod]`` imports to their bare equivalents.

    Ensures ``from scafad.layer0 import TelemetryRecord`` and
    ``from layer0.app_telemetry import TelemetryRecord`` resolve to the same
    class object, fixing the dual-identity ``isinstance`` failure.
    """

    _IS_ALIAS_HOOK = True  # sentinel for idempotency guard
    _PREFIX = "scafad."
    _LAYERS = frozenset(
        ["layer0", "layer1", "layer2", "layer3",
         "layer4", "layer5", "layer6", "runtime"]
    )

    def find_spec(
        self,
        fullname: str,
        path: object,  # noqa: ARG002
        target: object = None,  # noqa: ARG002
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(self._PREFIX):
            return None
        rest = fullname[len(self._PREFIX):]   # e.g. "layer0" or "layer0.app_telemetry"
        top_layer = rest.split(".")[0]
        if top_layer not in self._LAYERS:
            return None
        if fullname in sys.modules:
            return None  # already aliased

        # Ensure the bare module is present.
        if rest not in sys.modules:
            try:
                importlib.import_module(rest)
            except ImportError:
                return None

        bare_mod = sys.modules.get(rest)
        if bare_mod is None:
            return None

        # Register the alias immediately so dotted sub-imports also resolve.
        sys.modules[fullname] = bare_mod
        spec = importlib.machinery.ModuleSpec(fullname, _AliasLoader(bare_mod))
        spec.submodule_search_locations = getattr(bare_mod, "__path__", None)
        return spec


# Install once; the sentinel ensures idempotent installation if multiple
# conftest files are loaded in the same pytest session.
if not any(getattr(f, "_IS_ALIAS_HOOK", False) for f in sys.meta_path):
    sys.meta_path.insert(0, _ScafadNamespaceAlias())
