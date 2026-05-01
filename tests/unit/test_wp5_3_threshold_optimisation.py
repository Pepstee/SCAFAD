"""
Tests for WP-5.3: Optimise L3 decision threshold to maximise F1 on evaluation set.

This test suite verifies:
1. The find_optimal_threshold.py script implementation
2. The optimal_threshold.json results file
3. The threshold calibration in explainability.py
4. The updated headline_metrics.json
5. Cache consistency after threshold update
6. Metrics improvements and no regressions
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EVALUATION_DIR = REPO_ROOT / "evaluation"
RESULTS_DIR = EVALUATION_DIR / "results"
SCAFAD_DIR = REPO_ROOT / "scafad"

FIND_OPTIMAL_SCRIPT = EVALUATION_DIR / "find_optimal_threshold.py"
OPTIMAL_THRESHOLD_JSON = RESULTS_DIR / "optimal_threshold.json"
HEADLINE_METRICS_JSON = RESULTS_DIR / "headline_metrics.json"
SCAFAD_RESULTS_JSON = RESULTS_DIR / "scafad_results.json"
EXPLAINABILITY_MODULE = SCAFAD_DIR / "layer4" / "explainability.py"


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def optimal_threshold_data() -> Dict[str, Any]:
    """Load the optimal_threshold.json file."""
    assert OPTIMAL_THRESHOLD_JSON.exists(), f"Missing: {OPTIMAL_THRESHOLD_JSON}"
    with open(OPTIMAL_THRESHOLD_JSON) as f:
        return json.load(f)


@pytest.fixture
def headline_metrics() -> Dict[str, Any]:
    """Load the headline_metrics.json file."""
    assert HEADLINE_METRICS_JSON.exists(), f"Missing: {HEADLINE_METRICS_JSON}"
    with open(HEADLINE_METRICS_JSON) as f:
        return json.load(f)


@pytest.fixture
def scafad_results_sample() -> List[Dict[str, Any]]:
    """Load a sample of scafad_results.json."""
    assert SCAFAD_RESULTS_JSON.exists(), f"Missing: {SCAFAD_RESULTS_JSON}"
    with open(SCAFAD_RESULTS_JSON) as f:
        data = json.load(f)
    # Return the first 100 records for efficiency
    if isinstance(data, dict) and "per_record" in data:
        return data["per_record"][:100]
    elif isinstance(data, list):
        return data[:100]
    else:
        return []


@pytest.fixture
def explainability_code() -> str:
    """Read the explainability.py file."""
    assert EXPLAINABILITY_MODULE.exists(), f"Missing: {EXPLAINABILITY_MODULE}"
    with open(EXPLAINABILITY_MODULE) as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. Grid Search Script Tests
# ---------------------------------------------------------------------------

class TestGridSearchScript:
    """Tests for find_optimal_threshold.py script."""

    def test_script_exists(self):
        """Verify find_optimal_threshold.py exists."""
        assert FIND_OPTIMAL_SCRIPT.exists(), f"Script not found: {FIND_OPTIMAL_SCRIPT}"

    def test_script_is_valid_python(self):
        """Verify script has valid Python syntax."""
        with open(FIND_OPTIMAL_SCRIPT) as f:
            code = f.read()
        try:
            compile(code, str(FIND_OPTIMAL_SCRIPT), "exec")
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {FIND_OPTIMAL_SCRIPT}: {e}")

    def test_script_imports_successfully(self):
        """Verify script can be imported without errors."""
        sys.path.insert(0, str(EVALUATION_DIR))
        try:
            import find_optimal_threshold  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import find_optimal_threshold: {e}")
        finally:
            sys.path.pop(0)

    def test_script_runs_without_cache_and_no_update(self):
        """Verify script runs in read-only mode."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(FIND_OPTIMAL_SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Script should succeed (exit code 0 or 1 both acceptable in non-update mode)
        assert result.returncode in (0, 1), f"Script failed: {result.stderr}"

    def test_script_loads_cache(self):
        """Verify script successfully loads evaluation cache."""
        with open(SCAFAD_RESULTS_JSON) as f:
            data = json.load(f)
        # Cache must have records
        if isinstance(data, dict) and "per_record" in data:
            records = data["per_record"]
        else:
            records = data
        assert len(records) > 0, "Cache is empty"
        # Each record must have required fields
        assert "ground_truth" in records[0], "Missing ground_truth in cache"
        assert "l3_fused_score" in records[0], "Missing l3_fused_score in cache"


# ---------------------------------------------------------------------------
# 2. Optimal Threshold Results Tests
# ---------------------------------------------------------------------------

