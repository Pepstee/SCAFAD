"""
SCAFAD Layer 0 — DetectorRegistry
===================================

Central registration point for all 26 anomaly-detection algorithms.
Each detector module calls ``REGISTRY.register()`` at import time; the
``AnomalyDetectionEngine`` defers-imports this registry inside
``_register_algorithms()`` to avoid circular imports at module load.

WP-3.7: Part of the layer0_core.py decomposition (C-1 contribution).
Invariant I-9: weight-vector normalisation enforced in
``AnomalyDetectionEngine._normalize_algorithm_weights()`` — this registry
stores *default* weights only; the engine normalises at runtime.
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Callable, Dict, Iterator, Tuple

logger = logging.getLogger(__name__)

# Type alias for a detector callable
DetectorFn = Callable  # (telemetry, historical_data, ml_models, config) -> DetectionResult


class DetectorRegistry:
    """
    Registry mapping algorithm names to detector functions and default weights.

    Registration is driven by each detector module at import time via
    ``REGISTRY.register(name, weight, fn)``.  The engine iterates
    ``REGISTRY.items()`` to build its algorithm dispatch table.
    """

    def __init__(self) -> None:
        # Ordered so that iteration order matches registration order,
        # giving deterministic algorithm ordering for reproducibility (I-9).
        self._detectors: OrderedDict[str, Tuple[DetectorFn, float]] = OrderedDict()

    def register(self, name: str, default_weight: float, fn: DetectorFn) -> None:
        """Register a detector function under *name* with *default_weight*.

        Called at module import time by each detector file.  Duplicate
        registration (same name) raises ``ValueError`` to catch accidental
        double-imports early.

        Args:
            name:           Algorithm key, e.g. ``'statistical_outlier'``.
            default_weight: Initial weight ∈ [0, 1].  The engine normalises
                            the full weight vector before use (I-9).
            fn:             Detector callable with signature
                            ``detect(telemetry, historical_data,
                                     ml_models, config) -> DetectionResult``.
        """
        if name in self._detectors:
            raise ValueError(
                f"DetectorRegistry: duplicate registration for '{name}'. "
                "Each detector module must only be imported once."
            )
        if not (0.0 <= default_weight <= 1.0):
            raise ValueError(
                f"DetectorRegistry: default_weight for '{name}' must be in "
                f"[0, 1], got {default_weight!r}."
            )
        self._detectors[name] = (fn, default_weight)
        logger.debug("Registered detector: %s (weight=%.6f)", name, default_weight)

    def items(self) -> Iterator[Tuple[str, Tuple[DetectorFn, float]]]:
        """Iterate over ``(name, (fn, default_weight))`` pairs."""
        return iter(self._detectors.items())

    def names(self) -> list:
        """Return the ordered list of registered algorithm names."""
        return list(self._detectors.keys())

    def default_weights(self) -> Dict[str, float]:
        """Return a ``{name: default_weight}`` mapping."""
        return {name: weight for name, (_, weight) in self._detectors.items()}

    def __len__(self) -> int:
        return len(self._detectors)

    def __contains__(self, name: str) -> bool:
        return name in self._detectors


# Module-level singleton — imported by every detector module and by the engine.
REGISTRY: DetectorRegistry = DetectorRegistry()
