"""
T-013 -- Core-shim contract test (Phase 1, ADR-2)
=================================================

Permanent regression guard.  Asserts that every remaining file in
``project/scafad-r-core/core/layer*_*.py`` is a faithful compatibility shim
that re-exports its canonical counterpart under ``scafad/layer*/...`` (or
``scafad/runtime/...``).

Invariants enforced:
    1. The shim module imports successfully.
    2. The canonical module imports successfully.
    3. Every public name in the canonical module's ``__all__`` (or, if no
       ``__all__`` is defined, every non-dunder attribute) is reachable via
       the shim namespace and points to the *same* object (``is``-identity).
    4. If the shim defines ``__all__``, it must be a subset of the canonical
       ``__all__``.

This protects against silent shim drift when a canonical public symbol is
renamed or removed (Risk R2 in plan_c33fece9-*.md).

WP-3.9 update (2026-04-24): Removed four retired shim pairs:
  - core.layer1_pipeline        (retired, callers migrated to layer1.pipeline)
  - core.layer2_detection_matrix (retired, callers migrated to layer2.detection_matrix)
  - core.multilayer_pipeline    (retired, callers migrated to runtime.pipeline)
  - core.r_core_to_layer1_adapter (retired, callers migrated to layer0.adapter)

DL: Phase 1 (task ccd6f772-05b4-48d5-8f23-3c616974a599) -- initial contract.
"""
from __future__ import annotations

import importlib
from typing import Iterable, List, Tuple

import pytest


# ---------------------------------------------------------------------------
# Shim <-> canonical mapping.
#
# Kept in sync with the eight shim files enumerated in the task payload for
# ccd6f772 (Phase 1 of plan_c33fece9).  Any new shim added under ``core/``
# MUST be registered here or this test will silently miss it.
# ---------------------------------------------------------------------------

SHIM_PAIRS: List[Tuple[str, str]] = [
    # WP-3.9 (2026-04-24): layer1_pipeline, layer2_detection_matrix,
    # multilayer_pipeline, r_core_to_layer1_adapter retired — removed from list.
    ("core.layer3_trust_fusion",        "layer3.trust_fusion"),
    ("core.layer4_explainability",      "layer4.explainability"),
    ("core.layer5_threat_alignment",    "layer5.threat_alignment"),
    ("core.layer6_feedback_learning",   "layer6.feedback_learning"),
]


def _public_names(module) -> List[str]:
    """Return the canonical public symbol list for ``module``.

    Prefers ``module.__all__`` when present; otherwise falls back to every
    non-dunder attribute.  The fallback intentionally mirrors what
    ``from module import *`` would pull in when ``__all__`` is absent, so
    the shim assertion logic stays consistent either way.
    """
    explicit = getattr(module, "__all__", None)
    if explicit is not None:
        return list(explicit)
    return [name for name in vars(module) if not name.startswith("_")]


# ---------------------------------------------------------------------------
# Parametrised assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("shim_name,canonical_name", SHIM_PAIRS,
                         ids=[pair[0] for pair in SHIM_PAIRS])
def test_shim_imports_successfully(shim_name: str, canonical_name: str) -> None:
    """Each shim must import without raising."""
    shim = importlib.import_module(shim_name)
    assert shim is not None, f"import_module returned None for {shim_name}"


@pytest.mark.parametrize("shim_name,canonical_name", SHIM_PAIRS,
                         ids=[pair[0] for pair in SHIM_PAIRS])
def test_canonical_imports_successfully(shim_name: str, canonical_name: str) -> None:
    """The canonical target module must also import (sanity for the mapping)."""
    canonical = importlib.import_module(canonical_name)
    assert canonical is not None, f"import_module returned None for {canonical_name}"


@pytest.mark.parametrize("shim_name,canonical_name", SHIM_PAIRS,
                         ids=[pair[0] for pair in SHIM_PAIRS])
def test_shim_reexports_canonical_public_symbols(
    shim_name: str, canonical_name: str,
) -> None:
    """Every canonical public symbol must be reachable via the shim."""
    shim = importlib.import_module(shim_name)
    canonical = importlib.import_module(canonical_name)

    missing: List[str] = []
    mismatched: List[str] = []
    for name in _public_names(canonical):
        if not hasattr(shim, name):
            missing.append(name)
            continue
        if getattr(shim, name) is not getattr(canonical, name):
            mismatched.append(name)

    assert not missing, (
        f"Shim {shim_name} is missing canonical public symbol(s) "
        f"{missing!r} from {canonical_name}"
    )
    assert not mismatched, (
        f"Shim {shim_name} re-exports symbol(s) {mismatched!r} that are NOT "
        f"identical to those in {canonical_name} -- shim has drifted"
    )


@pytest.mark.parametrize("shim_name,canonical_name", SHIM_PAIRS,
                         ids=[pair[0] for pair in SHIM_PAIRS])
def test_shim_all_is_subset_of_canonical_all(
    shim_name: str, canonical_name: str,
) -> None:
    """If the shim declares ``__all__`` it must not introduce new names."""
    shim = importlib.import_module(shim_name)
    canonical = importlib.import_module(canonical_name)

    shim_all = getattr(shim, "__all__", None)
    if shim_all is None:
        pytest.skip(f"{shim_name} does not declare __all__")

    canonical_all = getattr(canonical, "__all__", None)
    canonical_surface: Iterable[str]
    if canonical_all is not None:
        canonical_surface = canonical_all
    else:
        canonical_surface = [n for n in vars(canonical) if not n.startswith("_")]

    extras = sorted(set(shim_all) - set(canonical_surface))
    assert not extras, (
        f"Shim {shim_name}.__all__ exposes name(s) {extras!r} that are not "
        f"part of {canonical_name}'s public surface"
    )
