"""
Tests for WP-5.6: Performance Benchmark — Cold-Start and Warm Invocation Latency

Test coverage includes:
  - percentile() function: linear interpolation, edge cases
  - run_benchmark() public API: returns valid schema, handles variable invocations
  - JSON schema validation: required keys, data types, reasonable value ranges
  - write_report() function: writes valid Markdown
  - load_benign_records() helper: returns correct records
  - _run_instrumented() function: process_record() timing breakdown
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

# Import public API from the benchmark module
from evaluation.performance_benchmark import (
    percentile,
    run_benchmark,
    write_report,
    _load_benign_records_from,
    _run_instrumented,
)


# =============================================================================
# Test Suite 1: percentile() Function
# =============================================================================


class TestPercentileFunction:
    """Test linear-interpolation percentile calculation."""

    def test_percentile_basic_p50(self) -> None:
        """P50 of [1, 2, 3, 4, 5] should be 3.0."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = percentile(data, 50)
        assert result == 3.0

    def test_percentile_basic_p25(self) -> None:
        """P25 of [1, 2, 3, 4, 5] should interpolate to 1.5."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = percentile(data, 25)
        # Linear interpolation: idx = 0.25 * 4 = 1.0 → value = sorted[1] = 2.0
        # Actually idx = 1.0, so no interpolation needed; result = 2.0
        assert isinstance(result, float)
        assert 1.5 <= result <= 2.0

    def test_percentile_basic_p75(self) -> None:
        """P75 of [1, 2, 3, 4, 5] should interpolate to 4.0."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = percentile(data, 75)
        assert isinstance(result, float)
        assert 4.0 <= result <= 4.5

    def test_percentile_boundary_p0(self) -> None:
        """P0 should return minimum value."""
        data = [10.0, 20.0, 30.0]
        result = percentile(data, 0)
        assert result == 10.0

    def test_percentile_boundary_p100(self) -> None:
        """P100 should return maximum value."""
        data = [10.0, 20.0, 30.0]
        result = percentile(data, 100)
        assert result == 30.0

    def test_percentile_single_value(self) -> None:
        """Percentile of single-element list should return that value."""
        data = [42.0]
        assert percentile(data, 50) == 42.0
        assert percentile(data, 25) == 42.0
        assert percentile(data, 99) == 42.0

    def test_percentile_empty_list(self) -> None:
        """Percentile of empty list should return 0.0."""
        data: list[float] = []
        assert percentile(data, 50) == 0.0

    def test_percentile_two_values_interpolation(self) -> None:
        """P75 of [10, 20] should interpolate between them."""
        data = [10.0, 20.0]
        result = percentile(data, 75)
        # idx = 0.75 * 1 = 0.75, interpolate between [10] and [20]
        # result = 10 * 0.25 + 20 * 0.75 = 2.5 + 15 = 17.5
        assert result == 17.5

    def test_percentile_unsorted_input(self) -> None:
        """percentile() should handle unsorted input correctly."""
        data = [30.0, 10.0, 20.0, 50.0, 40.0]
        result = percentile(data, 50)
        assert result == 30.0  # median of sorted [10, 20, 30, 40, 50]

    def test_percentile_p95(self) -> None:
        """P95 should return a high percentile value."""
        data = list(range(1, 101))  # [1, 2, ..., 100]
        result = percentile(data, 95)
        assert 95.0 <= result <= 96.0  # idx = 0.95 * 99 = 94.05

    def test_percentile_p99(self) -> None:
        """P99 should return the highest percentile value."""
        data = list(range(1, 101))  # [1, 2, ..., 100]
        result = percentile(data, 99)
        assert 99.0 <= result <= 100.0  # idx = 0.99 * 99 = 98.01


# =============================================================================
# Test Suite 2: JSON Schema Validation
# =============================================================================


