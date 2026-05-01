"""
tests/unit/test_wp37_layers_layer0_detectors.py
===============================================

Tests for WP-3.7: layers/layer0/detectors/ re-export shim package.

Coverage:
    - Package importability (layers.layer0, layers.layer0.detectors,
      layers.layer0.detectors.registry)
    - REGISTRY identity: layers shim shares the same singleton as canonical
    - DetectorRegistry / DetectorFn / REGISTRY exportable from registry shim
    - All 26 individual detector shim files export `detect`
    - Each shim's `detect` is the *same function object* as the canonical one
    - Importing layers.layer0.detectors triggers all 26 registrations
    - AnomalyDetectionEngine._register_algorithms delegates to DetectorRegistry
    - I-9 invariant: normalised algorithm weights sum to 1.0

Task: b195f84e-2bd2-4f0a-9563-0dbef4031c4e
Source: 1c04ea3e-126e-4b68-8208-ad2fd7470a2e
"""
from __future__ import annotations

import importlib
import inspect
import unittest


# ---------------------------------------------------------------------------
# Canonical names — these must stay in sync with scafad/layer0/detectors/
# ---------------------------------------------------------------------------
_ALL_DETECTOR_NAMES = [
    "statistical_outlier",
    "isolation_forest",
    "temporal_deviation",
    "correlation_break",
    "seasonal_deviation",
    "trend_change",
    "frequency_anomaly",
    "duration_outlier",
    "resource_spike",
    "memory_leak",
    "cpu_burst",
    "io_intensive",
    "network_anomaly",
    "storage_anomaly",
    "execution_pattern",
    "cold_start",
    "timeout_pattern",
    "error_clustering",
    "performance_regression",
    "concurrency_anomaly",
    "behavioral_drift",
    "cascade_failure",
    "resource_starvation",
    "security_anomaly",
    "dependency_failure",
    "economic_abuse",
]

assert len(_ALL_DETECTOR_NAMES) == 26, "Expected exactly 26 detector names"


# ===========================================================================
# Suite 1 — Package importability
# ===========================================================================

class TestPackageImportability(unittest.TestCase):
    """layers.layer0, layers.layer0.detectors, and the registry shim must all import."""

    def test_layers_layer0_package_importable(self):
        """layers.layer0 must be importable as a package."""
        mod = importlib.import_module("layers.layer0")
        self.assertIsNotNone(mod)

    def test_layers_layer0_detectors_package_importable(self):
        """layers.layer0.detectors must be importable as a package."""
        mod = importlib.import_module("layers.layer0.detectors")
        self.assertIsNotNone(mod)

    def test_layers_layer0_detectors_registry_importable(self):
        """layers.layer0.detectors.registry must be importable as a module."""
        mod = importlib.import_module("layers.layer0.detectors.registry")
        self.assertIsNotNone(mod)

    def test_layers_layer0_has_no_import_errors(self):
        """Importing the whole layers.layer0 namespace must not raise any exception."""
        try:
            import layers.layer0  # noqa: F401
            import layers.layer0.detectors  # noqa: F401
            import layers.layer0.detectors.registry  # noqa: F401
        except Exception as exc:
            self.fail(f"Unexpected import error: {exc}")


# ===========================================================================
# Suite 2 — REGISTRY identity via layers.layer0.detectors
# ===========================================================================

class TestRegistryIdentity(unittest.TestCase):
    """The REGISTRY object in the shim namespace must be the same singleton as
    the canonical registry, ensuring all registrations are visible to the engine."""

    def _canonical_registry(self):
        from layer0.detectors.registry import REGISTRY
        return REGISTRY

    def test_registry_exported_from_detectors_package(self):
        """layers.layer0.detectors must export REGISTRY."""
        import layers.layer0.detectors as shim_pkg
        self.assertTrue(hasattr(shim_pkg, "REGISTRY"),
                        "REGISTRY not found on layers.layer0.detectors")

    def test_registry_is_same_singleton_as_canonical(self):
        """layers.layer0.detectors.REGISTRY must be the canonical REGISTRY singleton."""
        import layers.layer0.detectors as shim_pkg
        from layer0.detectors.registry import REGISTRY as canonical
        self.assertIs(shim_pkg.REGISTRY, canonical,
                      "layers.layer0.detectors.REGISTRY is a different object than the canonical REGISTRY")