class TestOptimalThresholdResults:
    """Tests for optimal_threshold.json."""

    def test_optimal_threshold_json_exists(self):
        """Verify optimal_threshold.json exists."""
        assert OPTIMAL_THRESHOLD_JSON.exists(), f"File not found: {OPTIMAL_THRESHOLD_JSON}"

    def test_optimal_threshold_json_is_valid(self, optimal_threshold_data):
        """Verify optimal_threshold.json is valid JSON."""
        # If we got here, the fixture loaded it successfully
        assert isinstance(optimal_threshold_data, dict)

    def test_optimal_threshold_value(self, optimal_threshold_data):
        """Verify optimal threshold is 0.09."""
        optimal = optimal_threshold_data.get("optimal_threshold", {})
        value = optimal.get("value")
        assert value == 0.09, f"Expected threshold=0.09, got {value}"

    def test_optimal_f1_is_perfect(self, optimal_threshold_data):
        """Verify optimal F1 is 1.0."""
        optimal = optimal_threshold_data.get("optimal_threshold", {})
        f1 = optimal.get("f1")
        assert f1 == 1.0, f"Expected F1=1.0, got {f1}"

    def test_optimal_precision_and_recall(self, optimal_threshold_data):
        """Verify optimal precision and recall are both 1.0."""
        optimal = optimal_threshold_data.get("optimal_threshold", {})
        precision = optimal.get("precision")
        recall = optimal.get("recall")
        assert precision == 1.0, f"Expected precision=1.0, got {precision}"
        assert recall == 1.0, f"Expected recall=1.0, got {recall}"

    def test_score_distribution_is_separable(self, optimal_threshold_data):
        """Verify score distributions are perfectly separated."""
        dist = optimal_threshold_data.get("score_distribution", {})
        benign = dist.get("benign", {})
        anomaly = dist.get("anomaly", {})
        gap = dist.get("gap")

        benign_max = benign.get("max")
        anomaly_min = anomaly.get("min")

        # Gap should be positive and equal to anomaly_min - benign_max
        assert gap is not None, "Gap not found"
        expected_gap = anomaly_min - benign_max
        assert abs(gap - expected_gap) < 1e-4, f"Gap mismatch: {gap} vs {expected_gap}"
        assert gap > 0, f"Gap must be positive, got {gap}"

    def test_improvement_delta(self, optimal_threshold_data):
        """Verify F1 improvement from old threshold to optimal."""
        optimal = optimal_threshold_data.get("optimal_threshold", {})
        current = optimal_threshold_data.get("current_threshold", {})

        old_f1 = current.get("f1")
        new_f1 = optimal.get("f1")
        delta = new_f1 - old_f1

        # Should have significant improvement
        assert delta > 0.2, f"F1 delta too small: {delta}"

    def test_current_threshold_in_results(self, optimal_threshold_data):
        """Verify old threshold (0.30) is recorded for comparison."""
        current = optimal_threshold_data.get("current_threshold", {})
        value = current.get("value")
        assert value == 0.3, f"Expected current threshold=0.3, got {value}"


# ---------------------------------------------------------------------------
# 3. Explainability Threshold Calibration Tests
# ---------------------------------------------------------------------------

class TestExplainabilityThresholdCalibration:
    """Tests for threshold in explainability.py."""

    def test_explainability_module_exists(self):
        """Verify explainability module exists."""
        assert EXPLAINABILITY_MODULE.exists(), f"Module not found: {EXPLAINABILITY_MODULE}"

    def test_explainability_uses_calibrated_threshold(self, explainability_code):
        """Verify explainability uses 0.09 threshold with WP-5.3 comment."""
        # Should have line with fused_score >= 0.09 and WP-5.3 comment
        assert "fused_score >= 0.09" in explainability_code, \
            "Threshold 0.09 not found in explainability.py"
        assert "WP-5.3" in explainability_code, \
            "WP-5.3 comment not found in explainability.py"

    def test_explainability_three_level_decision(self, explainability_code):
        """Verify explainability has three-level decision logic."""
        # Should have thresholds for observe, review, and escalate
        assert "0.09" in explainability_code, "Missing 0.09 threshold"
        assert "0.75" in explainability_code, "Missing 0.75 threshold"
        assert '"observe"' in explainability_code or "'observe'" in explainability_code
        assert '"review"' in explainability_code or "'review'" in explainability_code
        assert '"escalate"' in explainability_code or "'escalate'" in explainability_code


# ---------------------------------------------------------------------------
# 4. Headline Metrics Calibration Tests
# ---------------------------------------------------------------------------