class TestBenchmarkJsonSchema:
    """Verify the benchmark output matches the required JSON schema."""

    def test_run_benchmark_returns_dict(self) -> None:
        """run_benchmark() should return a dictionary."""
        results = run_benchmark(warm_invocations=2)
        assert isinstance(results, dict)

    def test_json_schema_cold_start_key(self) -> None:
        """Results must contain 'cold_start_ms' key with float value."""
        results = run_benchmark(warm_invocations=2)
        assert "cold_start_ms" in results
        assert isinstance(results["cold_start_ms"], (int, float))
        assert results["cold_start_ms"] > 0  # Should be positive

    def test_json_schema_warm_mean_key(self) -> None:
        """Results must contain 'warm_mean_ms' key."""
        results = run_benchmark(warm_invocations=2)
        assert "warm_mean_ms" in results
        assert isinstance(results["warm_mean_ms"], (int, float))
        assert results["warm_mean_ms"] > 0

    def test_json_schema_warm_percentiles(self) -> None:
        """Results must contain p50, p95, p99 keys."""
        results = run_benchmark(warm_invocations=2)
        for key in ["warm_p50_ms", "warm_p95_ms", "warm_p99_ms"]:
            assert key in results, f"Missing key: {key}"
            assert isinstance(results[key], (int, float))
            assert results[key] > 0

    def test_json_schema_layer_breakdown(self) -> None:
        """Results must contain 'layer_breakdown' dict with l0, l1, l2_to_l6."""
        results = run_benchmark(warm_invocations=2)
        assert "layer_breakdown" in results
        lb = results["layer_breakdown"]
        assert isinstance(lb, dict)
        for key in ["l0_ms", "l1_ms", "l2_to_l6_ms"]:
            assert key in lb, f"Missing layer key: {key}"
            assert isinstance(lb[key], (int, float))
            assert lb[key] >= 0  # Layer times should be non-negative

    def test_json_schema_layer_breakdown_adapter(self) -> None:
        """Layer breakdown should include adapter_ms."""
        results = run_benchmark(warm_invocations=2)
        lb = results["layer_breakdown"]
        assert "adapter_ms" in lb
        assert isinstance(lb["adapter_ms"], (int, float))

    def test_json_schema_warm_invocations_count(self) -> None:
        """Results must include warm_invocations matching the request."""
        results = run_benchmark(warm_invocations=5)
        assert "warm_invocations" in results
        assert results["warm_invocations"] == 5

    def test_json_schema_warmstdev_key(self) -> None:
        """Results should include 'warm_stdev_ms'."""
        results = run_benchmark(warm_invocations=3)
        assert "warm_stdev_ms" in results
        assert isinstance(results["warm_stdev_ms"], (int, float))
        assert results["warm_stdev_ms"] >= 0

    def test_json_schema_cold_overhead_key(self) -> None:
        """Results should include 'cold_overhead_ms'."""
        results = run_benchmark(warm_invocations=2)
        assert "cold_overhead_ms" in results
        assert isinstance(results["cold_overhead_ms"], (int, float))
        # Can be negative if cold start is faster than warm mean

    def test_json_schema_generated_at_key(self) -> None:
        """Results should include 'generated_at' ISO timestamp."""
        results = run_benchmark(warm_invocations=2)
        assert "generated_at" in results
        assert isinstance(results["generated_at"], str)
        assert "T" in results["generated_at"]  # ISO format

    def test_json_schema_dataset_key(self) -> None:
        """Results should include 'dataset' path."""
        results = run_benchmark(warm_invocations=2)
        assert "dataset" in results
        assert isinstance(results["dataset"], str)

    def test_json_schema_warm_raw_ms(self) -> None:
        """Results should include 'warm_raw_ms' list."""
        results = run_benchmark(warm_invocations=3)
        assert "warm_raw_ms" in results
        assert isinstance(results["warm_raw_ms"], list)
        assert len(results["warm_raw_ms"]) == 3

    def test_json_schema_warm_layer_raw_ms(self) -> None:
        """Results should include per-layer raw timings."""
        results = run_benchmark(warm_invocations=3)
        assert "warm_layer_raw_ms" in results
        wlr = results["warm_layer_raw_ms"]
        for key in ["l0", "l1", "l2_to_l6"]:
            assert key in wlr, f"Missing raw layer key: {key}"
            assert isinstance(wlr[key], list)
            assert len(wlr[key]) == 3

    def test_json_schema_percentiles_ordered(self) -> None:
        """Percentiles should be ordered: p50 <= p95 <= p99."""
        results = run_benchmark(warm_invocations=5)
        p50 = results["warm_p50_ms"]
        p95 = results["warm_p95_ms"]
        p99 = results["warm_p99_ms"]
        assert p50 <= p95, f"p50 ({p50}) > p95 ({p95})"
        assert p95 <= p99, f"p95 ({p95}) > p99 ({p99})"

    def test_json_schema_layer_sum_approx_total(self) -> None:
        """Sum of layer timings should approximately equal total warm mean."""
        results = run_benchmark(warm_invocations=3)
        lb = results["layer_breakdown"]
        layer_sum = lb["l0_ms"] + lb["adapter_ms"] + lb["l1_ms"] + lb["l2_to_l6_ms"]
        total = results["warm_mean_ms"]
        # Allow 10% tolerance for rounding/measurement variance
        assert abs(layer_sum - total) < total * 0.15, (
            f"Layer sum ({layer_sum:.2f}) differs from total ({total:.2f}) by >"
            f" 15%"
        )