# ===========================================================================
# Suite 3 — registry.py shim exports
# ===========================================================================

class TestRegistryShimExports(unittest.TestCase):
    """layers.layer0.detectors.registry must export DetectorRegistry, DetectorFn,
    and REGISTRY — and they must be the same objects as the canonical ones."""

    def _canonical(self):
        import layer0.detectors.registry as canon
        return canon

    def test_DetectorRegistry_exported(self):
        """layers.layer0.detectors.registry must export DetectorRegistry."""
        mod = importlib.import_module("layers.layer0.detectors.registry")
        self.assertTrue(hasattr(mod, "DetectorRegistry"))

    def test_DetectorFn_exported(self):
        """layers.layer0.detectors.registry must export DetectorFn."""
        mod = importlib.import_module("layers.layer0.detectors.registry")
        self.assertTrue(hasattr(mod, "DetectorFn"))

    def test_REGISTRY_exported_from_registry_module(self):
        """layers.layer0.detectors.registry must export REGISTRY."""
        mod = importlib.import_module("layers.layer0.detectors.registry")
        self.assertTrue(hasattr(mod, "REGISTRY"))

    def test_DetectorRegistry_is_same_class(self):
        """DetectorRegistry from shim must be the identical class object."""
        from layers.layer0.detectors.registry import DetectorRegistry as shim_cls
        from layer0.detectors.registry import DetectorRegistry as canon_cls
        self.assertIs(shim_cls, canon_cls)

    def test_REGISTRY_is_same_singleton(self):
        """REGISTRY from registry.py shim must be the canonical singleton."""
        from layers.layer0.detectors.registry import REGISTRY as shim_reg
        from layer0.detectors.registry import REGISTRY as canon_reg
        self.assertIs(shim_reg, canon_reg)

    def test_DetectorRegistry_has_expected_interface(self):
        """DetectorRegistry from the shim must expose register/items/names/default_weights."""
        from layers.layer0.detectors.registry import DetectorRegistry
        instance = DetectorRegistry.__new__(DetectorRegistry)
        for method in ("register", "items", "names", "default_weights"):
            self.assertTrue(
                hasattr(DetectorRegistry, method),
                f"DetectorRegistry missing expected method: {method}",
            )


# ===========================================================================
# Suite 4 — Individual detector shim files
# ===========================================================================

