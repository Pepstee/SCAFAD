"""
WP-4.2: Complete Baselines Comparison — Add Remaining Classical Detectors

Feature tests for WP-4.2 acceptance criteria:
- AC-1: evaluation/baselines/classical_detectors.py updated with 6+ detectors
- AC-2: evaluation/results/baselines_results.json updated
- AC-3: evaluation/results/baselines_summary.md written with comparison table
- AC-4: SCAFAD F1 result included in table

Test coverage:
- File structure and existence
- Module imports and instantiation
- Results file schema validation
- Summary file structure and content
- Acceptance criteria verification
"""

import json
import os
import pytest
from pathlib import Path


class TestFileStructure:
    """Test that all required files exist and are readable."""

    @pytest.fixture(scope="class")
    def scafad_root(self):
        """Return the SCAFAD project root."""
        return Path(__file__).parent.parent.parent

    def test_classical_detectors_file_exists(self, scafad_root):
        """AC-1: classical_detectors.py must exist."""
        filepath = scafad_root / "evaluation" / "baselines" / "classical_detectors.py"
        assert filepath.exists(), f"classical_detectors.py not found at {filepath}"

    def test_baselines_results_json_exists(self, scafad_root):
        """AC-2: baselines_results.json must exist."""
        filepath = scafad_root / "evaluation" / "results" / "baselines_results.json"
        assert filepath.exists(), f"baselines_results.json not found at {filepath}"

    def test_baselines_summary_md_exists(self, scafad_root):
        """AC-3: baselines_summary.md must exist."""
        filepath = scafad_root / "evaluation" / "results" / "baselines_summary.md"
        assert filepath.exists(), f"baselines_summary.md not found at {filepath}"

    def test_classical_detectors_is_readable(self, scafad_root):
        """File must be readable Python."""
        filepath = scafad_root / "evaluation" / "baselines" / "classical_detectors.py"
        with open(filepath, 'r') as f:
            content = f.read()
        assert len(content) > 0, "classical_detectors.py is empty"
        assert "class" in content, "No class definitions found"

    def test_baselines_results_json_is_valid(self, scafad_root):
        """JSON file must be valid."""
        filepath = scafad_root / "evaluation" / "results" / "baselines_results.json"
        with open(filepath, 'r') as f:
            data = json.load(f)
        assert isinstance(data, dict), "baselines_results.json must be a dict"

    def test_baselines_summary_md_is_readable(self, scafad_root):
        """Markdown file must be readable."""
        filepath = scafad_root / "evaluation" / "results" / "baselines_summary.md"
        with open(filepath, 'r') as f:
            content = f.read()
        assert len(content) > 0, "baselines_summary.md is empty"


class TestDetectorImplementation:
    """Test that all detectors are implemented and importable."""

    def test_import_statistical_zscore_detector(self):
        """Should import StatisticalZScoreDetector."""
        from evaluation.baselines.classical_detectors import StatisticalZScoreDetector
        assert StatisticalZScoreDetector is not None

    def test_import_statistical_iqr_detector(self):
        """Should import StatisticalIQRDetector."""
        from evaluation.baselines.classical_detectors import StatisticalIQRDetector
        assert StatisticalIQRDetector is not None

    def test_import_moving_average_detector(self):
        """Should import MovingAverageDetector."""
        from evaluation.baselines.classical_detectors import MovingAverageDetector
        assert MovingAverageDetector is not None

    def test_import_isolation_forest_detector(self):
        """Should import IsolationForestDetector."""
        from evaluation.baselines.classical_detectors import IsolationForestDetector
        assert IsolationForestDetector is not None

    def test_import_one_class_svm_detector(self):
        """Should import OneClassSVMDetector."""
        from evaluation.baselines.classical_detectors import OneClassSVMDetector
        assert OneClassSVMDetector is not None

    def test_import_local_outlier_factor_detector(self):
        """Should import LocalOutlierFactorDetector."""
        from evaluation.baselines.classical_detectors import LocalOutlierFactorDetector
        assert LocalOutlierFactorDetector is not None

    def test_import_elliptic_envelope_detector(self):
        """Should import EllipticEnvelopeDetector."""
        from evaluation.baselines.classical_detectors import EllipticEnvelopeDetector
        assert EllipticEnvelopeDetector is not None

    def test_import_kmeans_detector(self):
        """Should import KMeansDetector."""
        from evaluation.baselines.classical_detectors import KMeansDetector
        assert KMeansDetector is not None

    def test_import_dbscan_anomaly_detector(self):
        """Should import DBSCANAnomalyDetector."""
        from evaluation.baselines.classical_detectors import DBSCANAnomalyDetector
        assert DBSCANAnomalyDetector is not None

    def test_detector_count_exceeds_minimum(self):
        """AC-1: At least 6 detectors must be implemented."""
        from evaluation.baselines import classical_detectors
        import inspect

        # Get all classes from the module
        detector_classes = [
            name for name, obj in inspect.getmembers(classical_detectors)
            if inspect.isclass(obj) and 'Detector' in name
            and obj.__module__ == 'evaluation.baselines.classical_detectors'
        ]
        assert len(detector_classes) >= 6, f"Expected ≥6 detectors, found {len(detector_classes)}"


