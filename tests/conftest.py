from __future__ import annotations

import asyncio
import importlib
import importlib.abc
import importlib.machinery
import inspect
import sys
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = ROOT.parent
SCAFAD_PKG: Final = REPO_ROOT / "scafad"

# Add repo root first so `scafad.*` absolute imports resolve.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Add scafad/ so intra-package imports used by scafad/runtime/runtime.py
# (e.g. `from layer0.telemetry import ...`) also resolve when tests are
# collected from the repo-root tests/ directory (DL-039).
if str(SCAFAD_PKG) not in sys.path:
    sys.path.insert(1, str(SCAFAD_PKG))


# ---------------------------------------------------------------------------
# Namespace-alias hook: prevent dual module identity (DL-040)
# ---------------------------------------------------------------------------
# When both repo root AND scafad/ are on sys.path, Python can load the same
# source file under two keys — e.g. `layer0.app_telemetry` and
# `scafad.layer0.app_telemetry` — producing two distinct class objects.
# isinstance() checks across that boundary fail even though the class name
# and definition are identical.  This finder ensures `scafad.layerX.*`
# imports always resolve to the same module object as the bare `layerX.*`
# counterpart (bare = authoritative, scafad.* = transparent alias).

class _AliasLoader(importlib.abc.Loader):
    """Return an already-initialised module unchanged."""

    def __init__(self, module: object) -> None:
        self._module = module

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> object:  # noqa: ARG002
        return self._module

    def exec_module(self, module: object) -> None:  # noqa: ARG002
        pass  # Already fully initialised as the bare module.


class _ScafadNamespaceAlias(importlib.abc.MetaPathFinder):
    """Redirect ``scafad.layerX[.submod]`` → bare ``layerX[.submod]``.

    Installed once into sys.meta_path[0] before any test import fires.
    The guard ensures idempotent installation across both conftest files
    (DL-040).
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


# Install once; the sentinel lets both conftest files call this safely.
if not any(getattr(f, "_IS_ALIAS_HOOK", False) for f in sys.meta_path):
    sys.meta_path.insert(0, _ScafadNamespaceAlias())


# ---------------------------------------------------------------------------
# Asyncio hook for historical tests that use @pytest.mark.asyncio
# ---------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """Execute asyncio-marked coroutine tests without pytest-asyncio.

    Some of the historical tests rely on ``@pytest.mark.asyncio`` while others
    simply define ``async def`` bodies.  Pytest normally delegates to
    ``pytest-asyncio`` in these scenarios, but the plugin is not available in
    our execution environment.  This hook reproduces the minimal behaviour we
    need by spawning a temporary event loop and executing the coroutine in a
    synchronous context.
    """

    test_func = pyfuncitem.obj
    marker = pyfuncitem.get_closest_marker("asyncio")

    if not inspect.iscoroutinefunction(test_func):
        if marker is None:
            return None
        return None

    loop = asyncio.new_event_loop()
    try:
        previous_loop = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        previous_loop = None

    try:
        asyncio.set_event_loop(loop)

        signature = inspect.signature(test_func)
        accepts_var_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )

        call_kwargs = {}
        for name, value in pyfuncitem.funcargs.items():
            if name in signature.parameters or accepts_var_kwargs:
                call_kwargs[name] = value

        loop.run_until_complete(test_func(**call_kwargs))
    finally:
        asyncio.set_event_loop(previous_loop)
        loop.close()

    return True
