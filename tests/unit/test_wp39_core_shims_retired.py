"""
WP-3.9 — Retire legacy core shims (core/*.py)
==============================================

Tests verifying that the four retired compatibility shims are gone and that
their canonical replacements work correctly.

Shims retired by WP-3.9:
    - core/layer1_pipeline.py        → layer1.pipeline
    - core/r_core_to_layer1_adapter.py → layer0.adapter
    - core/layer2_detection_matrix.py → layer2.detection_matrix
    - core/multilayer_pipeline.py    → runtime.pipeline

Invariants enforced:
    1. Retired shim files do NOT exist on disk.
    2. Retired shim modules are NOT importable (raise ImportError/ModuleNotFoundError).
    3. Canonical replacement modules ARE importable.
    4. Key public symbols from each canonical module are accessible.
    5. test_006_e2e_integration.py uses canonical import paths (not shim paths).
    6. test_core_shims.py SHIM_PAIRS does not contain the retired shim names.
    7. core/__init__.py still exists (other non-shim modules remain in core/).
    8. Remaining L3-L6 shims are still present in core/.
"""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]   # .../project/scafad-r-core
_CORE_DIR = _REPO_ROOT / "core"


def _file_exists(relative: str) -> bool:
    return (_REPO_ROOT / relative).exists()


# ---------------------------------------------------------------------------
# 1. Retired shim FILES must not exist on disk
# ---------------------------------------------------------------------------

RETIRED_SHIM_FILES = [
    "core/layer1_pipeline.py",
    "core/r_core_to_layer1_adapter.py",
    "core/layer2_detection_matrix.py",
    "core/multilayer_pipeline.py",
]


@pytest.mark.parametrize("path", RETIRED_SHIM_FILES)
def test_retired_shim_file_does_not_exist_on_disk(path: str) -> None:
    """WP-3.9: retired shim files must be absent from the repository."""
    assert not _file_exists(path), (
        f"Retired shim {path!r} still exists on disk — WP-3.9 deletion did not succeed"
    )


# ---------------------------------------------------------------------------
# 2. Retired shim MODULE NAMES must not be importable
# ---------------------------------------------------------------------------

RETIRED_SHIM_MODULES = [
    "core.layer1_pipeline",
    "core.r_core_to_layer1_adapter",
    "core.layer2_detection_matrix",
    "core.multilayer_pipeline",
]


@pytest.mark.parametrize("module_name", RETIRED_SHIM_MODULES)
def test_retired_shim_module_not_importable(module_name: str) -> None:
    """WP-3.9: retired shim modules must raise ImportError / ModuleNotFoundError."""
    with pytest.raises((ImportError, ModuleNotFoundError)):
        importlib.import_module(module_name)


# ---------------------------------------------------------------------------
# 3. Canonical replacement MODULES must still be importable
# ---------------------------------------------------------------------------

CANONICAL_MODULES = [
    "layer1.pipeline",
    "layer0.adapter",
    "layer2.detection_matrix",
    "runtime.pipeline",
]


@pytest.mark.parametrize("module_name", CANONICAL_MODULES)
def test_canonical_module_importable(module_name: str) -> None:
    """WP-3.9: canonical replacement modules must import without error."""
    mod = importlib.import_module(module_name)
    assert mod is not None, f"{module_name!r} import returned None"


# ---------------------------------------------------------------------------
# 4. Key public symbols from canonical modules are accessible
# ---------------------------------------------------------------------------

def test_layer1_pipeline_exports_Layer1CanonicalPipeline() -> None:
    """layer1.pipeline must expose Layer1CanonicalPipeline (the shim's only export)."""
    mod = importlib.import_module("layer1.pipeline")
    assert hasattr(mod, "Layer1CanonicalPipeline"), (
        "layer1.pipeline does not expose Layer1CanonicalPipeline"
    )
    # Must be a class (or at least callable)
    cls = mod.Layer1CanonicalPipeline
    assert callable(cls), "Layer1CanonicalPipeline is not callable"


def test_layer0_adapter_exports_RCoreToLayer1Adapter() -> None:
    """layer0.adapter must expose RCoreToLayer1Adapter (the shim's only export)."""
    mod = importlib.import_module("layer0.adapter")
    assert hasattr(mod, "RCoreToLayer1Adapter"), (
        "layer0.adapter does not expose RCoreToLayer1Adapter"
    )
    cls = mod.RCoreToLayer1Adapter
    assert callable(cls), "RCoreToLayer1Adapter is not callable"


def test_layer2_detection_matrix_has_public_symbols() -> None:
    """layer2.detection_matrix must be a non-empty module (not a blank stub)."""
    mod = importlib.import_module("layer2.detection_matrix")
    public = [n for n in dir(mod) if not n.startswith("_")]
    assert public, "layer2.detection_matrix exposes no public symbols"


def test_runtime_pipeline_has_public_symbols() -> None:
    """runtime.pipeline must be a non-empty module (not a blank stub)."""
    mod = importlib.import_module("runtime.pipeline")
    public = [n for n in dir(mod) if not n.startswith("_")]
    assert public, "runtime.pipeline exposes no public symbols"


# ---------------------------------------------------------------------------
# 5. test_006_e2e_integration.py uses canonical imports, not shim paths
# ---------------------------------------------------------------------------

_TEST_006_PATH = _REPO_ROOT / "tests" / "test_006_e2e_integration.py"


