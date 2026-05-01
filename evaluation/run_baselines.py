#!/usr/bin/env python3
"""
WP-4.2 / WP-4.5: Classical Baseline Evaluation Runner
======================================================

Runs the classical anomaly detectors from evaluation/baselines/classical_detectors.py
against the WP-4.4 synthetic evaluation dataset.  Computes precision, recall, F1-score,
and ROC-AUC for each model, together with per-model training and inference times.

Writes results to:  evaluation/results/baselines_results.json

Evaluation protocol — one-class anomaly detection
--------------------------------------------------
1. Load datasets/synthetic_eval_dataset.json.gz (6 500 records, 26 classes).
2. Extract 4 numeric features per record as specified:
       duration, memory_spike_kb, cpu_utilization, network_io_bytes
3. Build binary labels:  anomaly_type == 'benign'  →  0,  else  →  1
4. Training set  : benign-only records, first TRAIN_FRAC fraction
   (one-class learning: detectors see only normal data during training).
5. Test set      : remaining benign records  +  ALL anomaly records.
6. Evaluate each detector on the test set; report precision, recall, F1, ROC-AUC.

Usage
-----
    cd project/scafad-r-core
    python evaluation/run_baselines.py           # writes results JSON
    python evaluation/run_baselines.py --dry-run  # prints feature shapes, exits
"""

import argparse
import gzip
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Path setup — must happen before importing project modules
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # .../evaluation/
REPO_ROOT = SCRIPT_DIR.parent                         # .../scafad-r-core/

# Add repo root so that the `scafad` package is importable as `scafad.*`.
# WP-4.2: canonical detector module lives at evaluation/baselines/; add it
# to sys.path so the bare `from classical_detectors import ...` works.
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPT_DIR / "baselines"))