class TestResultsFileSchema:
    """Test the schema and content of baselines_results.json."""

    @pytest.fixture
    def results_data(self):
        """Load the baselines_results.json file."""
        from pathlib import Path
        filepath = Path(__file__).parent.parent.parent / "evaluation" / "results" / "baselines_results.json"
        with open(filepath, 'r') as f:
            return json.load(f)

    def test_results_has_models_key(self, results_data):
        """AC-2: results must have 'models' key."""
        assert "models" in results_data, "baselines_results.json missing 'models' key"

    def test_models_is_list(self, results_data):
        """models key must be a list."""
        assert isinstance(results_data["models"], list), "models must be a list"

    def test_model_count_is_reasonable(self, results_data):
        """Should have multiple model variants (expect ≥6)."""
        models = results_data["models"]
        assert len(models) >= 6, f"Expected ≥6 models, found {len(models)}"

    def test_each_model_has_required_fields(self, results_data):
        """Each model must have name, F1, Precision, Recall, ROC-AUC."""
        required_fields = {"name", "f1", "precision", "recall", "roc_auc"}
        for model in results_data["models"]:
            missing = required_fields - set(model.keys())
            assert not missing, f"Model {model.get('name', 'unknown')} missing fields: {missing}"

    def test_metrics_in_valid_range(self, results_data):
        """All metrics should be between 0 and 1."""
        for model in results_data["models"]:
            for metric in ["f1", "precision", "recall", "roc_auc"]:
                value = model[metric]
                assert 0 <= value <= 1, \
                    f"{model['name']}.{metric}={value} not in [0, 1]"

    def test_best_baseline_f1_is_high(self, results_data):
        """Best baseline should have reasonable F1 score (>0.7)."""
        f1_scores = [m["f1"] for m in results_data["models"]]
        max_f1 = max(f1_scores)
        assert max_f1 > 0.7, f"Best baseline F1={max_f1} is too low"

    def test_one_class_svm_nu010_present(self, results_data):
        """OneClassSVM (nu=0.10) should be in results."""
        names = [m["name"] for m in results_data["models"]]
        assert any("OneClassSVM" in n and "0.10" in n for n in names), \
            "OneClassSVM (nu=0.10) not found in results"

    def test_isolation_forest_present(self, results_data):
        """IsolationForest should be in results."""
        names = [m["name"] for m in results_data["models"]]
        assert any("IsolationForest" in n for n in names), \
            "IsolationForest not found in results"

    def test_zscore_present(self, results_data):
        """ZScore detector should be in results."""
        names = [m["name"] for m in results_data["models"]]
        assert any("ZScore" in n or "Z-Score" in n for n in names), \
            "ZScore not found in results"


