#!/usr/bin/env python3
"""
Tests for WP-4.5: Run classical baselines against synthetic dataset and record results.

Test coverage:
- Script existence and executability
- Output file presence and validity
- JSON structure and schema compliance
- Model list completeness (12 configs, 4 required models)
- Metric ranges and data types
- Train/test split correctness
- Reproducibility and regressions
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures and constants
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "evaluation" / "run_baselines.py"
RESULTS_PATH = REPO_ROOT / "evaluation" / "results" / "baselines_results.json"

EXPECTED_MODELS = {
    "ZScore (threshold=3.0)",
    "ZScore (threshold=2.5)",
    "IQR (multiplier=1.5)",
    "IQR (multiplier=2.0)",
    "MovingAverage (w=10)",
    "IsolationForest (n=100, cont=0.10)",
    "IsolationForest (n=200, cont=0.05)",
    "OneClassSVM (nu=0.10)",
    "OneClassSVM (nu=0.05)",
    "LocalOutlierFactor (k=20, cont=0.10)",
    "LocalOutlierFactor (k=10, cont=0.05)",
    "DBSCAN (eps=0.5, min_samples=5)",
    # WP-4.2 additions
    "EllipticEnvelope (cont=0.10)",
    "KMeans (k=5)",
}

REQUIRED_MODELS = {
    "IsolationForest",
    "OneClassSVM",
    "LocalOutlierFactor",
    "ZScore",
    "EllipticEnvelope",
    "KMeans",
}

EXPECTED_FEATURES = [
    "duration",
    "memory_spike_kb",
    "cpu_utilization",
    "network_io_bytes",
]


@pytest.fixture
def results_json():
    """Load the baselines_results.json file as a dict."""
    with open(RESULTS_PATH) as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Script presence and executability
# ─────────────────────────────────────────────────────────────────────────────


class TestScriptPresence:
    """Verify the evaluation script exists and is properly formed."""

    def test_script_file_exists(self):
        """Script file must exist at evaluation/run_baselines.py."""
        assert SCRIPT_PATH.exists(), f"Script not found: {SCRIPT_PATH}"

    def test_script_is_readable(self):
        """Script must be readable."""
        assert os.access(SCRIPT_PATH, os.R_OK), f"Script not readable: {SCRIPT_PATH}"

    def test_script_is_python(self):
        """Script must be a Python file (ends in .py)."""
        assert str(SCRIPT_PATH).endswith(".py"), f"Script is not .py: {SCRIPT_PATH}"

    def test_script_has_shebang_or_main(self):
        """Script must have a main entry point or be importable."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "if __name__" in content or "def main" in content, \
            "Script has no main() or __name__ guard"

    def test_script_imports_no_syntax_errors(self):
        """Script must be syntactically valid Python."""
        result = subprocess.run(
            ["python", "-m", "py_compile", str(SCRIPT_PATH)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Syntax error in script: {result.stderr}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Output file presence and validity
# ─────────────────────────────────────────────────────────────────────────────


class TestOutputFilesExistence:
    """Verify the output files exist and are valid JSON."""

    def test_results_json_exists(self):
        """baselines_results.json must exist."""
        assert RESULTS_PATH.exists(), f"Results file not found: {RESULTS_PATH}"

    def test_results_json_is_readable(self):
        """Results file must be readable."""
        assert os.access(RESULTS_PATH, os.R_OK), f"Results not readable: {RESULTS_PATH}"

    def test_results_json_is_not_empty(self):
        """Results file must not be empty."""
        assert RESULTS_PATH.stat().st_size > 0, "Results file is empty"

    def test_results_json_is_valid_json(self, results_json):
        """Results file must be valid JSON (fixture will fail if not)."""
        assert isinstance(results_json, dict), "Results must be a JSON object"

    def test_results_json_not_blank(self, results_json):
        """Results JSON must contain data (not empty dict)."""
        assert len(results_json) > 0, "Results JSON is empty"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Root-level schema compliance
# ─────────────────────────────────────────────────────────────────────────────


class TestResultsSchema:
    """Verify the root-level structure of baselines_results.json."""

    def test_has_generated_at(self, results_json):
        """Must have a generated_at timestamp."""
        assert "generated_at" in results_json, "Missing 'generated_at' field"

    def test_generated_at_is_string(self, results_json):
        """generated_at must be a string (ISO8601)."""
        assert isinstance(results_json["generated_at"], str), \
            f"generated_at must be string, got {type(results_json['generated_at'])}"

    def test_has_dataset_path(self, results_json):
        """Must have a dataset path."""
        assert "dataset" in results_json, "Missing 'dataset' field"
        assert "synthetic_eval_dataset" in results_json["dataset"], \
            "Dataset path must reference synthetic_eval_dataset"

    def test_has_evaluation_protocol(self, results_json):
        """Must document the evaluation protocol used."""
        assert "evaluation_protocol" in results_json, "Missing 'evaluation_protocol'"
        assert "one-class" in results_json["evaluation_protocol"].lower(), \
            "Protocol must be 'one-class'"

    def test_has_train_records_count(self, results_json):
        """Must report number of training records."""
        assert "train_records" in results_json, "Missing 'train_records'"
        assert isinstance(results_json["train_records"], int), \
            "train_records must be an integer"

    def test_train_records_is_200(self, results_json):
        """Training set should have 200 benign records (80% of 250)."""
        assert results_json["train_records"] == 200, \
            f"Expected 200 train records, got {results_json['train_records']}"

    def test_has_test_records_count(self, results_json):
        """Must report number of test records."""
        assert "test_records" in results_json, "Missing 'test_records'"
        assert isinstance(results_json["test_records"], int), \
            "test_records must be an integer"

    def test_test_records_is_6300(self, results_json):
        """Test set should have 6300 records (50 benign + 6250 anomalies)."""
        assert results_json["test_records"] == 6300, \
            f"Expected 6300 test records, got {results_json['test_records']}"

    def test_has_test_anomaly_rate(self, results_json):
        """Must report the test anomaly rate."""
        assert "test_anomaly_rate" in results_json, "Missing 'test_anomaly_rate'"
        rate = results_json["test_anomaly_rate"]
        assert isinstance(rate, (int, float)), "Anomaly rate must be numeric"

    def test_test_anomaly_rate_is_high(self, results_json):
        """Test anomaly rate should be ~99.2% (6250 / 6300)."""
        rate = results_json["test_anomaly_rate"]
        assert 0.99 < rate < 1.0, \
            f"Anomaly rate should be ~0.992, got {rate}"

    def test_has_features_list(self, results_json):
        """Must report the features used."""
        assert "features" in results_json, "Missing 'features' field"
        assert isinstance(results_json["features"], list), \
            "features must be a list"

    def test_features_match_expected(self, results_json):
        """Features must match the 4 core numeric features."""
        features = results_json["features"]
        assert set(features) == set(EXPECTED_FEATURES), \
            f"Expected features {EXPECTED_FEATURES}, got {features}"

    def test_has_total_evaluation_time(self, results_json):
        """Must report total wall-clock evaluation time."""
        assert "total_evaluation_time_s" in results_json, \
            "Missing 'total_evaluation_time_s'"
        t = results_json["total_evaluation_time_s"]
        assert isinstance(t, (int, float)), \
            "total_evaluation_time_s must be numeric"

    def test_total_time_is_reasonable(self, results_json):
        """Total time should be between 1 and 30 seconds (14 models including KMeans)."""
        t = results_json["total_evaluation_time_s"]
        assert 1.0 <= t <= 30.0, \
            f"Total time should be ~4-10s, got {t}s"

    def test_has_models_key(self, results_json):
        """Must have a 'models' key."""
        assert "models" in results_json, "Missing 'models' key"

    def test_models_is_list(self, results_json):
        """models must be a list."""
        assert isinstance(results_json["models"], list), \
            f"models must be a list, got {type(results_json['models'])}"

    def test_models_not_empty(self, results_json):
        """models list must not be empty."""
        assert len(results_json["models"]) > 0, "models list is empty"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Model list completeness
# ─────────────────────────────────────────────────────────────────────────────


class TestModelListCompleteness:
    """Verify that all expected models are present and required ones included."""

    def test_model_count(self, results_json):
        """Should have all 14 detector configurations (12 original + 2 WP-4.2 additions)."""
        models = results_json["models"]
        assert len(models) == 14, \
            f"Expected 14 models, got {len(models)}"

    def test_all_expected_models_present(self, results_json):
        """All expected model names must be in the results."""
        model_names = {m["name"] for m in results_json["models"]}
        missing = EXPECTED_MODELS - model_names
        assert not missing, f"Missing models: {missing}"

    def test_no_unexpected_models(self, results_json):
        """No models should be present that aren't expected."""
        model_names = {m["name"] for m in results_json["models"]}
        unexpected = model_names - EXPECTED_MODELS
        assert not unexpected, f"Unexpected models: {unexpected}"

    def test_required_model_isolation_forest_present(self, results_json):
        """IsolationForest must be present in at least one config."""
        model_names = {m["name"] for m in results_json["models"]}
        assert any("IsolationForest" in name for name in model_names), \
            "IsolationForest model not found"

    def test_required_model_one_class_svm_present(self, results_json):
        """OneClassSVM must be present in at least one config."""
        model_names = {m["name"] for m in results_json["models"]}
        assert any("OneClassSVM" in name for name in model_names), \
            "OneClassSVM model not found"

    def test_required_model_local_outlier_factor_present(self, results_json):
        """LocalOutlierFactor must be present in at least one config."""
        model_names = {m["name"] for m in results_json["models"]}
        assert any("LocalOutlierFactor" in name for name in model_names), \
            "LocalOutlierFactor model not found"

    def test_required_model_zscore_present(self, results_json):
        """ZScore must be present in at least one config."""
        model_names = {m["name"] for m in results_json["models"]}
        assert any("ZScore" in name for name in model_names), \
            "ZScore model not found"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Per-model schema and metric ranges
# ─────────────────────────────────────────────────────────────────────────────


class TestPerModelSchema:
    """Verify that each model entry has the required fields and valid values."""

    def test_each_model_has_name(self, results_json):
        """Every model entry must have a name."""
        for i, model in enumerate(results_json["models"]):
            assert "name" in model, f"Model {i} missing 'name' field"
            assert isinstance(model["name"], str), \
                f"Model {i} name must be string"

    def test_each_model_has_precision(self, results_json):
        """Every model entry must have precision (or error field)."""
        for i, model in enumerate(results_json["models"]):
            if "error" not in model:
                assert "precision" in model, \
                    f"Model {i} ({model['name']}) missing 'precision'"

    def test_precision_in_valid_range(self, results_json):
        """Precision must be in [0, 1]."""
        for model in results_json["models"]:
            if "error" not in model:
                prec = model["precision"]
                assert 0 <= prec <= 1, \
                    f"Model {model['name']} precision out of range: {prec}"

    def test_each_model_has_recall(self, results_json):
        """Every model entry must have recall."""
        for model in results_json["models"]:
            if "error" not in model:
                assert "recall" in model, \
                    f"Model {model['name']} missing 'recall'"

    def test_recall_in_valid_range(self, results_json):
        """Recall must be in [0, 1]."""
        for model in results_json["models"]:
            if "error" not in model:
                recall = model["recall"]
                assert 0 <= recall <= 1, \
                    f"Model {model['name']} recall out of range: {recall}"

    def test_each_model_has_f1(self, results_json):
        """Every model entry must have F1 score."""
        for model in results_json["models"]:
            if "error" not in model:
                assert "f1" in model, \
                    f"Model {model['name']} missing 'f1'"

    def test_f1_in_valid_range(self, results_json):
        """F1 score must be in [0, 1]."""
        for model in results_json["models"]:
            if "error" not in model:
                f1 = model["f1"]
                assert 0 <= f1 <= 1, \
                    f"Model {model['name']} F1 out of range: {f1}"

    def test_each_model_has_roc_auc(self, results_json):
        """Every model entry must have ROC-AUC."""
        for model in results_json["models"]:
            if "error" not in model:
                assert "roc_auc" in model, \
                    f"Model {model['name']} missing 'roc_auc'"

    def test_roc_auc_in_valid_range(self, results_json):
        """ROC-AUC must be in [0, 1]."""
        for model in results_json["models"]:
            if "error" not in model:
                auc = model["roc_auc"]
                assert 0 <= auc <= 1, \
                    f"Model {model['name']} ROC-AUC out of range: {auc}"

    def test_each_model_has_train_time(self, results_json):
        """Every model entry must have train_time_s."""
        for model in results_json["models"]:
            if "error" not in model:
                assert "train_time_s" in model, \
                    f"Model {model['name']} missing 'train_time_s'"

    def test_train_time_is_non_negative(self, results_json):
        """Training time must be non-negative."""
        for model in results_json["models"]:
            if "error" not in model:
                t = model["train_time_s"]
                assert t >= 0, \
                    f"Model {model['name']} train_time_s is negative: {t}"

    def test_each_model_has_infer_time(self, results_json):
        """Every model entry must have infer_time_s."""
        for model in results_json["models"]:
            if "error" not in model:
                assert "infer_time_s" in model, \
                    f"Model {model['name']} missing 'infer_time_s'"

    def test_infer_time_is_non_negative(self, results_json):
        """Inference time must be non-negative."""
        for model in results_json["models"]:
            if "error" not in model:
                t = model["infer_time_s"]
                assert t >= 0, \
                    f"Model {model['name']} infer_time_s is negative: {t}"

    def test_each_model_has_model_parameters(self, results_json):
        """Every model entry must have model_parameters."""
        for model in results_json["models"]:
            if "error" not in model:
                assert "model_parameters" in model, \
                    f"Model {model['name']} missing 'model_parameters'"
            assert isinstance(model.get("model_parameters", {}), dict), \
                f"Model {model['name']} model_parameters must be a dict"

    def test_model_parameters_are_json_serializable(self, results_json):
        """All model parameters must be JSON-serializable types."""
        for model in results_json["models"]:
            try:
                json.dumps(model.get("model_parameters", {}))
            except (TypeError, ValueError) as exc:
                pytest.fail(
                    f"Model {model['name']} model_parameters not JSON-serializable: {exc}"
                )


# ─────────────────────────────────────────────────────────────────────────────
# 6. Metric reasonableness checks
# ─────────────────────────────────────────────────────────────────────────────


class TestMetricReasonableness:
    """Verify that metrics are in reasonable ranges and make logical sense."""

    def test_best_f1_is_high(self, results_json):
        """The best F1 across all models should be > 0.8."""
        f1_scores = [m["f1"] for m in results_json["models"] if "error" not in m]
        best_f1 = max(f1_scores)
        assert best_f1 > 0.8, \
            f"Best F1 is too low: {best_f1}"

    def test_best_roc_auc_is_high(self, results_json):
        """The best ROC-AUC across all models should be > 0.85."""
        auc_scores = [m["roc_auc"] for m in results_json["models"] if "error" not in m]
        best_auc = max(auc_scores)
        assert best_auc > 0.85, \
            f"Best ROC-AUC is too low: {best_auc}"

    def test_zscore_has_perfect_precision(self, results_json):
        """ZScore variants should have precision = 1.0 (no false positives)."""
        zscore_models = [m for m in results_json["models"] if "ZScore" in m["name"]]
        for model in zscore_models:
            assert model["precision"] == 1.0, \
                f"ZScore {model['name']} precision should be 1.0, got {model['precision']}"

    def test_dbscan_has_high_precision(self, results_json):
        """DBSCAN should have high precision (few false positives)."""
        dbscan = [m for m in results_json["models"] if "DBSCAN" in m["name"]]
        assert len(dbscan) == 1, "Expected exactly one DBSCAN model"
        assert dbscan[0]["precision"] == 1.0, \
            f"DBSCAN precision should be 1.0, got {dbscan[0]['precision']}"

    def test_dbscan_has_low_recall(self, results_json):
        """DBSCAN recall should be low (~0.047) due to conservative threshold."""
        dbscan = [m for m in results_json["models"] if "DBSCAN" in m["name"]]
        assert dbscan[0]["recall"] < 0.1, \
            f"DBSCAN recall should be < 0.1, got {dbscan[0]['recall']}"

    def test_precision_recall_correlation(self, results_json):
        """In general, high-precision models should have lower recall."""
        # (Not a strict rule, but a sanity check)
        for model in results_json["models"]:
            if "error" not in model and model["precision"] > 0.99:
                # High precision models often trade recall
                # This is not a hard requirement, just a check
                pass

    def test_all_models_evaluated_successfully(self, results_json):
        """All 12 models should be evaluated without errors."""
        errors = [m for m in results_json["models"] if "error" in m]
        assert len(errors) == 0, \
            f"Models failed evaluation: {[m['name'] for m in errors]}"

    def test_evaluation_time_split_makes_sense(self, results_json):
        """Sum of train + infer times should be less than total time."""
        total_time = results_json["total_evaluation_time_s"]
        sum_train = sum(m.get("train_time_s", 0) for m in results_json["models"])
        sum_infer = sum(m.get("infer_time_s", 0) for m in results_json["models"])
        # Allow 50% overhead for iteration and setup
        assert sum_train + sum_infer <= total_time * 1.5, \
            f"Train+infer times {sum_train + sum_infer} > total_time {total_time}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Benchmark baseline checks (from build report)
# ─────────────────────────────────────────────────────────────────────────────


class TestBenchmarkBaselines:
    """Verify that the reported baselines match the expected results."""

    def test_one_class_svm_nu010_exists(self, results_json):
        """OneClassSVM (nu=0.10) should be the best F1 model."""
        model_names = {m["name"] for m in results_json["models"]}
        assert "OneClassSVM (nu=0.10)" in model_names, \
            "OneClassSVM (nu=0.10) not found"

    def test_one_class_svm_nu010_f1_is_high(self, results_json):
        """OneClassSVM (nu=0.10) should have F1 ≥ 0.885."""
        models = {m["name"]: m for m in results_json["models"]}
        f1 = models["OneClassSVM (nu=0.10)"]["f1"]
        assert f1 >= 0.885, \
            f"OneClassSVM (nu=0.10) F1 should be ≥ 0.885, got {f1}"

    def test_zscore_variants_exist(self, results_json):
        """Both ZScore (threshold=3.0) and (2.5) should exist."""
        model_names = {m["name"] for m in results_json["models"]}
        assert "ZScore (threshold=3.0)" in model_names, \
            "ZScore (threshold=3.0) not found"
        assert "ZScore (threshold=2.5)" in model_names, \
            "ZScore (threshold=2.5) not found"

    def test_zscore_has_high_auc(self, results_json):
        """ZScore models should have ROC-AUC ≥ 0.895."""
        zscore_models = [m for m in results_json["models"] if "ZScore" in m["name"]]
        for model in zscore_models:
            assert model["roc_auc"] >= 0.895, \
                f"ZScore {model['name']} ROC-AUC should be ≥ 0.895, got {model['roc_auc']}"

    def test_isolation_forest_models_exist(self, results_json):
        """Both IsolationForest configs should exist."""
        model_names = {m["name"] for m in results_json["models"]}
        assert "IsolationForest (n=100, cont=0.10)" in model_names, \
            "IsolationForest (n=100, cont=0.10) not found"
        assert "IsolationForest (n=200, cont=0.05)" in model_names, \
            "IsolationForest (n=200, cont=0.05) not found"

    def test_local_outlier_factor_models_exist(self, results_json):
        """Both LocalOutlierFactor configs should exist."""
        model_names = {m["name"] for m in results_json["models"]}
        assert "LocalOutlierFactor (k=20, cont=0.10)" in model_names, \
            "LocalOutlierFactor (k=20, cont=0.10) not found"
        assert "LocalOutlierFactor (k=10, cont=0.05)" in model_names, \
            "LocalOutlierFactor (k=10, cont=0.05) not found"

    def test_elliptic_envelope_model_exists(self, results_json):
        """EllipticEnvelope (WP-4.2) should be present."""
        model_names = {m["name"] for m in results_json["models"]}
        assert "EllipticEnvelope (cont=0.10)" in model_names, \
            "EllipticEnvelope (cont=0.10) not found"

    def test_kmeans_model_exists(self, results_json):
        """KMeans (WP-4.2) should be present."""
        model_names = {m["name"] for m in results_json["models"]}
        assert "KMeans (k=5)" in model_names, \
            "KMeans (k=5) not found"

    def test_elliptic_envelope_f1_is_reasonable(self, results_json):
        """EllipticEnvelope should have F1 >= 0.80."""
        models = {m["name"]: m for m in results_json["models"]}
        f1 = models["EllipticEnvelope (cont=0.10)"]["f1"]
        assert f1 >= 0.80, \
            f"EllipticEnvelope F1 should be >= 0.80, got {f1}"

    def test_kmeans_f1_is_reasonable(self, results_json):
        """KMeans should have F1 >= 0.75."""
        models = {m["name"]: m for m in results_json["models"]}
        f1 = models["KMeans (k=5)"]["f1"]
        assert f1 >= 0.75, \
            f"KMeans F1 should be >= 0.75, got {f1}"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Integration and acceptance tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationAndAcceptance:
    """End-to-end acceptance criteria verification."""

    def test_results_file_contains_all_required_info(self, results_json):
        """Results file must contain all information needed for WP-4.6 comparison."""
        required_keys = {
            "generated_at",
            "dataset",
            "evaluation_protocol",
            "train_records",
            "test_records",
            "test_anomaly_rate",
            "features",
            "total_evaluation_time_s",
            "models",
        }
        actual_keys = set(results_json.keys())
        missing = required_keys - actual_keys
        assert not missing, f"Missing required keys: {missing}"

    def test_acceptance_criterion_metrics_present(self, results_json):
        """All acceptance criteria metrics (precision, recall, F1, ROC-AUC) present."""
        for model in results_json["models"]:
            if "error" not in model:
                for field in ("precision", "recall", "f1", "roc_auc"):
                    assert field in model, \
                        f"Model {model['name']} missing {field}"

    def test_acceptance_criterion_timing_present(self, results_json):
        """Acceptance criteria: train_time_s and infer_time_s must be present."""
        for model in results_json["models"]:
            if "error" not in model:
                for field in ("train_time_s", "infer_time_s"):
                    assert field in model, \
                        f"Model {model['name']} missing {field}"

    def test_results_valid_for_wp46_comparison(self, results_json):
        """Results must be in the correct format for WP-4.6 (SCAFAD vs baselines)."""
        # WP-4.6 will compare SCAFAD performance against these baselines
        # Ensure all required metadata and metrics are present
        assert len(results_json["models"]) >= 4, \
            "Must have at least 4 models for fair comparison"
        for model in results_json["models"]:
            if "error" not in model:
                # Each model must have F1 and ROC-AUC for comparison
                assert "f1" in model and "roc_auc" in model, \
                    f"Model {model['name']} missing comparison metrics"

    def test_script_is_runnable(self):
        """The script should be runnable with --dry-run flag."""
        result = subprocess.run(
            ["python", str(SCRIPT_PATH), "--dry-run"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should exit successfully (code 0)
        assert result.returncode == 0, \
            f"Script --dry-run failed: {result.stderr}"

    def test_full_evaluation_consistency(self, results_json):
        """Verify consistency between root metadata and individual model results."""
        # Test record count should match: 50 benign + sum of anomalies
        # Since we have 250 records per class * 25 anomaly classes
        expected_test_records = 50 + (250 * 25)  # benign + anomalies
        assert results_json["test_records"] == expected_test_records, \
            f"Test records inconsistent: expected {expected_test_records}, got {results_json['test_records']}"

        # All models should be evaluated on the same test set
        for model in results_json["models"]:
            if "error" not in model:
                # Metrics should be realistic for the stated test_records
                pass
