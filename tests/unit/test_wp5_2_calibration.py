"""Tests for WP-5.2: L2 detection threshold calibration.

Tests verify:
1. Calibration script runs and produces correct results
2. Threshold is updated correctly in detection_matrix.py
3. F1-score improves from baseline (0.30 → 0.15)
4. Detection matrix still functions with new threshold
5. Score separation between benign and anomalous records is correct
"""

import json
import re
from pathlib import Path
import pytest
import sys

# Bootstrap path for imports
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAFAD_PKG = _REPO_ROOT / "scafad"
_EVAL_PATH = _REPO_ROOT / "evaluation"

for _p in (str(_REPO_ROOT), str(_SCAFAD_PKG)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from layer2.detection_matrix import MultiVectorDetectionMatrix
from evaluation.calibration.threshold_calibration import (
    calibrate,
    _map_record,
    _compute_metrics,
)


# ============================================================================
# Test Class: Calibration Script Functionality
# ============================================================================

class TestCalibrationScript:
    """Verify the calibrate() public API works correctly."""

    def test_calibration_runs_without_error(self):
        """Test that calibrate() completes successfully."""
        dataset_path = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
        if not dataset_path.exists():
            pytest.skip(f"Dataset not found at {dataset_path}")

        results = calibrate(
            dataset_path=dataset_path,
            output_path=None,  # Don't write to disk in test
            update_source=False,
        )
        assert results is not None
        assert isinstance(results, dict)

    def test_calibration_results_structure(self):
        """Test that calibration results have the expected structure."""
        dataset_path = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
        if not dataset_path.exists():
            pytest.skip(f"Dataset not found at {dataset_path}")

        results = calibrate(
            dataset_path=dataset_path,
            output_path=None,
            update_source=False,
        )

        # Check top-level keys
        assert "calibration_metadata" in results
        assert "score_stats" in results
        assert "baseline" in results
        assert "selected" in results
        assert "improvement" in results
        assert "curve" in results

        # Check metadata
        meta = results["calibration_metadata"]
        assert meta["n_records"] == 6500
        assert meta["n_anomalous"] == 6250
        assert meta["n_benign"] == 250
        assert meta["anomaly_rate"] == 0.9615

        # Check score_stats
        stats = results["score_stats"]
        assert "benign_score_min" in stats
        assert "benign_score_max" in stats
        assert "benign_score_mean" in stats
        assert "anomalous_score_min" in stats
        assert "anomalous_score_max" in stats
        assert "anomalous_score_mean" in stats
        assert "separation_gap" in stats

    def test_selected_threshold_is_valid(self):
        """Test that the selected threshold is a valid float."""
        dataset_path = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
        if not dataset_path.exists():
            pytest.skip(f"Dataset not found at {dataset_path}")

        results = calibrate(
            dataset_path=dataset_path,
            output_path=None,
            update_source=False,
        )

        selected = results["selected"]
        assert "threshold" in selected
        assert isinstance(selected["threshold"], (int, float))
        assert 0.0 <= selected["threshold"] <= 1.0

    def test_f1_improvement_is_positive(self):
        """Test that new threshold improves F1 over baseline 0.30."""
        dataset_path = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
        if not dataset_path.exists():
            pytest.skip(f"Dataset not found at {dataset_path}")

        results = calibrate(
            dataset_path=dataset_path,
            output_path=None,
            update_source=False,
        )

        improvement = results["improvement"]
        assert improvement["f1_delta"] > 0, \
            f"F1 should improve from baseline; got delta {improvement['f1_delta']}"

    def test_baseline_is_computed(self):
        """Test that baseline (0.30) metrics are computed."""
        dataset_path = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
        if not dataset_path.exists():
            pytest.skip(f"Dataset not found at {dataset_path}")

        results = calibrate(
            dataset_path=dataset_path,
            output_path=None,
            update_source=False,
        )

        baseline = results["baseline"]
        assert baseline["threshold"] == 0.30
        assert "precision" in baseline
        assert "recall" in baseline
        assert "f1" in baseline

    def test_score_separation_exists(self):
        """Test that benign and anomalous scores are well separated."""
        dataset_path = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
        if not dataset_path.exists():
            pytest.skip(f"Dataset not found at {dataset_path}")

        results = calibrate(
            dataset_path=dataset_path,
            output_path=None,
            update_source=False,
        )

        stats = results["score_stats"]
        benign_max = stats["benign_score_max"]
        anomalous_min = stats["anomalous_score_min"]
        gap = stats["separation_gap"]

        # Check that anomalous min > benign max (perfect separation)
        assert anomalous_min > benign_max, \
            f"No score separation: benign_max={benign_max}, anomalous_min={anomalous_min}"

        # Check that gap width is reasonable (≥ 0.05)
        assert gap >= 0.05, f"Separation gap too small: {gap}"


# ============================================================================
# Test Class: Metrics Computation
# ============================================================================

class TestMetricsComputation:
    """Verify _compute_metrics() correctness."""

    def test_compute_metrics_perfect_separation(self):
        """Test metrics with perfect classification."""
        scores = [0.1, 0.2, 0.3, 0.9, 0.95]
        labels = [0, 0, 0, 1, 1]
        threshold = 0.5

        tp, fp, fn, p, r, f1 = _compute_metrics(scores, labels, threshold)

        assert tp == 2
        assert fp == 0
        assert fn == 0
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0

    def test_compute_metrics_all_false_positives(self):
        """Test metrics when all positive predictions are wrong."""
        scores = [0.9, 0.95, 0.1, 0.2]
        labels = [0, 0, 1, 1]
        threshold = 0.5

        tp, fp, fn, p, r, f1 = _compute_metrics(scores, labels, threshold)

        assert tp == 0
        assert fp == 2
        assert fn == 2
        assert p == 0.0  # No true positives
        assert r == 0.0  # No true positives
        assert f1 == 0.0

    def test_compute_metrics_all_negatives(self):
        """Test metrics when threshold is very high."""
        scores = [0.1, 0.2, 0.3, 0.4]
        labels = [0, 0, 1, 1]
        threshold = 0.5

        tp, fp, fn, p, r, f1 = _compute_metrics(scores, labels, threshold)

        assert tp == 0
        assert fp == 0
        assert fn == 2


# ============================================================================
# Test Class: Record Mapping
# ============================================================================

class TestRecordMapping:
    """Verify _map_record() translates synthetic records correctly."""

    def test_map_record_benign(self):
        """Test mapping a benign synthetic record."""
        raw = {
            "event_id": "evt_123",
            "anomaly_type": "benign",
            "execution_phase": "initialization",
            "duration": 0.5,  # seconds
            "memory_spike_kb": 100.0,
            "cpu_utilization": 25.5,
            "network_io_bytes": 1000.0,
            "causal_depth": 2,
            "parent_chain": ["parent1", "parent2"],
            "graph_node_id": "node_abc",
            "economic_risk_score": 0.1,
            "silent_failure_probability": 0.05,
            "completeness_score": 0.99,
            "adversarial_score": 0.1,
            "tags": {"category": "legitimate"},
        }

        mapped = _map_record(raw)

        assert mapped["record_id"] == "evt_123"
        assert mapped["anomaly_type"] == "benign"
        assert mapped["execution_phase"] == "initialization"
        assert mapped["telemetry_data"]["l0_duration_ms"] == 500.0
        assert mapped["telemetry_data"]["l0_memory_spike_kb"] == 100.0
        assert mapped["telemetry_data"]["l0_cpu_utilization"] == 25.5
        assert mapped["telemetry_data"]["l0_network_io_bytes"] == 1000.0
        assert mapped["provenance_chain"]["causal_depth"] == 2
        assert mapped["context_metadata"]["anomaly_severity"] == 1.0  # 0.1 * 10

    def test_map_record_anomalous(self):
        """Test mapping an anomalous synthetic record."""
        raw = {
            "event_id": "evt_456",
            "anomaly_type": "exfiltration",
            "execution_phase": "execution",
            "duration": 2.0,  # seconds
            "memory_spike_kb": 5000.0,
            "cpu_utilization": 95.0,
            "network_io_bytes": 1000000.0,
            "causal_depth": 5,
            "parent_chain": ["p1", "p2", "p3"],
            "graph_node_id": "node_xyz",
            "economic_risk_score": 0.95,
            "silent_failure_probability": 0.8,
            "completeness_score": 0.95,
            "adversarial_score": 0.9,
            "tags": {"category": "malicious"},
        }

        mapped = _map_record(raw)

        assert mapped["anomaly_type"] == "exfiltration"
        assert mapped["telemetry_data"]["l0_duration_ms"] == 2000.0
        assert mapped["telemetry_data"]["l0_memory_spike_kb"] == 5000.0
        assert mapped["context_metadata"]["anomaly_severity"] == 9.0  # 0.9 * 10

    def test_map_record_defaults(self):
        """Test mapping with missing fields uses defaults."""
        raw = {"event_id": "evt_empty"}

        mapped = _map_record(raw)

        assert mapped["record_id"] == "evt_empty"
        assert mapped["anomaly_type"] == "benign"
        assert mapped["telemetry_data"]["l0_duration_ms"] == 0.0
        assert mapped["context_metadata"]["anomaly_severity"] == 0.0


# ============================================================================
# Test Class: Detection Matrix Threshold
# ============================================================================

class TestDetectionMatrixThreshold:
    """Verify the threshold in detection_matrix.py is correct."""

    def test_threshold_is_updated_in_source(self):
        """Test that detection_matrix.py contains the new threshold."""
        dm_path = _SCAFAD_PKG / "layer2" / "detection_matrix.py"
        source = dm_path.read_text(encoding="utf-8")

        # Check that the threshold is set to 0.15
        pattern = r"anomaly_indicated\s*=\s*aggregate\s*>=\s*([0-9.]+)"
        matches = re.findall(pattern, source)

        assert len(matches) > 0, "Could not find 'anomaly_indicated = aggregate >= <float>'"

        # Get the first (and should be only) match
        threshold_str = matches[0]
        threshold_float = float(threshold_str)

        assert threshold_float == 0.15, \
            f"Expected threshold 0.15, got {threshold_float}"

    def test_calibration_comment_is_present(self):
        """Test that the calibration comment is in the source."""
        dm_path = _SCAFAD_PKG / "layer2" / "detection_matrix.py"
        source = dm_path.read_text(encoding="utf-8")

        # Check for the calibration comment
        assert "WP-5.2" in source, "WP-5.2 reference missing from comment"
        assert "calibration" in source.lower(), "calibration keyword missing"
        assert "0.15" in source, "New threshold not mentioned in comment"
        assert "0.30" in source or "0.590" in source, "Baseline reference missing"


# ============================================================================
# Test Class: Detection Matrix Functionality
# ============================================================================

class TestDetectionMatrixFunctionality:
    """Verify detection matrix still works with new threshold."""

    def test_detection_matrix_initialization(self):
        """Test that detection matrix can be instantiated."""
        detector = MultiVectorDetectionMatrix()
        assert detector is not None

    def test_detection_matrix_analyzes_record(self):
        """Test that detection matrix can analyze a record."""
        detector = MultiVectorDetectionMatrix()

        benign_record = {
            "record_id": "test_1",
            "event_id": "evt_1",
            "anomaly_type": "benign",
            "execution_phase": "initialization",
            "telemetry_data": {
                "l0_duration_ms": 100.0,
                "l0_memory_spike_kb": 50.0,
                "l0_cpu_utilization": 10.0,
                "l0_network_io_bytes": 500.0,
            },
            "provenance_chain": {
                "causal_depth": 1,
                "parent_chain": [],
                "graph_node_id": "node_1",
            },
            "context_metadata": {
                "economic_risk_score": 0.0,
                "silent_failure_probability": 0.0,
                "completeness_score": 1.0,
                "anomaly_category": "legitimate",
                "anomaly_severity": 0.0,
            },
        }

        result = detector.analyze(benign_record)
        assert result is not None
        assert hasattr(result, "aggregate_score")
        assert hasattr(result, "anomaly_indicated")
        assert isinstance(result.aggregate_score, (int, float))
        assert isinstance(result.anomaly_indicated, bool)

    def test_benign_record_below_threshold(self):
        """Test that a benign record scores below the new threshold."""
        detector = MultiVectorDetectionMatrix()

        benign_record = {
            "record_id": "benign_test",
            "event_id": "evt_benign",
            "anomaly_type": "benign",
            "execution_phase": "initialization",
            "telemetry_data": {
                "l0_duration_ms": 50.0,
                "l0_memory_spike_kb": 10.0,
                "l0_cpu_utilization": 5.0,
                "l0_network_io_bytes": 100.0,
            },
            "provenance_chain": {
                "causal_depth": 0,
                "parent_chain": [],
                "graph_node_id": "node_benign",
            },
            "context_metadata": {
                "economic_risk_score": 0.0,
                "silent_failure_probability": 0.0,
                "completeness_score": 1.0,
                "anomaly_category": "legitimate",
                "anomaly_severity": 0.0,
            },
        }

        result = detector.analyze(benign_record)

        # Benign records should score low (near 0.05–0.10 range)
        assert result.aggregate_score < 0.15, \
            f"Benign record scored {result.aggregate_score}, expected < 0.15"
        assert result.anomaly_indicated is False

    def test_anomalous_record_above_threshold(self):
        """Test that an anomalous record scores above the new threshold."""
        detector = MultiVectorDetectionMatrix()

        anomalous_record = {
            "record_id": "anom_test",
            "event_id": "evt_anom",
            "anomaly_type": "exfiltration",
            "execution_phase": "execution",
            "telemetry_data": {
                "l0_duration_ms": 5000.0,
                "l0_memory_spike_kb": 10000.0,
                "l0_cpu_utilization": 98.0,
                "l0_network_io_bytes": 1000000000.0,
            },
            "provenance_chain": {
                "causal_depth": 10,
                "parent_chain": ["p1", "p2", "p3", "p4"],
                "graph_node_id": "node_anom",
            },
            "context_metadata": {
                "economic_risk_score": 0.99,
                "silent_failure_probability": 0.99,
                "completeness_score": 0.95,
                "anomaly_category": "malicious",
                "anomaly_severity": 9.0,
            },
        }

        result = detector.analyze(anomalous_record)

        # Anomalous records should score high (> 0.15)
        assert result.aggregate_score >= 0.15, \
            f"Anomalous record scored {result.aggregate_score}, expected >= 0.15"
        assert result.anomaly_indicated is True


# ============================================================================
# Test Class: Calibration Results File
# ============================================================================

class TestCalibrationResultsFile:
    """Verify that calibration_results.json exists and is valid."""

    def test_calibration_results_file_exists(self):
        """Test that calibration_results.json was created."""
        results_path = _REPO_ROOT / "evaluation" / "calibration" / "calibration_results.json"

        assert results_path.exists(), \
            f"calibration_results.json not found at {results_path}"

    def test_calibration_results_file_is_valid_json(self):
        """Test that calibration_results.json is valid JSON."""
        results_path = _REPO_ROOT / "evaluation" / "calibration" / "calibration_results.json"

        if not results_path.exists():
            pytest.skip(f"calibration_results.json not found at {results_path}")

        with open(results_path, "r", encoding="utf-8") as fh:
            results = json.load(fh)

        assert isinstance(results, dict)
        assert "selected" in results
        assert results["selected"]["threshold"] == 0.15

    def test_calibration_results_show_improvement(self):
        """Test that results show F1 improvement over baseline."""
        results_path = _REPO_ROOT / "evaluation" / "calibration" / "calibration_results.json"

        if not results_path.exists():
            pytest.skip(f"calibration_results.json not found at {results_path}")

        with open(results_path, "r", encoding="utf-8") as fh:
            results = json.load(fh)

        improvement = results["improvement"]
        baseline_f1 = results["baseline"]["f1"]
        selected_f1 = results["selected"]["f1"]

        # Check that improvement metrics are positive
        assert improvement["f1_delta"] > 0
        assert improvement["f1_pct_improvement"] > 0

        # Check that selected F1 is better than baseline
        assert selected_f1 >= baseline_f1


# ============================================================================
# Test Class: Edge Cases and Error Conditions
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_custom_threshold_list(self):
        """Test calibration with custom threshold list."""
        dataset_path = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
        if not dataset_path.exists():
            pytest.skip(f"Dataset not found at {dataset_path}")

        custom_thresholds = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20]
        results = calibrate(
            dataset_path=dataset_path,
            output_path=None,
            thresholds=custom_thresholds,
            update_source=False,
        )

        # Check that selected threshold is from the custom list
        assert results["selected"]["threshold"] in custom_thresholds

    def test_no_output_path(self):
        """Test that calibration works with output_path=None."""
        dataset_path = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
        if not dataset_path.exists():
            pytest.skip(f"Dataset not found at {dataset_path}")

        # Should not raise an exception
        results = calibrate(
            dataset_path=dataset_path,
            output_path=None,
            update_source=False,
        )

        assert results is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