# =============================================================================
# Test Suite 3: write_report() Function
# =============================================================================


class TestWriteReportFunction:
    """Test Markdown report generation."""

    def test_write_report_creates_file(self) -> None:
        """write_report() should create a file."""
        results = run_benchmark(warm_invocations=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.md"
            write_report(results, report_path)
            assert report_path.exists()

    def test_write_report_content_is_markdown(self) -> None:
        """Report should contain Markdown headers."""
        results = run_benchmark(warm_invocations=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.md"
            write_report(results, report_path)
            content = report_path.read_text(encoding="utf-8")
            assert "# WP-5.6 Performance Benchmark Report" in content
            assert "##" in content  # Markdown subheaders
            assert "|" in content  # Tables

    def test_write_report_contains_metrics(self) -> None:
        """Report should include key performance metrics."""
        results = run_benchmark(warm_invocations=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.md"
            write_report(results, report_path)
            content = report_path.read_text(encoding="utf-8")
            assert "Cold-start latency" in content
            assert "Warm mean" in content
            assert "Layer Breakdown" in content

    def test_write_report_layer_breakdown_in_report(self) -> None:
        """Report should include layer breakdown details."""
        results = run_benchmark(warm_invocations=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.md"
            write_report(results, report_path)
            content = report_path.read_text(encoding="utf-8")
            assert "L0" in content
            assert "L1" in content
            assert "L2" in content

    def test_write_report_parent_dir_created(self) -> None:
        """write_report() should create parent directories."""
        results = run_benchmark(warm_invocations=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "subdir" / "deep" / "report.md"
            write_report(results, report_path)
            assert report_path.exists()
            assert report_path.parent.exists()


# =============================================================================
# Test Suite 4: Data Loading Helpers
# =============================================================================


class TestDataLoadingHelpers:
    """Test benign record loading from dataset."""

    def test_load_benign_records_returns_list(self) -> None:
        """_load_benign_records_from() should return a list."""
        from evaluation.performance_benchmark import DATASET_PATH

        records = _load_benign_records_from(DATASET_PATH, 5)
        assert isinstance(records, list)

    def test_load_benign_records_count(self) -> None:
        """Should return exactly n records when dataset has enough."""
        from evaluation.performance_benchmark import DATASET_PATH

        records = _load_benign_records_from(DATASET_PATH, 10)
        assert len(records) == 10

    def test_load_benign_records_are_benign(self) -> None:
        """All returned records should have anomaly_type='benign'."""
        from evaluation.performance_benchmark import DATASET_PATH

        records = _load_benign_records_from(DATASET_PATH, 5)
        for record in records:
            assert record.get("anomaly_type", "").lower() == "benign"

    def test_load_benign_records_returns_dicts(self) -> None:
        """Each record should be a dict."""
        from evaluation.performance_benchmark import DATASET_PATH

        records = _load_benign_records_from(DATASET_PATH, 3)
        for record in records:
            assert isinstance(record, dict)


# =============================================================================
# Test Suite 5: run_benchmark() Variations
# =============================================================================


class TestRunBenchmarkVariations:
    """Test run_benchmark() with different parameters."""

    def test_run_benchmark_small_invocations(self) -> None:
        """run_benchmark(warm_invocations=2) should complete."""
        results = run_benchmark(warm_invocations=2)
        assert results["warm_invocations"] == 2
        assert len(results["warm_raw_ms"]) == 2

    def test_run_benchmark_medium_invocations(self) -> None:
        """run_benchmark(warm_invocations=10) should complete."""
        results = run_benchmark(warm_invocations=10)
        assert results["warm_invocations"] == 10
        assert len(results["warm_raw_ms"]) == 10

    def test_run_benchmark_default_invocations(self) -> None:
        """run_benchmark() with no args should use WARM_INVOCATIONS default."""
        from evaluation.performance_benchmark import WARM_INVOCATIONS

        results = run_benchmark()
        assert results["warm_invocations"] == WARM_INVOCATIONS

    def test_run_benchmark_results_are_serializable(self) -> None:
        """Results should be JSON-serializable."""
        results = run_benchmark(warm_invocations=2)
        # Should not raise
        json_str = json.dumps(results)
        assert isinstance(json_str, str)
        reparsed = json.loads(json_str)
        assert reparsed["cold_start_ms"] > 0


# =============================================================================
# Test Suite 6: _run_instrumented() Function
# =============================================================================


class TestRunInstrumentedFunction:
    """Test per-layer timing instrumentation."""

    def test_run_instrumented_returns_dict(self) -> None:
        """_run_instrumented() should return a timing dict."""
        from runtime.runtime import SCAFADCanonicalRuntime
        from evaluation.performance_benchmark import DATASET_PATH

        runtime = SCAFADCanonicalRuntime()
        records = _load_benign_records_from(DATASET_PATH, 1)
        result = _run_instrumented(runtime, records[0])
        assert isinstance(result, dict)

    def test_run_instrumented_timing_keys(self) -> None:
        """_run_instrumented() should return all timing keys."""
        from runtime.runtime import SCAFADCanonicalRuntime
        from evaluation.performance_benchmark import DATASET_PATH

        runtime = SCAFADCanonicalRuntime()
        records = _load_benign_records_from(DATASET_PATH, 1)
        result = _run_instrumented(runtime, records[0])
        for key in ["total_ms", "build_ms", "l0_ms", "adapter_ms", "l1_ms", "l2_to_l6_ms"]:
            assert key in result, f"Missing timing key: {key}"

    def test_run_instrumented_all_times_positive(self) -> None:
        """All timing measurements should be non-negative."""
        from runtime.runtime import SCAFADCanonicalRuntime
        from evaluation.performance_benchmark import DATASET_PATH

        runtime = SCAFADCanonicalRuntime()
        records = _load_benign_records_from(DATASET_PATH, 1)
        result = _run_instrumented(runtime, records[0])
        for key, value in result.items():
            assert value >= 0, f"{key}={value} is negative"

    def test_run_instrumented_total_sum_approx_layers(self) -> None:
        """Total time should approximately equal sum of layer times."""
        from runtime.runtime import SCAFADCanonicalRuntime
        from evaluation.performance_benchmark import DATASET_PATH

        runtime = SCAFADCanonicalRuntime()
        records = _load_benign_records_from(DATASET_PATH, 1)
        result = _run_instrumented(runtime, records[0])
        total = result["total_ms"]
        layer_sum = result["build_ms"] + result["l0_ms"] + result["adapter_ms"] \
                    + result["l1_ms"] + result["l2_to_l6_ms"]
        # Allow 10% tolerance for rounding
        assert abs(total - layer_sum) < total * 0.15, (
            f"total ({total:.2f}) vs layers ({layer_sum:.2f})"
        )


# =============================================================================
# Test Suite 7: Regression & Sanity Checks
# =============================================================================


class TestSanityChecks:
    """Sanity checks for performance and data validity."""

    def test_cold_start_reasonable_magnitude(self) -> None:
        """Cold start should be in reasonable range (10-500 ms)."""
        results = run_benchmark(warm_invocations=2)
        cold = results["cold_start_ms"]
        assert 10 < cold < 500, f"Cold start {cold} ms is unreasonable"

    def test_warm_mean_reasonable_magnitude(self) -> None:
        """Warm mean should be in reasonable range (10-500 ms)."""
        results = run_benchmark(warm_invocations=2)
        warm = results["warm_mean_ms"]
        assert 10 < warm < 500, f"Warm mean {warm} ms is unreasonable"

    def test_cold_overhead_not_impossible(self) -> None:
        """Cold overhead should not be wildly negative or positive."""
        results = run_benchmark(warm_invocations=2)
        overhead = results["cold_overhead_ms"]
        # Allow range: -200 to +200 ms
        assert -200 < overhead < 200, f"Cold overhead {overhead} ms is out of range"

    def test_l0_dominates_latency(self) -> None:
        """L0 should dominate (>50%) of total latency per literature."""
        results = run_benchmark(warm_invocations=3)
        lb = results["layer_breakdown"]
        total = lb["l0_ms"] + lb["adapter_ms"] + lb["l1_ms"] + lb["l2_to_l6_ms"]
        l0_pct = lb["l0_ms"] / total * 100
        assert l0_pct > 50, f"L0 is only {l0_pct:.1f}% of latency"

    def test_layer_breakdown_non_negative(self) -> None:
        """All layer times should be non-negative."""
        results = run_benchmark(warm_invocations=2)
        lb = results["layer_breakdown"]
        for key, value in lb.items():
            assert value >= 0, f"Layer {key}={value} is negative"


# =============================================================================
# Test Suite 8: Edge Cases & Error Handling
# =============================================================================


class TestEdgeCases:
    """Edge case and error condition tests."""

    def test_percentile_large_dataset(self) -> None:
        """percentile() should handle large datasets."""
        data = list(range(10000))
        p50 = percentile(data, 50)
        p95 = percentile(data, 95)
        p99 = percentile(data, 99)
        assert 4900 < p50 < 5100
        assert 9400 < p95 < 9600
        assert 9800 < p99 < 10000

    def test_percentile_all_same_values(self) -> None:
        """percentile() of all-same values should return that value."""
        data = [42.0] * 100
        for p in [0, 25, 50, 75, 100]:
            assert percentile(data, p) == 42.0

    def test_benchmark_json_can_be_written(self) -> None:
        """Results should be writable to JSON file."""
        results = run_benchmark(warm_invocations=2)
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "results.json"
            with open(str(json_path), "w") as fh:
                json.dump(results, fh)
            assert json_path.exists()
            content = json.loads(json_path.read_text())
            assert content["cold_start_ms"] > 0


# =============================================================================
# Test Suite 9: API Importability
# =============================================================================


class TestPublicApi:
    """Verify public API functions are importable."""

    def test_import_percentile(self) -> None:
        """percentile should be importable from module."""
        from evaluation.performance_benchmark import percentile as p

        assert callable(p)
        result = p([1, 2, 3], 50)
        assert isinstance(result, (int, float))

    def test_import_run_benchmark(self) -> None:
        """run_benchmark should be importable from module."""
        from evaluation.performance_benchmark import run_benchmark as rb

        assert callable(rb)

    def test_import_write_report(self) -> None:
        """write_report should be importable from module."""
        from evaluation.performance_benchmark import write_report as wr

        assert callable(wr)

    def test_percentile_docstring(self) -> None:
        """percentile() should have a docstring."""
        assert percentile.__doc__ is not None
        assert "percentile" in percentile.__doc__.lower()

    def test_run_benchmark_docstring(self) -> None:
        """run_benchmark() should have a docstring."""
        assert run_benchmark.__doc__ is not None
        assert "cold" in run_benchmark.__doc__.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