from sklearn.metrics import (                          # noqa: E402
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from classical_detectors import (                      # noqa: E402
    DBSCANAnomalyDetector,
    EllipticEnvelopeDetector,
    IsolationForestDetector,
    KMeansDetector,
    LocalOutlierFactorDetector,
    MovingAverageDetector,
    OneClassSVMDetector,
    StatisticalIQRDetector,
    StatisticalZScoreDetector,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATASET_PATH = REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
OUTPUT_PATH = REPO_ROOT / "evaluation" / "results" / "baselines_results.json"

FEATURE_NAMES: List[str] = [
    "duration",
    "memory_spike_kb",
    "cpu_utilization",
    "network_io_bytes",
]

# Fraction of benign records used for training; rest go to the test set.
TRAIN_FRAC = 0.8

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data loading and feature extraction
# ---------------------------------------------------------------------------

def load_dataset(path: Path) -> List[Dict[str, Any]]:
    """Decompress and parse the gzip-compressed JSON dataset.

    Parameters
    ----------
    path:
        Filesystem path to the ``.json.gz`` dataset file.

    Returns
    -------
    list of record dicts
    """
    logger.info("Loading dataset: %s", path)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        records: List[Dict[str, Any]] = json.load(fh)
    logger.info("Loaded %d records.", len(records))
    return records


def extract_features_labels(
    records: List[Dict[str, Any]],
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract the 4 core numeric features and binary labels from raw dicts.

    Features (in order): duration, memory_spike_kb, cpu_utilization, network_io_bytes
    Label encoding: benign → 0, any anomaly type → 1

    Parameters
    ----------
    records:
        List of record dicts as loaded from the dataset file.

    Returns
    -------
    X : ndarray, shape (n_records, 4)
    y : ndarray, shape (n_records,), dtype int
    """
    X_rows: List[List[float]] = []
    y_rows: List[int] = []

    for rec in records:
        X_rows.append([
            float(rec["duration"]),
            float(rec["memory_spike_kb"]),
            float(rec["cpu_utilization"]),
            float(rec["network_io_bytes"]),
        ])
        y_rows.append(0 if rec["anomaly_type"] == "benign" else 1)

    return np.array(X_rows, dtype=float), np.array(y_rows, dtype=int)


# ---------------------------------------------------------------------------
# Train / test split (one-class protocol)
# ---------------------------------------------------------------------------

def build_train_test_split(
    records: List[Dict[str, Any]],
    train_frac: float = TRAIN_FRAC,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split the dataset following the one-class anomaly detection protocol.

    * Training set  : benign records only (first ``train_frac`` fraction).
    * Test set      : remaining benign records + ALL anomaly records.

    This mimics production: models are trained on known-good traces and then
    evaluated against a mix of benign and anomalous samples.

    Parameters
    ----------
    records:
        Full list of record dicts.
    train_frac:
        Fraction of benign records reserved for training.
    seed:
        NumPy random seed for the benign shuffle (does not affect dataset
        generation reproducibility — only the train/test index cut here).

    Returns
    -------
    X_train, X_test, y_train, y_test : ndarrays
    """
    rng = np.random.default_rng(seed)

    benign = [r for r in records if r["anomaly_type"] == "benign"]
    anomalous = [r for r in records if r["anomaly_type"] != "benign"]

    # Shuffle the benign subset with the seeded RNG for reproducibility.
    benign_idx = rng.permutation(len(benign))
    n_train = int(len(benign) * train_frac)
    train_benign = [benign[i] for i in benign_idx[:n_train]]
    test_benign = [benign[i] for i in benign_idx[n_train:]]

    train_records = train_benign
    test_records = test_benign + anomalous

    X_train, y_train = extract_features_labels(train_records)
    X_test, y_test = extract_features_labels(test_records)

    logger.info(
        "Train: %d benign records (labels all 0). "
        "Test: %d benign + %d anomaly = %d total (anomaly rate %.1f%%).",
        len(train_benign),
        len(test_benign),
        len(anomalous),
        len(test_records),
        100.0 * np.mean(y_test),
    )
    return X_train, X_test, y_train, y_test


# ---------------------------------------------------------------------------
# Per-model evaluation
# ---------------------------------------------------------------------------

def _safe_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Return ROC-AUC or 0.0 if the metric cannot be computed."""
    try:
        return float(roc_auc_score(y_true, y_score))
    except ValueError:
        return 0.0


def evaluate_one(
    name: str,
    detector: Any,
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> Dict[str, Any]:
    """Fit ``detector`` on ``X_train``, predict on ``X_test``, compute metrics.

    Parameters
    ----------
    name:
        Human-readable model name that appears in the results JSON.
    detector:
        Any ``BaseAnomalyDetector`` subclass instance.
    X_train:
        Benign-only feature matrix used for training.
    X_test:
        Full test feature matrix (benign + anomalies).
    y_test:
        Binary ground-truth labels for ``X_test``.

    Returns
    -------
    Dict with keys: name, precision, recall, f1, roc_auc,
                    train_time_s, infer_time_s, model_parameters, error (opt.)
    """
    logger.info("  Evaluating: %s …", name)

    # --- Train ---
    t0 = time.perf_counter()
    try:
        detector.fit(X_train, feature_names=FEATURE_NAMES)
        train_time_s = time.perf_counter() - t0
    except Exception as exc:  # noqa: BLE001
        logger.warning("    TRAIN FAILED (%s): %s", name, exc)
        return {
            "name": name,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.0,
            "train_time_s": 0.0,
            "infer_time_s": 0.0,
            "error": str(exc),
        }

    # --- Infer ---
    t1 = time.perf_counter()
    try:
        result = detector.predict(X_test)
        infer_time_s = time.perf_counter() - t1
    except Exception as exc:  # noqa: BLE001
        logger.warning("    INFER FAILED (%s): %s", name, exc)
        return {
            "name": name,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.0,
            "train_time_s": round(train_time_s, 6),
            "infer_time_s": 0.0,
            "error": str(exc),
        }

    y_pred = result.anomaly_predictions
    y_score = result.anomaly_scores

    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))
    roc_auc = _safe_roc_auc(y_test, y_score)

    logger.info(
        "    → precision=%.4f  recall=%.4f  F1=%.4f  ROC-AUC=%.4f"
        "  train=%.2fs  infer=%.2fs",
        precision,
        recall,
        f1,
        roc_auc,
        train_time_s,
        infer_time_s,
    )

    return {
        "name": name,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "roc_auc": round(roc_auc, 6),
        "train_time_s": round(train_time_s, 6),
        "infer_time_s": round(infer_time_s, 6),
        "model_parameters": result.model_parameters,
    }


# ---------------------------------------------------------------------------
# Detector suite
# ---------------------------------------------------------------------------

def build_detector_suite() -> List[Tuple[str, Any]]:
    """Return the list of (name, detector) pairs to evaluate.

    Includes at minimum: IsolationForest, OneClassSVM, LocalOutlierFactor,
    ZScore — plus IQR, MovingAverage, and DBSCAN for completeness.

    Returns
    -------
    list of (name_str, detector_instance) tuples
    """
    return [
        # ── Statistical baselines ──────────────────────────────────────────
        (
            "ZScore (threshold=3.0)",
            StatisticalZScoreDetector(threshold=3.0),
        ),
        (
            "ZScore (threshold=2.5)",
            StatisticalZScoreDetector(threshold=2.5),
        ),
        (
            "IQR (multiplier=1.5)",
            StatisticalIQRDetector(iqr_multiplier=1.5),
        ),
        (
            "IQR (multiplier=2.0)",
            StatisticalIQRDetector(iqr_multiplier=2.0),
        ),
        (
            "MovingAverage (w=10)",
            MovingAverageDetector(window_size=10, std_multiplier=2.0),
        ),
        # ── Classical ML baselines ─────────────────────────────────────────
        (
            "IsolationForest (n=100, cont=0.10)",
            IsolationForestDetector(contamination=0.10, n_estimators=100, random_state=42),
        ),
        (
            "IsolationForest (n=200, cont=0.05)",
            IsolationForestDetector(contamination=0.05, n_estimators=200, random_state=42),
        ),
        (
            "OneClassSVM (nu=0.10)",
            OneClassSVMDetector(gamma="scale", nu=0.10),
        ),
        (
            "OneClassSVM (nu=0.05)",
            OneClassSVMDetector(gamma="auto", nu=0.05),
        ),
        (
            "LocalOutlierFactor (k=20, cont=0.10)",
            LocalOutlierFactorDetector(n_neighbors=20, contamination=0.10),
        ),
        (
            "LocalOutlierFactor (k=10, cont=0.05)",
            LocalOutlierFactorDetector(n_neighbors=10, contamination=0.05),
        ),
        (
            "DBSCAN (eps=0.5, min_samples=5)",
            DBSCANAnomalyDetector(eps=0.5, min_samples=5),
        ),
        # ── Additional classical ML baselines (WP-4.2) ────────────────────
        (
            "EllipticEnvelope (cont=0.10)",
            EllipticEnvelopeDetector(contamination=0.10),
        ),
        (
            "KMeans (k=5)",
            KMeansDetector(n_clusters=5, threshold_std_multiplier=2.0),
        ),
    ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_evaluation(dry_run: bool = False) -> Dict[str, Any]:
    """Execute the full baseline evaluation pipeline.

    Parameters
    ----------
    dry_run:
        If *True*, print shapes and exit without running the detectors.

    Returns
    -------
    Results dict matching the ``baselines_results.json`` schema.
    """
    records = load_dataset(DATASET_PATH)
    X_train, X_test, y_train, y_test = build_train_test_split(records)

    logger.info(
        "Feature matrix shapes — train: %s, test: %s",
        X_train.shape,
        X_test.shape,
    )

    if dry_run:
        logger.info("Dry-run requested — skipping detector evaluation.")
        return {}

    detector_suite = build_detector_suite()
    logger.info(
        "Running %d detector configurations …", len(detector_suite)
    )

    model_results: List[Dict[str, Any]] = []
    wall_start = time.perf_counter()

    for name, detector in detector_suite:
        model_entry = evaluate_one(name, detector, X_train, X_test, y_test)
        model_results.append(model_entry)

    wall_elapsed = time.perf_counter() - wall_start
    logger.info(
        "Evaluation complete in %.1f s. %d models evaluated.",
        wall_elapsed,
        len(model_results),
    )

    # ── Build results document ─────────────────────────────────────────────
    results: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "datasets/synthetic_eval_dataset.json.gz",
        "evaluation_protocol": "one-class: trained on benign-only records",
        "train_records": int(X_train.shape[0]),
        "test_records": int(X_test.shape[0]),
        "test_anomaly_rate": round(float(np.mean(y_test)), 6),
        "features": FEATURE_NAMES,
        "total_evaluation_time_s": round(wall_elapsed, 3),
        "models": model_results,
    }

    return results


def main() -> None:
    """Parse CLI arguments, run evaluation, write JSON output."""
    parser = argparse.ArgumentParser(
        description="WP-4.5 classical baseline evaluator",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print feature shapes then exit without running detectors.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help=f"Path for the JSON results file (default: {OUTPUT_PATH})",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = run_evaluation(dry_run=args.dry_run)

    if args.dry_run:
        logger.info("Dry-run complete — no file written.")
        return

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    logger.info("Results written to: %s", output_path)

    # ── Human-readable summary ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"{'Model':<45} {'Prec':>6} {'Rec':>6} {'F1':>6} {'AUC':>6}")
    print("-" * 70)
    for m in results["models"]:
        err = m.get("error", "")
        if err:
            print(f"  {m['name']:<43}  ERROR: {err[:25]}")
        else:
            print(
                f"  {m['name']:<43}"
                f"  {m['precision']:>6.4f}"
                f"  {m['recall']:>6.4f}"
                f"  {m['f1']:>6.4f}"
                f"  {m['roc_auc']:>6.4f}"
            )
    print("=" * 70)


if __name__ == "__main__":
    main()