class TestDetectorShimFiles(unittest.TestCase):
    """Each of the 26 detector shim files must be importable and export `detect`."""

    def _shim_module_name(self, name: str) -> str:
        return f"layers.layer0.detectors.{name}"

    def _canon_module_name(self, name: str) -> str:
        return f"layer0.detectors.{name}"

    def test_all_shim_modules_importable(self):
        """Every detector shim module must import without error."""
        for name in _ALL_DETECTOR_NAMES:
            with self.subTest(detector=name):
                try:
                    mod = importlib.import_module(self._shim_module_name(name))
                    self.assertIsNotNone(mod)
                except ImportError as exc:
                    self.fail(f"Could not import {self._shim_module_name(name)}: {exc}")

    def test_all_shim_modules_export_detect(self):
        """Every detector shim module must export a callable named `detect`."""
        for name in _ALL_DETECTOR_NAMES:
            with self.subTest(detector=name):
                mod = importlib.import_module(self._shim_module_name(name))
                self.assertTrue(
                    hasattr(mod, "detect"),
                    f"{self._shim_module_name(name)} does not export 'detect'",
                )
                self.assertTrue(
                    callable(mod.detect),
                    f"{self._shim_module_name(name)}.detect is not callable",
                )

    def test_shim_detect_is_same_function_as_canonical(self):
        """Each shim's `detect` must be the *same function object* as the canonical one.

        This verifies the shim is a pure re-export and not a copy/wrapper, so
        callers using either import path get the same implementation.
        """
        for name in _ALL_DETECTOR_NAMES:
            with self.subTest(detector=name):
                shim_mod = importlib.import_module(self._shim_module_name(name))
                canon_mod = importlib.import_module(self._canon_module_name(name))
                self.assertIs(
                    shim_mod.detect,
                    canon_mod.detect,
                    f"layers.layer0.detectors.{name}.detect is not the same object as "
                    f"layer0.detectors.{name}.detect",
                )

    def test_all_shims_have_all_attr(self):
        """Every shim must declare __all__ containing at least 'detect'."""
        for name in _ALL_DETECTOR_NAMES:
            with self.subTest(detector=name):
                mod = importlib.import_module(self._shim_module_name(name))
                self.assertTrue(
                    hasattr(mod, "__all__"),
                    f"{self._shim_module_name(name)} is missing __all__",
                )
                self.assertIn(
                    "detect",
                    mod.__all__,
                    f"'detect' not in __all__ of {self._shim_module_name(name)}",
                )

    def test_shim_count_is_26(self):
        """Exactly 26 detector shim modules must exist under layers.layer0.detectors."""
        self.assertEqual(len(_ALL_DETECTOR_NAMES), 26)
        importable = []
        for name in _ALL_DETECTOR_NAMES:
            try:
                importlib.import_module(f"layers.layer0.detectors.{name}")
                importable.append(name)
            except ImportError:
                pass
        self.assertEqual(
            len(importable),
            26,
            f"Expected 26 importable detector shims, found {len(importable)}: "
            f"missing={set(_ALL_DETECTOR_NAMES) - set(importable)}",
        )


# ===========================================================================
# Suite 5 — REGISTRY population via layers import
# ===========================================================================

class TestRegistryPopulation(unittest.TestCase):
    """Importing layers.layer0.detectors must trigger all 26 registrations so the
    REGISTRY contains exactly 26 entries (the canonical modules did registrations
    at import time; we verify the count via the shim path)."""

    def test_registry_has_26_detectors_after_import(self):
        """After importing layers.layer0.detectors, REGISTRY must have exactly 26 entries."""
        import layers.layer0.detectors  # triggers all 26 REGISTRY.register() calls
        from layer0.detectors.registry import REGISTRY
        self.assertEqual(
            len(REGISTRY),
            26,
            f"Expected 26 detectors in REGISTRY, found {len(REGISTRY)}: {REGISTRY.names()}",
        )

    def test_registry_names_match_expected_list(self):
        """REGISTRY must contain exactly the 26 expected algorithm names."""
        import layers.layer0.detectors  # noqa: F401
        from layer0.detectors.registry import REGISTRY
        registered = set(REGISTRY.names())
        expected = set(_ALL_DETECTOR_NAMES)
        self.assertEqual(
            registered,
            expected,
            f"Registry mismatch. Extra: {registered - expected}, Missing: {expected - registered}",
        )

    def test_registry_all_detectors_have_positive_weight(self):
        """Every registered detector must have a positive default weight in [0, 1]."""
        import layers.layer0.detectors  # noqa: F401
        from layer0.detectors.registry import REGISTRY
        weights = REGISTRY.default_weights()
        for name, w in weights.items():
            with self.subTest(detector=name):
                self.assertGreater(w, 0.0, f"{name} has zero weight")
                self.assertLessEqual(w, 1.0, f"{name} weight > 1.0")


# ===========================================================================
# Suite 6 — AnomalyDetectionEngine delegation (I-9)
# ===========================================================================

