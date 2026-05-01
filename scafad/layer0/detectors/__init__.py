"""
scafad.layer0.detectors
========================

Package containing all 26 SCAFAD anomaly-detection algorithms as
independently testable modules.  Importing this package triggers every
detector module, which in turn registers itself with ``REGISTRY`` via
``REGISTRY.register()`` at module load time.

Algorithm groups (C-1 contribution):
    Statistical (8):  statistical_outlier, isolation_forest,
                      temporal_deviation, correlation_break,
                      seasonal_deviation, trend_change,
                      frequency_anomaly, duration_outlier
    Resource (6):     resource_spike, memory_leak, cpu_burst,
                      io_intensive, network_anomaly, storage_anomaly
    Execution (6):    execution_pattern, cold_start, timeout_pattern,
                      error_clustering, performance_regression,
                      concurrency_anomaly
    Advanced (6):     behavioral_drift, cascade_failure,
                      resource_starvation, security_anomaly,
                      dependency_failure, economic_abuse

WP-3.7: Decomposition of the layer0_core.py monolith.
"""

from layer0.detectors.registry import REGISTRY  # noqa: F401 — re-exported for convenience

# --- Statistical Detection Algorithms (8) ---
from layer0.detectors import statistical_outlier      # noqa: F401
from layer0.detectors import isolation_forest         # noqa: F401
from layer0.detectors import temporal_deviation       # noqa: F401
from layer0.detectors import correlation_break        # noqa: F401
from layer0.detectors import seasonal_deviation       # noqa: F401
from layer0.detectors import trend_change             # noqa: F401
from layer0.detectors import frequency_anomaly        # noqa: F401
from layer0.detectors import duration_outlier         # noqa: F401

# --- Resource-Based Detection Algorithms (6) ---
from layer0.detectors import resource_spike           # noqa: F401
from layer0.detectors import memory_leak              # noqa: F401
from layer0.detectors import cpu_burst                # noqa: F401
from layer0.detectors import io_intensive             # noqa: F401
from layer0.detectors import network_anomaly          # noqa: F401
from layer0.detectors import storage_anomaly          # noqa: F401

# --- Execution Pattern Algorithms (6) ---
from layer0.detectors import execution_pattern        # noqa: F401
from layer0.detectors import cold_start               # noqa: F401
from layer0.detectors import timeout_pattern          # noqa: F401
from layer0.detectors import error_clustering         # noqa: F401
from layer0.detectors import performance_regression   # noqa: F401
from layer0.detectors import concurrency_anomaly      # noqa: F401

# --- Advanced Detection Algorithms (6) ---
from layer0.detectors import behavioral_drift         # noqa: F401
from layer0.detectors import cascade_failure          # noqa: F401
from layer0.detectors import resource_starvation      # noqa: F401
from layer0.detectors import security_anomaly         # noqa: F401
from layer0.detectors import dependency_failure       # noqa: F401
from layer0.detectors import economic_abuse           # noqa: F401

__all__ = ["REGISTRY"]
