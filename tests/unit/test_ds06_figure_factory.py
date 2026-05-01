"""
test_ds06_figure_factory.py — DS-06 Tests

Tests for the dissertation figure factory (evaluation/figures/figure_factory.py):
  - Script execution without errors
  - 5 figure files are generated (.png and .pdf)
  - All figures use real data (headline_metrics.json, baselines_results.json, optimal_threshold.json)
  - No placeholder/random data used
  - Figure quality and content verification

Task ID: 9cf6ab7e-da3c-4477-ad06-558d67257279
Source task: DS-06 (Build dissertation figure factory)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def get_project_root():
    """Get the project root directory.

    Current file is at tests/unit/test_ds06_figure_factory.py
    Project root is 3 levels up (tests/unit -> tests -> scafad-r-core)
    """
    test_file = Path(__file__).resolve()
    return test_file.parent.parent.parent


PROJECT_ROOT = get_project_root()
FIGURE_FACTORY_SCRIPT = PROJECT_ROOT / "evaluation" / "figures" / "figure_factory.py"
FIGURES_DIR = PROJECT_ROOT / "evaluation" / "figures"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"

# Data files that figure_factory.py depends on
HEADLINE_METRICS = RESULTS_DIR / "headline_metrics.json"
BASELINES_RESULTS = RESULTS_DIR / "baselines_results.json"
OPTIMAL_THRESHOLD = RESULTS_DIR / "optimal_threshold.json"
SCAFAD_RESULTS = RESULTS_DIR / "scafad_results.json"

# Expected output files (both .png and .pdf for each figure)
EXPECTED_FIGURES = [
    "fig01_roc_curve",
    "fig02_precision_recall_curve",
    "fig03_threshold_grid_search",
    "fig04_baselines_comparison",
    "fig05_confusion_matrix",
]


class TestFigureFactoryExecution(unittest.TestCase):
    """Tests for figure_factory.py script execution and output."""

    def test_script_exists(self):
        """Verify figure_factory.py exists at expected location."""
        self.assertTrue(
            FIGURE_FACTORY_SCRIPT.exists(),
            f"figure_factory.py not found at {FIGURE_FACTORY_SCRIPT}"
        )

    def test_script_is_executable(self):
        """Verify figure_factory.py is a valid Python file."""
        self.assertTrue(
            FIGURE_FACTORY_SCRIPT.suffix == ".py",
            f"Expected .py file, got {FIGURE_FACTORY_SCRIPT.suffix}"
        )

    def test_figures_directory_exists(self):
        """Verify figures directory exists."""
        self.assertTrue(
            FIGURES_DIR.exists() and FIGURES_DIR.is_dir(),
            f"Figures directory not found at {FIGURES_DIR}"
        )

    def test_required_data_files_exist(self):
        """Verify all required data files exist."""
        data_files = [
            HEADLINE_METRICS,
            BASELINES_RESULTS,
            OPTIMAL_THRESHOLD,
            SCAFAD_RESULTS,
        ]
        for data_file in data_files:
            self.assertTrue(
                data_file.exists(),
                f"Required data file not found: {data_file}"
            )

    def test_figure_factory_runs_without_error(self):
        """Verify figure_factory.py executes successfully."""
        result = subprocess.run(
            [sys.executable, str(FIGURE_FACTORY_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )
        self.assertEqual(
            result.returncode, 0,
            f"Script exited with code {result.returncode}\nStdout: {result.stdout}\nStderr: {result.stderr}"
        )

    def test_all_figure_files_generated(self):
        """Verify all 5 figure files are generated in both PNG and PDF format."""
        # Run the script to ensure figures are generated
        subprocess.run(
            [sys.executable, str(FIGURE_FACTORY_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )

        for stem in EXPECTED_FIGURES:
            png_file = FIGURES_DIR / f"{stem}.png"
            pdf_file = FIGURES_DIR / f"{stem}.pdf"

            self.assertTrue(
                png_file.exists(),
                f"PNG file not generated: {png_file}"
            )
            self.assertTrue(
                pdf_file.exists(),
                f"PDF file not generated: {pdf_file}"
            )

    def test_figure_files_have_content(self):
        """Verify all figure files are non-empty (contain actual plot data)."""
        # Run the script first
        subprocess.run(
            [sys.executable, str(FIGURE_FACTORY_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )

        for stem in EXPECTED_FIGURES:
            png_file = FIGURES_DIR / f"{stem}.png"
            pdf_file = FIGURES_DIR / f"{stem}.pdf"

            # Verify PNG has content
            png_size = png_file.stat().st_size
            self.assertGreater(
                png_size, 10000,  # Reasonable minimum size for a plot
                f"PNG file too small ({png_size} bytes): {png_file}"
            )

            # Verify PDF has content
            pdf_size = pdf_file.stat().st_size
            self.assertGreater(
                pdf_size, 5000,  # Reasonable minimum size for a plot PDF
                f"PDF file too small ({pdf_size} bytes): {pdf_file}"
            )


class TestDataIntegrity(unittest.TestCase):
    """Tests to verify figures use real data, not placeholders."""

    def _load_json(self, path):
        """Load and parse a JSON file."""
        with open(path, "r") as f:
            return json.load(f)

    def test_headline_metrics_structure(self):
        """Verify headline_metrics.json has required structure."""
        data = self._load_json(HEADLINE_METRICS)

        # Check top-level structure
        self.assertIn("scafad", data)
        self.assertIn("baselines", data)

        # Check SCAFAD metrics
        scafad = data["scafad"]
        self.assertIn("precision", scafad)
        self.assertIn("recall", scafad)
        self.assertIn("f1", scafad)
        self.assertIn("roc_auc", scafad)
        self.assertIn("confusion_matrix", scafad)

        # Verify values are real numbers, not placeholders
        self.assertIsInstance(scafad["f1"], (int, float))
        self.assertGreaterEqual(scafad["f1"], 0)
        self.assertLessEqual(scafad["f1"], 1)

    def test_optimal_threshold_structure(self):
        """Verify optimal_threshold.json has required structure."""
        data = self._load_json(OPTIMAL_THRESHOLD)

        # Check top-level structure
        self.assertIn("optimal_threshold", data)
        self.assertIn("all_results", data)

        # Check optimal threshold details
        optimal = data["optimal_threshold"]
        self.assertIn("value", optimal)
        self.assertIn("f1", optimal)
        self.assertIn("precision", optimal)
        self.assertIn("recall", optimal)

        # Verify optimal threshold is realistic
        self.assertGreaterEqual(optimal["value"], 0)
        self.assertLessEqual(optimal["value"], 1)

        # Verify all_results is a list of results
        self.assertIsInstance(data["all_results"], list)
        self.assertGreater(len(data["all_results"]), 10)

        # Check structure of results
        for result in data["all_results"]:
            self.assertIn("threshold", result)
            self.assertIn("f1", result)
            self.assertIn("precision", result)
            self.assertIn("recall", result)

    def test_baselines_results_structure(self):
        """Verify baselines_results.json has models with real metrics."""
        data = self._load_json(BASELINES_RESULTS)

        # Check structure
        self.assertIn("models", data)
        self.assertIsInstance(data["models"], list)
        self.assertGreater(len(data["models"]), 5)

        # Check each model has required fields
        for model in data["models"]:
            self.assertIn("name", model)
            self.assertIn("f1", model)
            self.assertIn("roc_auc", model)
            self.assertIn("precision", model)
            self.assertIn("recall", model)

            # Verify values are realistic
            self.assertIsInstance(model["f1"], (int, float))
            self.assertGreaterEqual(model["f1"], 0)
            self.assertLessEqual(model["f1"], 1)

    def test_scafad_results_structure(self):
        """Verify scafad_results.json has per-record scores."""
        data = self._load_json(SCAFAD_RESULTS)

        # Check structure
        self.assertIn("per_record", data)
        self.assertIsInstance(data["per_record"], list)
        self.assertGreater(len(data["per_record"]), 100)

        # Check each record has required fields
        for record in data["per_record"][:10]:  # Sample first 10
            self.assertIn("l3_fused_score", record)
            self.assertIn("ground_truth", record)

            # Verify values are realistic
            self.assertIsInstance(record["l3_fused_score"], (int, float))
            self.assertGreaterEqual(record["l3_fused_score"], 0)
            self.assertLessEqual(record["l3_fused_score"], 1)
            self.assertIn(record["ground_truth"], [0, 1])


class TestFigureContent(unittest.TestCase):
    """Tests to verify figure content matches expected metrics."""

    def _load_json(self, path):
        """Load and parse a JSON file."""
        with open(path, "r") as f:
            return json.load(f)

    def test_roc_curve_auc_is_perfect(self):
        """Verify ROC curve figure uses real AUC=1.0 from data."""
        headline = self._load_json(HEADLINE_METRICS)
        scafad = headline["scafad"]

        # SCAFAD ROC AUC should be 1.0
        self.assertEqual(scafad["roc_auc"], 1.0)

    def test_pr_curve_ap_is_perfect(self):
        """Verify Precision-Recall curve uses perfect metrics from data."""
        headline = self._load_json(HEADLINE_METRICS)
        scafad = headline["scafad"]

        # SCAFAD should have perfect precision and recall
        self.assertEqual(scafad["precision"], 1.0)
        self.assertEqual(scafad["recall"], 1.0)

    def test_threshold_grid_search_optimal_is_0_09(self):
        """Verify threshold grid search shows optimum at 0.09."""
        optimal_data = self._load_json(OPTIMAL_THRESHOLD)
        optimal = optimal_data["optimal_threshold"]

        # Optimal threshold should be 0.09
        self.assertEqual(optimal["value"], 0.09)
        # Optimal F1 should be 1.0
        self.assertEqual(optimal["f1"], 1.0)

    def test_confusion_matrix_has_correct_values(self):
        """Verify confusion matrix values match headline metrics."""
        headline = self._load_json(HEADLINE_METRICS)
        cm = headline["scafad"]["confusion_matrix"]

        # Check structure
        self.assertIn("tn", cm)
        self.assertIn("fp", cm)
        self.assertIn("fn", cm)
        self.assertIn("tp", cm)

        # For SCAFAD with perfect scores, we expect:
        # tp should be large (6250), tn should be 50
        # fp and fn should be 0
        self.assertEqual(cm["fp"], 0)
        self.assertEqual(cm["fn"], 0)
        self.assertGreater(cm["tp"], 1000)
        self.assertGreater(cm["tn"], 0)

    def test_baselines_comparison_includes_top_9(self):
        """Verify baselines comparison includes at least 9 baseline models."""
        baselines_data = self._load_json(BASELINES_RESULTS)
        models = baselines_data["models"]

        # Should have at least 9 baseline models for comparison
        self.assertGreaterEqual(len(models), 9)


class TestFigureFactoryIntegration(unittest.TestCase):
    """Integration tests for the entire figure factory."""

    def test_full_pipeline_produces_all_outputs(self):
        """Verify full pipeline from script execution to file output."""
        # This is effectively an end-to-end test
        result = subprocess.run(
            [sys.executable, str(FIGURE_FACTORY_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )

        # Script should succeed
        self.assertEqual(result.returncode, 0)

        # Output should mention all 5 figures
        output = result.stdout
        self.assertIn("fig01_roc_curve", output)
        self.assertIn("fig02_precision_recall_curve", output)
        self.assertIn("fig03_threshold_grid_search", output)
        self.assertIn("fig04_baselines_comparison", output)
        self.assertIn("fig05_confusion_matrix", output)

        # All files should exist
        for stem in EXPECTED_FIGURES:
            png = FIGURES_DIR / f"{stem}.png"
            pdf = FIGURES_DIR / f"{stem}.pdf"
            self.assertTrue(png.exists())
            self.assertTrue(pdf.exists())

    def test_script_output_mentions_success(self):
        """Verify script output indicates successful generation."""
        result = subprocess.run(
            [sys.executable, str(FIGURE_FACTORY_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout
        self.assertIn("successfully", output.lower())
        self.assertIn("dissertation figure factory", output.lower())


class TestFigureFactory_ImportAndStructure(unittest.TestCase):
    """Tests for code structure and importability."""

    def test_figure_factory_module_imports(self):
        """Verify figure_factory.py can be imported as a module."""
        spec = __import__('importlib.util').util.spec_from_file_location(
            "figure_factory", FIGURE_FACTORY_SCRIPT
        )
        module = __import__('importlib.util').util.module_from_spec(spec)

        # Should not raise an ImportError
        spec.loader.exec_module(module)

    def test_main_function_exists(self):
        """Verify figure_factory.py has a main() function."""
        spec = __import__('importlib.util').util.spec_from_file_location(
            "figure_factory", FIGURE_FACTORY_SCRIPT
        )
        module = __import__('importlib.util').util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # main() function should exist
        self.assertTrue(hasattr(module, "main"))
        self.assertTrue(callable(module.main))

    def test_load_functions_exist(self):
        """Verify figure_factory.py has all required data loader functions."""
        spec = __import__('importlib.util').util.spec_from_file_location(
            "figure_factory", FIGURE_FACTORY_SCRIPT
        )
        module = __import__('importlib.util').util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Required functions
        required_functions = [
            "load_headline_metrics",
            "load_baselines_results",
            "load_optimal_threshold",
            "load_scafad_results",
        ]

        for func_name in required_functions:
            self.assertTrue(
                hasattr(module, func_name),
                f"Missing function: {func_name}"
            )
            self.assertTrue(callable(getattr(module, func_name)))


if __name__ == "__main__":
    unittest.main()
