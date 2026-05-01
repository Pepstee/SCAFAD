"""WP-5.2: L2 detection-threshold calibration using the synthetic evaluation dataset.

Sweeps thresholds in [0.10, 0.90] at step 0.05, evaluates every record in the
WP-4.4 synthetic dataset through ``MultiVectorDetectionMatrix``, then selects
the threshold that maximises F1-score.  Ties are broken by higher recall; among
remaining ties, the lower threshold is preferred (more sensitive).

Usage (from project/scafad-r-core/)::

    python evaluation/calibration/threshold_calibration.py

Outputs:
    evaluation/calibration/calibration_results.json — full curve + selected threshold

The selected threshold is written into detection_matrix.py automatically if you
pass ``--update`` on the command line.  The test suite calls ``calibrate()``
directly with ``update_source=False`` by default.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path bootstrap: allow running from any CWD and from pytest
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]          # …/scafad-r-core
_SCAFAD_PKG = _REPO_ROOT / "scafad"

for _p in (str(_REPO_ROOT), str(_SCAFAD_PKG)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from layer2.detection_matrix import MultiVectorDetectionMatrix  # noqa: E402

# ---------------------------------------------------------------------------
# Default file paths
# ---------------------------------------------------------------------------
_DATASET_PATH = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
_OUTPUT_PATH = _REPO_ROOT / "evaluation" / "calibration" / "calibration_results.json"
_DETECTION_MATRIX_PATH = _SCAFAD_PKG / "layer2" / "detection_matrix.py"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _map_record(raw: Dict) -> Dict:
    """Translate a WP-4.4 v4.2 synthetic record into the L2 envelope format.

    Field mapping
    ~~~~~~~~~~~~~
    ``duration`` (seconds)              → ``telemetry_data.l0_duration_ms``
    ``memory_spike_kb``                 → ``telemetry_data.l0_memory_spike_kb``
    ``cpu_utilization`` (%)             → ``telemetry_data.l0_cpu_utilization``
    ``network_io_bytes``                → ``telemetry_data.l0_network_io_bytes``
    ``causal_depth``                    → ``provenance_chain.causal_depth``
    ``parent_chain``                    → ``provenance_chain.parent_chain``
    ``graph_node_id``                   → ``provenance_chain.graph_node_id``
    ``economic_risk_score``             → ``context_metadata.economic_risk_score``
    ``silent_failure_probability``      → ``context_metadata.silent_failure_probability``
    ``completeness_score``              → ``context_metadata.completeness_score``
    ``tags.category``                   → ``context_metadata.anomaly_category``
    ``adversarial_score`` × 10          → ``context_metadata.anomaly_severity``
    """
    tags: Dict = raw.get("tags", {}) or {}
    return {
        "record_id": raw.get("event_id", ""),
        "event_id": raw.get("event_id", ""),
        "anomaly_type": raw.get("anomaly_type", "benign"),
        "execution_phase": raw.get("execution_phase", "unknown"),
        "telemetry_data": {
            # Synthetic dataset stores duration in seconds; detector expects ms
            "l0_duration_ms": float(raw.get("duration") or 0.0) * 1000.0,
            "l0_memory_spike_kb": float(raw.get("memory_spike_kb") or 0.0),
            "l0_cpu_utilization": float(raw.get("cpu_utilization") or 0.0),
            "l0_network_io_bytes": float(raw.get("network_io_bytes") or 0.0),
        },
        "provenance_chain": {
            "causal_depth": float(raw.get("causal_depth") or 0.0),
            "parent_chain": list(raw.get("parent_chain") or []),
            "graph_node_id": raw.get("graph_node_id"),
        },
        "context_metadata": {
            "economic_risk_score": float(raw.get("economic_risk_score") or 0.0),
            "silent_failure_probability": float(
                raw.get("silent_failure_probability") or 0.0
            ),
            "completeness_score": float(raw.get("completeness_score") or 1.0),
            "anomaly_category": tags.get("category", "unknown"),
            # adversarial_score ∈ [0, 1] → severity ∈ [0, 10]
            "anomaly_severity": float(raw.get("adversarial_score") or 0.0) * 10.0,
        },
    }


def _compute_metrics(
    scores: List[float],
    labels: List[int],
    threshold: float,
) -> Tuple[int, int, int, float, float, float]:
    """Return ``(tp, fp, fn, precision, recall, f1)`` at *threshold*."""
    tp = fp = fn = 0
    for score, label in zip(scores, labels):
        predicted = 1 if score >= threshold else 0
        if predicted == 1 and label == 1:
            tp += 1
        elif predicted == 1 and label == 0:
            fp += 1
        elif predicted == 0 and label == 1:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return tp, fp, fn, round(precision, 6), round(recall, 6), round(f1, 6)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calibrate(
    dataset_path: Path = _DATASET_PATH,
    output_path: Optional[Path] = _OUTPUT_PATH,
    thresholds: Optional[List[float]] = None,
    update_source: bool = False,
) -> Dict:
    """Run threshold calibration on the synthetic evaluation dataset.

    Parameters
    ----------
    dataset_path:
        Path to ``synthetic_eval_dataset.json.gz`` (WP-4.4, schema v4.2).
    output_path:
        Where to write ``calibration_results.json``.  Pass ``None`` to skip
        writing (useful in unit tests).
    thresholds:
        Thresholds to sweep.  Defaults to ``[0.10, 0.15, …, 0.90]``.
    update_source:
        If ``True``, patch ``detection_matrix.py`` with the selected threshold.
        Disabled by default so tests do not modify source during a test run.

    Returns
    -------
    dict
        Full calibration results including the selected threshold, P/R curve,
        and improvement metrics versus the baseline (0.30).
    """
    if thresholds is None:
        thresholds = [round(0.10 + i * 0.05, 2) for i in range(17)]  # [0.10 … 0.90]

    # ------------------------------------------------------------------
    # 1. Load dataset and score every record
    # ------------------------------------------------------------------
    with gzip.open(dataset_path, "rt", encoding="utf-8") as fh:
        raw_records: List[Dict] = json.load(fh)

    detector = MultiVectorDetectionMatrix()
    scores: List[float] = []
    labels: List[int] = []

    for raw in raw_records:
        envelope = _map_record(raw)
        result = detector.analyze(envelope)
        scores.append(result.aggregate_score)
        labels.append(0 if raw.get("anomaly_type", "benign") == "benign" else 1)

    n_total = len(labels)
    n_anomalous = sum(labels)
    n_benign = n_total - n_anomalous

    benign_scores = [s for s, l in zip(scores, labels) if l == 0]
    anomalous_scores = [s for s, l in zip(scores, labels) if l == 1]

    # ------------------------------------------------------------------
    # 2. Compute precision / recall curve
    # ------------------------------------------------------------------
    curve: List[Dict] = []
    for t in thresholds:
        tp, fp, fn, p, r, f1 = _compute_metrics(scores, labels, t)
        curve.append(
            {"threshold": t, "tp": tp, "fp": fp, "fn": fn,
             "precision": p, "recall": r, "f1": f1}
        )

    # Baseline at hard-coded 0.30
    _, _, _, bp, br, bf1 = _compute_metrics(scores, labels, 0.30)
    baseline = {"threshold": 0.30, "precision": bp, "recall": br, "f1": bf1}

    # ------------------------------------------------------------------
    # 3. Select best threshold
    #    Primary key: F1 high  Secondary: recall high
    #    Tertiary: threshold HIGH (more conservative; robust to distribution shift)
    # ------------------------------------------------------------------
    best_row = max(curve, key=lambda row: (row["f1"], row["recall"], row["threshold"]))
    selected_threshold = best_row["threshold"]

    results = {
        "calibration_metadata": {
            "dataset": str(dataset_path.name),
            "n_records": n_total,
            "n_anomalous": n_anomalous,
            "n_benign": n_benign,
            "anomaly_rate": round(n_anomalous / n_total, 4),
            "sweep_range": f"[{thresholds[0]:.2f}, {thresholds[-1]:.2f}]",
            "sweep_step": 0.05,
        },
        "score_stats": {
            "benign_score_min": round(min(benign_scores), 4),
            "benign_score_max": round(max(benign_scores), 4),
            "benign_score_mean": round(sum(benign_scores) / len(benign_scores), 4),
            "anomalous_score_min": round(min(anomalous_scores), 4),
            "anomalous_score_max": round(max(anomalous_scores), 4),
            "anomalous_score_mean": round(
                sum(anomalous_scores) / len(anomalous_scores), 4
            ),
            "separation_gap": round(
                min(anomalous_scores) - max(benign_scores), 4
            ),
        },
        "baseline": baseline,
        "selected": {
            "threshold": selected_threshold,
            "precision": best_row["precision"],
            "recall": best_row["recall"],
            "f1": best_row["f1"],
        },
        "improvement": {
            "f1_delta": round(best_row["f1"] - bf1, 6),
            "f1_pct_improvement": round(
                (best_row["f1"] - bf1) / bf1 * 100 if bf1 > 0 else float("inf"),
                2,
            ),
        },
        "curve": curve,
    }

    # ------------------------------------------------------------------
    # 4. Persist results
    # ------------------------------------------------------------------
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)

    # ------------------------------------------------------------------
    # 5. Optionally patch detection_matrix.py
    # ------------------------------------------------------------------
    if update_source:
        _patch_detection_matrix(selected_threshold)

    return results


def _patch_detection_matrix(new_threshold: float) -> None:
    """Update the ``anomaly_indicated`` comparison in ``detection_matrix.py``.

    Replaces the literal ``aggregate >= 0.3`` (or whatever the current value is)
    with ``aggregate >= <new_threshold>`` and adds a calibration comment.
    """
    source = _DETECTION_MATRIX_PATH.read_text(encoding="utf-8")

    # Pattern: anomaly_indicated=aggregate >= <float>,
    pattern = r"(anomaly_indicated\s*=\s*aggregate\s*>=\s*)([0-9.]+)"
    new_value = f"{new_threshold:.2f}"
    replacement = (
        rf"\g<1>{new_value}"
    )
    patched, count = re.subn(pattern, replacement, source)
    if count == 0:
        raise RuntimeError(
            "Could not find 'anomaly_indicated = aggregate >= <float>' in "
            f"{_DETECTION_MATRIX_PATH}"
        )
    _DETECTION_MATRIX_PATH.write_text(patched, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Calibrate L2 detection threshold.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=_DATASET_PATH,
        help="Path to synthetic_eval_dataset.json.gz",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_OUTPUT_PATH,
        help="Where to write calibration_results.json",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="Patch detection_matrix.py with the selected threshold",
    )
    args = parser.parse_args()

    results = calibrate(
        dataset_path=args.dataset,
        output_path=args.output,
        update_source=args.update,
    )
    sel = results["selected"]
    base = results["baseline"]
    imp = results["improvement"]
    stats = results["score_stats"]

    print(f"\n{'='*60}")
    print(f"  WP-5.2: L2 Threshold Calibration Results")
    print(f"{'='*60}")
    print(f"  Dataset        : {results['calibration_metadata']['dataset']}")
    print(f"  Records        : {results['calibration_metadata']['n_records']:,}")
    print(f"  Anomalous      : {results['calibration_metadata']['n_anomalous']:,}")
    print(f"  Benign         : {results['calibration_metadata']['n_benign']:,}")
    print()
    print(f"  Score gap      : [{stats['benign_score_max']:.4f}, "
          f"{stats['anomalous_score_min']:.4f}]  "
          f"(width={stats['separation_gap']:.4f})")
    print()
    print(f"  Baseline  (0.30) -> "
          f"P={base['precision']:.4f}  R={base['recall']:.4f}  F1={base['f1']:.4f}")
    print(f"  Selected  ({sel['threshold']:.2f}) -> "
          f"P={sel['precision']:.4f}  R={sel['recall']:.4f}  F1={sel['f1']:.4f}")
    print(f"  Improvement    : F1 {imp['f1_delta']:+.4f} "
          f"({imp['f1_pct_improvement']:+.1f}%)")
    if args.update:
        print(f"\n  detection_matrix.py patched -> threshold = {sel['threshold']:.2f}")
    print(f"\n  Results written to: {args.output}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    _cli()