class TestSummaryFile:
    """Test the structure and content of baselines_summary.md."""

    @pytest.fixture
    def summary_content(self):
        """Load the baselines_summary.md file."""
        from pathlib import Path
        filepath = Path(__file__).parent.parent.parent / "evaluation" / "results" / "baselines_summary.md"
        with open(filepath, 'r') as f:
            return f.read()

    def test_summary_file_is_not_empty(self, summary_content):
        """AC-3: Summary file must have content."""
        assert len(summary_content) > 0, "baselines_summary.md is empty"

    def test_summary_contains_comparison_table(self, summary_content):
        """AC-3: Summary must contain a comparison table (markdown table syntax)."""
        assert "|" in summary_content, "No table found in baselines_summary.md"
        assert "---" in summary_content, "No table separator found"

    def test_summary_contains_f1_column(self, summary_content):
        """Summary table should mention F1 metric."""
        lines = summary_content.split('\n')
        # Find the header line
        header_found = False
        for line in lines:
            if "|" in line and ("F1" in line or "f1" in line):
                header_found = True
                break
        assert header_found, "F1 column not found in summary table"

    def test_summary_contains_scafad_row(self, summary_content):
        """AC-4: SCAFAD must have a row in the summary table."""
        assert "SCAFAD" in summary_content, "SCAFAD row not found in summary"

    def test_scafad_f1_is_reported(self, summary_content):
        """AC-4: SCAFAD F1 score must be in the summary."""
        scafad_section = summary_content[summary_content.find("SCAFAD"):]
        # Look for F1 value (1.0000 or similar)
        assert any(f1_str in scafad_section for f1_str in ["1.0000", "1.000", "100%"]), \
            "SCAFAD F1 score not found near SCAFAD row"

    def test_summary_mentions_detectors(self, summary_content):
        """Summary should reference the detector methods."""
        detector_keywords = ["IsolationForest", "OneClassSVM", "ZScore", "LOF"]
        mentioned = [kw for kw in detector_keywords if kw in summary_content or kw.lower() in summary_content.lower()]
        assert len(mentioned) > 0, "No detector names found in summary"

    def test_summary_has_comparison_information(self, summary_content):
        """Summary should include comparison/gap information."""
        comparison_keywords = ["gap", "better", "SCAFAD", "baseline", "performance", "improve"]
        mentioned = [kw for kw in comparison_keywords if kw.lower() in summary_content.lower()]
        assert len(mentioned) > 0, "No comparison information found in summary"


class TestAcceptanceCriteria:
    """Test that all AC criteria are met."""

    @pytest.fixture(scope="class")
    def scafad_root(self):
        """Return the SCAFAD project root."""
        return Path(__file__).parent.parent.parent

    def test_ac1_detectors_implemented(self):
        """AC-1: ≥6 classical detectors in classical_detectors.py."""
        from evaluation.baselines import classical_detectors
        import inspect

        detector_classes = [
            name for name, obj in inspect.getmembers(classical_detectors)
            if inspect.isclass(obj) and 'Detector' in name
            and obj.__module__ == 'evaluation.baselines.classical_detectors'
        ]
        assert len(detector_classes) >= 6, \
            f"AC-1 FAIL: Need ≥6 detectors, found {len(detector_classes)}"

    def test_ac2_results_json_complete(self, scafad_root):
        """AC-2: baselines_results.json with all model results."""
        filepath = scafad_root / "evaluation" / "results" / "baselines_results.json"
        with open(filepath, 'r') as f:
            data = json.load(f)

        assert "models" in data, "AC-2 FAIL: 'models' key missing"
        assert isinstance(data["models"], list), "AC-2 FAIL: 'models' not a list"
        assert len(data["models"]) >= 6, f"AC-2 FAIL: Need ≥6 model results, found {len(data['models'])}"

        # Each model must have metrics
        for model in data["models"]:
            assert "f1" in model and "precision" in model and "recall" in model, \
                f"AC-2 FAIL: Model {model.get('name')} missing metrics"

    def test_ac3_summary_file_complete(self, scafad_root):
        """AC-3: baselines_summary.md with comparison table."""
        filepath = scafad_root / "evaluation" / "results" / "baselines_summary.md"
        with open(filepath, 'r') as f:
            content = f.read()

        assert len(content) > 100, "AC-3 FAIL: Summary file too short"
        assert "|" in content and "---" in content, \
            "AC-3 FAIL: No markdown table found"
        assert "Detector" in content or "Model" in content or "detector" in content, \
            "AC-3 FAIL: No detector column found"

    def test_ac4_scafad_f1_in_table(self, scafad_root):
        """AC-4: SCAFAD F1 result included in summary table."""
        filepath = scafad_root / "evaluation" / "results" / "baselines_summary.md"
        with open(filepath, 'r') as f:
            content = f.read()

        # Find SCAFAD row
        assert "SCAFAD" in content, "AC-4 FAIL: SCAFAD not in summary"

        # Extract all SCAFAD lines
        lines = content.split('\n')
        scafad_table_rows = [line for line in lines if "SCAFAD" in line and "|" in line]
        assert len(scafad_table_rows) > 0, "AC-4 FAIL: SCAFAD table row not found"

        # Check for F1 value in the table row
        scafad_row = scafad_table_rows[0]
        assert "1.0000" in scafad_row, \
            f"AC-4 FAIL: SCAFAD F1 value (1.0000) not found in row: {scafad_row}"