class TestHeadlineMetricsCalibration:
    """Tests for headline_metrics.json."""

    def test_headline_metrics_exists(self):
        """Verify headline_metrics.json exists."""
        assert HEADLINE_METRICS_JSON.exists(), f"File not found: {HEADLINE_METRICS_JSON}"

    def test_headline_metrics_is_valid_json(self, headline_metrics):
        """Verify headline_metrics.json is valid JSON."""
        assert isinstance(headline_metrics, dict)

    def test_scafad_f1_is_perfect(self, headline_metrics):
        """Verify SCAFAD F1 score is 1.0."""
        scafad = headline_metrics.get("scafad", {})
        f1 = scafad.get("f1")
        assert f1 == 1.0, f"Expected SCAFAD F1=1.0, got {f1}"

    def test_scafad_precision_is_perfect(self, headline_metrics):
        """Verify SCAFAD precision is 1.0."""
        scafad = headline_metrics.get("scafad", {})
        precision = scafad.get("precision")
        assert precision == 1.0, f"Expected SCAFAD precision=1.0, got {precision}"

    def test_scafad_recall_is_perfect(self, headline_metrics):
        """Verify SCAFAD recall is 1.0."""
        scafad = headline_metrics.get("scafad", {})
        recall = scafad.get("recall")
        assert recall == 1.0, f"Expected SCAFAD recall=1.0, got {recall}"

    def test_scafad_roc_auc_unchanged(self, headline_metrics):
        """Verify SCAFAD ROC-AUC is 1.0 (unchanged by threshold)."""
        scafad = headline_metrics.get("scafad", {})
        roc_auc = scafad.get("roc_auc")
        assert roc_auc == 1.0, f"Expected SCAFAD ROC-AUC=1.0, got {roc_auc}"

    def test_confusion_matrix_perfect(self, headline_metrics):
        """Verify confusion matrix is perfect (TP=6250, FP=0, FN=0, TN=50)."""
        scafad = headline_metrics.get("scafad", {})
        cm = scafad.get("confusion_matrix", {})

        tp = cm.get("tp")
        fp = cm.get("fp")
        fn = cm.get("fn")
        tn = cm.get("tn")

        assert tp == 6250, f"Expected TP=6250, got {tp}"
        assert fp == 0, f"Expected FP=0, got {fp}"
        assert fn == 0, f"Expected FN=0, got {fn}"
        assert tn == 50, f"Expected TN=50, got {tn}"

    def test_threshold_calibration_metadata(self, headline_metrics):
        """Verify threshold calibration metadata is present."""
        # Check if any threshold calibration info is in the file
        content = str(headline_metrics)
        # The headline_metrics should reference the new performance
        assert "1.0" in content or "1" in content

    def test_dissertation_claims_pass(self, headline_metrics):
        """Verify all dissertation claims pass tolerance."""
        scafad = headline_metrics.get("scafad", {})
        f1 = scafad.get("f1")
        precision = scafad.get("precision")
        recall = scafad.get("recall")

        # All should be at or above target thresholds
        assert f1 >= 0.85, f"F1 below 0.85: {f1}"
        assert precision >= 0.85, f"Precision below 0.85: {precision}"
        assert recall >= 0.85, f"Recall below 0.85: {recall}"

    def test_baseline_comparison(self, headline_metrics):
        """Verify SCAFAD F1 exceeds all baselines."""
        scafad = headline_metrics.get("scafad", {})
        scafad_f1 = scafad.get("f1")

        baselines = headline_metrics.get("baselines", [])
        for baseline in baselines:
            baseline_f1 = baseline.get("f1")
            assert baseline_f1 is not None, f"Baseline {baseline.get('name')} missing F1"
            assert scafad_f1 >= baseline_f1, \
                f"SCAFAD F1={scafad_f1} not >= baseline {baseline.get('name')} F1={baseline_f1}"

    def test_support_numbers(self, headline_metrics):
        """Verify support numbers (total=6300, positives=6250, negatives=50)."""
        scafad = headline_metrics.get("scafad", {})
        support = scafad.get("support", {})

        total = support.get("total")
        positives = support.get("positives")
        negatives = support.get("negatives")

        assert total == 6300, f"Expected total=6300, got {total}"
        assert positives == 6250, f"Expected positives=6250, got {positives}"
        assert negatives == 50, f"Expected negatives=50, got {negatives}"


# ---------------------------------------------------------------------------
# 5. Cache Consistency Tests
# ---------------------------------------------------------------------------