class TestAnomalyDetectionEngineDelegation(unittest.TestCase):
    """AnomalyDetectionEngine._register_algorithms() must delegate to DetectorRegistry.
    It must NOT use an inline dict of hardcoded method references.
    I-9: normalised algorithm_weights must sum to 1.0."""

    def _make_engine(self):
        from layer0.layer0_core import AnomalyDetectionEngine, DetectionConfig
        return AnomalyDetectionEngine(DetectionConfig())

    def test_register_algorithms_returns_26_algorithms(self):
        """_register_algorithms() must return a dict with exactly 26 entries."""
        engine = self._make_engine()
        self.assertEqual(
            len(engine.algorithms),
            26,
            f"Expected 26 algorithms, got {len(engine.algorithms)}: {list(engine.algorithms.keys())}",
        )

    def test_register_algorithms_contains_all_expected_names(self):
        """engine.algorithms must contain all 26 canonical algorithm names."""
        engine = self._make_engine()
        registered = set(engine.algorithms.keys())
        expected = set(_ALL_DETECTOR_NAMES)
        self.assertEqual(
            registered,
            expected,
            f"Algorithm mismatch. Extra: {registered - expected}, Missing: {expected - registered}",
        )

    def test_all_algorithms_are_callable(self):
        """Every value in engine.algorithms must be callable."""
        engine = self._make_engine()
        for name, fn in engine.algorithms.items():
            with self.subTest(algorithm=name):
                self.assertTrue(callable(fn), f"engine.algorithms['{name}'] is not callable")

    def test_i9_weights_sum_to_1(self):
        """I-9: after normalisation, algorithm_weights must sum to 1.0 (within 1e-6 tolerance)."""
        engine = self._make_engine()
        total = sum(engine.config.algorithm_weights.values())
        self.assertAlmostEqual(
            total,
            1.0,
            places=6,
            msg=f"I-9 violated: algorithm_weights sum to {total:.9f}, not 1.0",
        )

    def test_i9_weights_all_non_negative(self):
        """I-9: all normalised weights must be >= 0."""
        engine = self._make_engine()
        for name, w in engine.config.algorithm_weights.items():
            with self.subTest(algorithm=name):
                self.assertGreaterEqual(w, 0.0, f"{name} has negative weight {w}")

    def test_register_algorithms_uses_registry_not_hardcoded_dict(self):
        """_register_algorithms() source must reference REGISTRY — not a hand-coded dict.

        This is a structural guard: the method body must contain the string 'REGISTRY'
        to confirm it reads from DetectorRegistry and not a manually maintained dict.
        """
        from layer0.layer0_core import AnomalyDetectionEngine
        src = inspect.getsource(AnomalyDetectionEngine._register_algorithms)
        self.assertIn(
            "REGISTRY",
            src,
            "_register_algorithms() source does not reference REGISTRY — "
            "it may be using an inline algorithm dict (WP-3.7 regression).",
        )


# ===========================================================================
# Suite 7 — No inline algorithm definitions in layer0_core.py
# ===========================================================================

class TestNoInlineAlgorithms(unittest.TestCase):
    """layer0_core.py must not contain per-algorithm detect() function bodies.
    All algorithm logic must live in the individual detector modules (WP-3.7).
    """

    def _layer0_core_source(self) -> str:
        from layer0 import layer0_core
        return inspect.getsource(layer0_core)

    def test_AnomalyDetectionEngine_does_not_define_inline_algorithms(self):
        """AnomalyDetectionEngine must not define static/instance detect_* methods
        for individual algorithms (those belong in the detector modules).

        We check that none of the 26 canonical algorithm names appear as method
        definitions directly on the class.
        """
        from layer0.layer0_core import AnomalyDetectionEngine
        class_methods = {
            name
            for name, _ in inspect.getmembers(AnomalyDetectionEngine, predicate=inspect.isfunction)
        }
        for algo_name in _ALL_DETECTOR_NAMES:
            with self.subTest(algorithm=algo_name):
                # The method would typically be named detect_<algo> or _detect_<algo>
                self.assertNotIn(
                    f"detect_{algo_name}",
                    class_methods,
                    f"AnomalyDetectionEngine has an inline detect_{algo_name}() — "
                    "this algorithm must live in its own module (WP-3.7).",
                )
                self.assertNotIn(
                    f"_detect_{algo_name}",
                    class_methods,
                    f"AnomalyDetectionEngine has an inline _detect_{algo_name}() — "
                    "this algorithm must live in its own module (WP-3.7).",
                )


if __name__ == "__main__":
    unittest.main()