class TestIntegration:
    """Integration tests for WP-4.2 components."""

    def test_detectors_instantiable(self):
        """All detectors should be instantiable."""
        from evaluation.baselines.classical_detectors import (
            StatisticalZScoreDetector,
            StatisticalIQRDetector,
            MovingAverageDetector,
            IsolationForestDetector,
            OneClassSVMDetector,
            LocalOutlierFactorDetector,
            EllipticEnvelopeDetector,
            KMeansDetector,
            DBSCANAnomalyDetector,
        )

        detectors = [
            StatisticalZScoreDetector,
            StatisticalIQRDetector,
            MovingAverageDetector,
            IsolationForestDetector,
            OneClassSVMDetector,
            LocalOutlierFactorDetector,
            EllipticEnvelopeDetector,
            KMeansDetector,
            DBSCANAnomalyDetector,
        ]

        for detector_class in detectors:
            try:
                instance = detector_class()
                assert instance is not None, f"{detector_class.__name__} instantiation failed"
            except Exception as e:
                pytest.fail(f"Failed to instantiate {detector_class.__name__}: {e}")

    def test_results_and_summary_consistency(self):
        """Verify results.json and summary.md are consistent."""
        from pathlib import Path

        scafad_root = Path(__file__).parent.parent.parent

        # Load results
        with open(scafad_root / "evaluation" / "results" / "baselines_results.json") as f:
            results = json.load(f)

        # Load summary
        with open(scafad_root / "evaluation" / "results" / "baselines_summary.md") as f:
            summary = f.read()

        # Check that models from results appear in summary
        model_count_in_results = len(results["models"])
        model_count_in_summary = summary.count("|") // 5  # Rough estimate based on table structure

        assert model_count_in_summary > 0, "No models found in summary"
        # Summary should mention multiple models
        assert any(model["name"] in summary for model in results["models"][:3]), \
            "Top models not found in summary"

    def test_wp42_results_files_are_recent(self):
        """Verify that results files were recently generated (not stale)."""
        from pathlib import Path
        import time

        scafad_root = Path(__file__).parent.parent.parent
        results_file = scafad_root / "evaluation" / "results" / "baselines_results.json"
        summary_file = scafad_root / "evaluation" / "results" / "baselines_summary.md"

        # Check that files exist and are not empty
        assert results_file.stat().st_size > 100, "baselines_results.json is suspiciously small"
        assert summary_file.stat().st_size > 100, "baselines_summary.md is suspiciously small"

        # Files should have been modified within the last 7 days (reasonable threshold)
        now = time.time()
        max_age_seconds = 7 * 24 * 60 * 60
        results_age = now - results_file.stat().st_mtime
        summary_age = now - summary_file.stat().st_mtime

        assert results_age < max_age_seconds, f"baselines_results.json is too old ({results_age/3600:.1f} hours)"
        assert summary_age < max_age_seconds, f"baselines_summary.md is too old ({summary_age/3600:.1f} hours)"