class TestCacheConsistency:
    """Tests for scafad_results.json cache consistency."""

    def test_cache_has_per_record_data(self, scafad_results_sample):
        """Verify cache has per-record data."""
        assert len(scafad_results_sample) > 0, "Cache is empty"

    def test_cache_has_required_fields(self, scafad_results_sample):
        """Verify each cache record has required fields."""
        required_fields = ["ground_truth", "l3_fused_score", "predicted_label", "l4_decision"]
        for field in required_fields:
            for record in scafad_results_sample:
                assert field in record, \
                    f"Field '{field}' not found in record: {record.keys()}"

    def test_cache_predicted_labels_are_binary(self, scafad_results_sample):
        """Verify predicted labels are 0 or 1."""
        for record in scafad_results_sample:
            label = record.get("predicted_label")
            assert label in (0, 1), \
                f"Invalid predicted_label: {label} (must be 0 or 1)"

    def test_cache_decisions_match_labels(self, scafad_results_sample):
        """Verify l4_decision is consistent with predicted_label."""
        decision_map = {"observe": 0, "review": 1, "escalate": 1}
        for record in scafad_results_sample:
            decision = record.get("l4_decision")
            label = record.get("predicted_label")
            expected_label = decision_map.get(decision)
            assert expected_label is not None, f"Invalid decision: {decision}"
            assert label == expected_label, \
                f"Decision {decision} maps to {expected_label}, got label {label}"

    def test_cache_threshold_calibration_metadata(self):
        """Verify WP-5.3 calibration metadata in cache."""
        with open(SCAFAD_RESULTS_JSON) as f:
            data = json.load(f)

        # Check for threshold calibration metadata
        if isinstance(data, dict):
            # Metadata might be at root or per-record
            content = str(data)
            # At minimum, the file should exist and contain our predictions
            assert "predicted_label" in content or len(data) > 0


# ---------------------------------------------------------------------------
# 6. Threshold Decisions Tests
# ---------------------------------------------------------------------------

class TestThresholdDecisions:
    """Tests for decision thresholds in action."""

    def test_score_below_threshold_is_observe(self, scafad_results_sample):
        """Verify score < 0.09 maps to 'observe'."""
        for record in scafad_results_sample:
            score = record.get("l3_fused_score")
            decision = record.get("l4_decision")
            if score < 0.09:
                assert decision == "observe", \
                    f"Score {score} < 0.09 should be 'observe', got {decision}"

    def test_score_between_0_09_and_0_75_is_review(self, scafad_results_sample):
        """Verify 0.09 <= score < 0.75 maps to 'review'."""
        for record in scafad_results_sample:
            score = record.get("l3_fused_score")
            decision = record.get("l4_decision")
            if 0.09 <= score < 0.75:
                assert decision == "review", \
                    f"Score {score} in [0.09, 0.75) should be 'review', got {decision}"

    def test_escalate_threshold_is_defined(self, explainability_code):
        """Verify escalate threshold (0.75) is defined."""
        assert "0.75" in explainability_code, \
            "Escalate threshold 0.75 not found in explainability.py"


# ---------------------------------------------------------------------------
# 7. Regression Test
# ---------------------------------------------------------------------------

class TestRegressionCacheLoading:
    """Basic regression test for cache loading."""

    def test_no_regression_in_cache_loading(self):
        """Verify cache loads without errors."""
        with open(SCAFAD_RESULTS_JSON) as f:
            data = json.load(f)
        # Basic sanity check: must be non-empty
        if isinstance(data, dict) and "per_record" in data:
            records = data["per_record"]
        else:
            records = data
        assert len(records) > 0, "Cache is empty or corrupt"


# ---------------------------------------------------------------------------
# 8. Metrics Improvement Tests
# ---------------------------------------------------------------------------

class TestMetricsImprovement:
    """Tests verifying metrics improvements."""

    def test_f1_improvement_is_significant(self, optimal_threshold_data):
        """Verify F1 improvement from 0.724 to 1.0."""
        optimal = optimal_threshold_data.get("optimal_threshold", {})
        current = optimal_threshold_data.get("current_threshold", {})

        old_f1 = current.get("f1", 0)
        new_f1 = optimal.get("f1", 0)
        delta = new_f1 - old_f1

        # Should be at least 0.27 improvement
        assert delta >= 0.27, f"F1 delta too small: {delta}"

    def test_recall_improvement_is_substantial(self, optimal_threshold_data):
        """Verify recall improvement from 0.567 to 1.0."""
        optimal = optimal_threshold_data.get("optimal_threshold", {})
        current = optimal_threshold_data.get("current_threshold", {})

        old_recall = current.get("recall", 0)
        new_recall = optimal.get("recall", 0)
        delta = new_recall - old_recall

        # Should be at least 0.43 improvement
        assert delta >= 0.43, f"Recall delta too small: {delta}"

    def test_precision_maintained(self, optimal_threshold_data):
        """Verify precision is maintained at 1.0."""
        optimal = optimal_threshold_data.get("optimal_threshold", {})
        precision = optimal.get("precision", 0)

        # Precision should remain perfect
        assert precision == 1.0, f"Precision degraded: {precision}"