def test_test_006_does_not_import_from_core_layer1_pipeline() -> None:
    """test_006 must not import from the retired core.layer1_pipeline shim."""
    if not _TEST_006_PATH.exists():
        pytest.skip("test_006_e2e_integration.py not found")
    content = _TEST_006_PATH.read_text(encoding="utf-8")
    assert "core.layer1_pipeline" not in content, (
        "test_006_e2e_integration.py still imports from retired core.layer1_pipeline"
    )
    assert "from core.layer1_pipeline" not in content


def test_test_006_does_not_import_from_core_r_core_to_layer1_adapter() -> None:
    """test_006 must not import from the retired core.r_core_to_layer1_adapter shim."""
    if not _TEST_006_PATH.exists():
        pytest.skip("test_006_e2e_integration.py not found")
    content = _TEST_006_PATH.read_text(encoding="utf-8")
    assert "core.r_core_to_layer1_adapter" not in content, (
        "test_006_e2e_integration.py still imports from retired core.r_core_to_layer1_adapter"
    )


def test_test_006_uses_canonical_layer1_pipeline_import() -> None:
    """test_006 must import Layer1CanonicalPipeline from the canonical layer1.pipeline path."""
    if not _TEST_006_PATH.exists():
        pytest.skip("test_006_e2e_integration.py not found")
    content = _TEST_006_PATH.read_text(encoding="utf-8")
    assert "from layer1.pipeline import Layer1CanonicalPipeline" in content, (
        "test_006 does not use canonical 'from layer1.pipeline import Layer1CanonicalPipeline'"
    )


def test_test_006_uses_canonical_adapter_import() -> None:
    """test_006 must import RCoreToLayer1Adapter from the canonical layer0.adapter path."""
    if not _TEST_006_PATH.exists():
        pytest.skip("test_006_e2e_integration.py not found")
    content = _TEST_006_PATH.read_text(encoding="utf-8")
    assert "from layer0.adapter import RCoreToLayer1Adapter" in content, (
        "test_006 does not use canonical 'from layer0.adapter import RCoreToLayer1Adapter'"
    )


# ---------------------------------------------------------------------------
# 6. test_core_shims.py SHIM_PAIRS must not contain retired pairs
# ---------------------------------------------------------------------------

_SHIM_CONTRACT_PATH = _REPO_ROOT / "tests" / "contract" / "test_core_shims.py"

RETIRED_SHIM_NAMES_IN_PAIRS = [
    "core.layer1_pipeline",
    "core.r_core_to_layer1_adapter",
    "core.layer2_detection_matrix",
    "core.multilayer_pipeline",
]


@pytest.mark.parametrize("retired_name", RETIRED_SHIM_NAMES_IN_PAIRS)
def test_core_shims_contract_does_not_reference_retired_pair(retired_name: str) -> None:
    """SHIM_PAIRS in test_core_shims.py must not list any retired shim module names."""
    if not _SHIM_CONTRACT_PATH.exists():
        pytest.skip("tests/contract/test_core_shims.py not found")

    # Import the module to inspect SHIM_PAIRS at runtime (most reliable)
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("_test_core_shims_mod", _SHIM_CONTRACT_PATH)
    assert spec is not None and spec.loader is not None
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    shim_pairs = getattr(mod, "SHIM_PAIRS", [])
    listed_shim_names = [pair[0] for pair in shim_pairs]
    assert retired_name not in listed_shim_names, (
        f"SHIM_PAIRS still contains retired shim {retired_name!r} — "
        "WP-3.9 update to test_core_shims.py was incomplete"
    )


# ---------------------------------------------------------------------------
# 7. core/__init__.py still exists (non-shim modules remain in core/)
# ---------------------------------------------------------------------------

def test_core_package_init_still_exists() -> None:
    """core/__init__.py must survive WP-3.9 (other core modules remain)."""
    assert _file_exists("core/__init__.py"), (
        "core/__init__.py was incorrectly deleted — "
        "non-shim modules still live in core/ and need the package init"
    )


# ---------------------------------------------------------------------------
# 8. Remaining L3-L6 shims are still present in core/
# ---------------------------------------------------------------------------

REMAINING_SHIM_FILES = [
    "core/layer3_trust_fusion.py",
    "core/layer4_explainability.py",
    "core/layer5_threat_alignment.py",
    "core/layer6_feedback_learning.py",
]


@pytest.mark.parametrize("path", REMAINING_SHIM_FILES)
def test_remaining_l3_to_l6_shim_still_exists(path: str) -> None:
    """L3-L6 shims were NOT in WP-3.9 scope and must still be on disk."""
    assert _file_exists(path), (
        f"Shim {path!r} was incorrectly deleted — it is not in WP-3.9 scope"
    )


# ---------------------------------------------------------------------------
# 9. core/ non-shim modules are unaffected
# ---------------------------------------------------------------------------

NON_SHIM_CORE_FILES = [
    "core/graph_robustness_analyzer.py",
    "core/ignn_model.py",
    "core/real_graph_analysis.py",
    "core/telemetry_crypto_validator.py",
]


@pytest.mark.parametrize("path", NON_SHIM_CORE_FILES)
def test_non_shim_core_module_still_exists(path: str) -> None:
    """Non-shim core modules must be untouched by WP-3.9."""
    assert _file_exists(path), (
        f"Non-shim module {path!r} was incorrectly deleted by WP-3.9"
    )
