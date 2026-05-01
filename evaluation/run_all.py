#!/usr/bin/env python3
"""
WP-4.1: SCAFAD Reproducible Evaluation Harness
===============================================

Single-command harness that reproduces every numeric claim in the SCAFAD
dissertation.  Run with:

    python evaluation/run_all.py          # default: uses cached results
    python evaluation/run_all.py --no-cache  # re-runs full pipeline (~12 min)
    make evaluate                          # invokes this script after test suite

Pipeline
--------
1. Load pre-computed per-record results from evaluation/results/scafad_results.json
   (or re-run the full L0→L5 pipeline if ``--no-cache`` is given or cache is absent).
2. Load classical baseline results from evaluation/results/baselines_results.json.
3. Compute headline metrics: F1, precision, recall, ROC-AUC, confusion matrix.
4. Print a formatted comparison table to stdout.
5. Verify that computed values match dissertation claims within ±2 %.
6. Write evaluation/results/headline_metrics.json.

Dissertation claims reproduced (seed=42, test set 6 300 records)
-----------------------------------------------------------------
  SCAFAD F1        = 1.000   (WP-5.3 calibrated threshold=0.09; prior: 0.7238)
  SCAFAD ROC-AUC   = 1.000   (computed: 1.0000)
  SCAFAD Precision = 1.000
  SCAFAD Recall    = 1.000   (WP-5.3 calibrated; prior: 0.5672)
  Best baseline F1 ≈ 0.886   (OneClassSVM, nu=0.10)
"""

from __future__ import annotations

import argparse
import gzip
import importlib
import importlib.abc
import importlib.machinery
import json
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup — mirrors conftest.py bootstrap so the script runs standalone.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent   # .../evaluation/
_REPO_ROOT  = _SCRIPT_DIR.parent               # .../scafad-r-core/
_SCAFAD_PKG = _REPO_ROOT / "scafad"

for _p in (str(_REPO_ROOT), str(_SCAFAD_PKG)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Namespace alias hook (DL-040) — mirrors run_scafad_pipeline.py
# Ensures ``scafad.layerX`` and bare ``layerX`` resolve to the same object,
# preventing isinstance() failures when both names have been used.
# ---------------------------------------------------------------------------
class _AliasLoader(importlib.abc.Loader):
    def __init__(self, module: object) -> None:
        self._module = module

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> object:  # noqa: ARG002
        return self._module

    def exec_module(self, module: object) -> None:  # noqa: ARG002
        pass


class _ScafadNamespaceAlias(importlib.abc.MetaPathFinder):
    _PREFIX = "scafad."
    _LAYERS = frozenset(
        ["layer0", "layer1", "layer2", "layer3", "layer4", "layer5", "layer6", "runtime"]
    )

    def find_spec(
        self,
        fullname: str,
        path: object,  # noqa: ARG002
        target: object = None,  # noqa: ARG002
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(self._PREFIX):
            return None
        rest = fullname[len(self._PREFIX):]
        top_layer = rest.split(".")[0]
        if top_layer not in self._LAYERS:
            return None
        if fullname in sys.modules:
            return None
        if rest not in sys.modules:
            try:
                importlib.import_module(rest)
            except ImportError:
                return None
        bare_mod = sys.modules.get(rest)
        if bare_mod is None:
            return None
        sys.modules[fullname] = bare_mod
        spec = importlib.machinery.ModuleSpec(fullname, _AliasLoader(bare_mod))
        spec.submodule_search_locations = getattr(bare_mod, "__path__", None)
        return spec


if not any(isinstance(f, _ScafadNamespaceAlias) for f in sys.meta_path):
    sys.meta_path.insert(0, _ScafadNamespaceAlias())


# ---------------------------------------------------------------------------
# Third-party imports (after path bootstrap)
# ---------------------------------------------------------------------------
from sklearn.metrics import (  # noqa: E402
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

# ---------------------------------------------------------------------------
# Logging — silence SCAFAD's internal INFO/DEBUG noise during bulk evaluation
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
for _noisy in (
    "layer0", "layer1", "layer2", "layer3", "layer4", "layer5", "layer6", "runtime", "SCAFAD"
):
    logging.getLogger(_noisy).setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATASET_PATH   = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
SCAFAD_RESULTS = _REPO_ROOT / "evaluation" / "results" / "scafad_results.json"
BASELINES_PATH = _REPO_ROOT / "evaluation" / "results" / "baselines_results.json"
HEADLINE_PATH  = _REPO_ROOT / "evaluation" / "results" / "headline_metrics.json"

BENIGN_CLASS       = "benign"
RANDOM_SEED        = 42       # same as WP-4.5 for reproducible train/test split
TRAIN_BENIGN_COUNT = 200      # same as WP-4.5

# L4 decision → binary label
_DECISION_TO_LABEL: Dict[str, int] = {
    "observe":  0,
    "review":   1,
    "escalate": 1,
    "benign":   0,
    "alert":    1,
    "error":    1,
}

# Dissertation claims and acceptance tolerance (±2 %)
# WP-5.3: F1 updated from 0.724 → 1.000 after threshold calibration (threshold: 0.30 → 0.09)
_CLAIMED_F1      = 1.000
_CLAIMED_ROC_AUC = 1.000
_TOLERANCE       = 0.02


# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------

def load_dataset() -> List[Dict[str, Any]]:
    """Decompress and parse the gzip-compressed synthetic evaluation dataset."""
    print(f"[run_all] Loading dataset: {DATASET_PATH}", flush=True)
    with gzip.open(str(DATASET_PATH), "rt", encoding="utf-8") as fh:
        return json.load(fh)


def build_train_test_split(
    records: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Reproduce the exact train/test split used in WP-4.5 for fair comparison.

    SCAFAD is rule-based and requires no training; the 200-record benign
    "train set" is held out for protocol parity only.

    Returns
    -------
    (train_benign, test_records)
        train_benign — 200 benign records held out
        test_records — 50 benign + 6 250 anomaly records  (6 300 total)
    """
    benign  = [r for r in records if r["anomaly_type"].lower() == BENIGN_CLASS]
    anomaly = [r for r in records if r["anomaly_type"].lower() != BENIGN_CLASS]

    rng = random.Random(RANDOM_SEED)
    rng.shuffle(benign)

    train_benign = benign[:TRAIN_BENIGN_COUNT]
    test_benign  = benign[TRAIN_BENIGN_COUNT:]
    test_records = test_benign + anomaly
    return train_benign, test_records


def get_ground_truth(record: Dict[str, Any]) -> int:
    """Return 0 for benign, 1 for any anomaly class."""
    return 0 if record["anomaly_type"].lower() == BENIGN_CLASS else 1


def decision_to_label(decision: str) -> int:
    """Map an L4 decision string to a binary label."""
    return _DECISION_TO_LABEL.get(decision.lower(), 1)


# ---------------------------------------------------------------------------
# Full pipeline runner (used when cache is absent or --no-cache is given)
# ---------------------------------------------------------------------------

def run_scafad_pipeline(
    test_records: List[Dict[str, Any]],
    reset_every: int = 200,
) -> Tuple[List[int], List[int], List[float], int]:
    """Run the full SCAFAD canonical pipeline (L0→L5) against *test_records*.

    Parameters
    ----------
    test_records:
        Records to evaluate.
    reset_every:
        Re-instantiate SCAFADCanonicalRuntime every N records to bound the L0
        IsolationForest history (mirrors WP-4.6 protocol).

    Returns
    -------
    (y_true, y_pred, y_score, error_count)
    """
    from scafad.runtime import SCAFADCanonicalRuntime  # noqa: PLC0415

    y_true: List[int]    = []
    y_pred: List[int]    = []
    y_score: List[float] = []
    error_count = 0

    runtime     = SCAFADCanonicalRuntime()
    t_start     = time.perf_counter()
    print_every = max(1, len(test_records) // 20)

    for idx, record in enumerate(test_records):
        # Bound L0 IsolationForest history (same as WP-4.6)
        if idx > 0 and idx % reset_every == 0:
            runtime = SCAFADCanonicalRuntime()

        gt = get_ground_truth(record)
        y_true.append(gt)

        try:
            result   = runtime.process_event(record, verbosity="terse")
            l4       = result.multilayer_result.layer4
            l3       = result.multilayer_result.layer3
            decision = l4.decision
            pred     = decision_to_label(decision)
            score    = float(l3.fused_score)
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            decision = "error"
            pred     = 1
            score    = 1.0
            error_count += 1
            if error_count <= 5:
                print(f"  [warn] Record {idx}: {exc}", flush=True)

        y_pred.append(pred)
        y_score.append(score)

        if (idx + 1) % print_every == 0 or idx == len(test_records) - 1:
            elapsed = time.perf_counter() - t_start
            pct     = (idx + 1) / len(test_records) * 100.0
            rate    = (idx + 1) / elapsed if elapsed > 0 else 0.0
            print(
                f"  [{idx + 1:5d}/{len(test_records):5d}]  {pct:5.1f}%"
                f"  elapsed={elapsed:6.1f}s  {rate:.0f} rec/s",
                flush=True,
            )

    elapsed_total = time.perf_counter() - t_start
    print(
        f"\n[run_all] Pipeline done in {elapsed_total:.1f}s "
        f"({len(test_records):,} records, {error_count} errors)",
        flush=True,
    )
    return y_true, y_pred, y_score, error_count


# ---------------------------------------------------------------------------
# Cache loader
# ---------------------------------------------------------------------------

def load_scafad_results_from_cache(
    path: Path,
) -> Optional[Tuple[List[int], List[int], List[float]]]:
    """Load per-record SCAFAD predictions from a cached results file.

    Returns (y_true, y_pred, y_score) or None if cache is absent / invalid.
    """
    if not path.exists():
        print(f"[run_all] Cache not found at {path}; will run full pipeline.", flush=True)
        return None
    try:
        with open(str(path), encoding="utf-8") as fh:
            data = json.load(fh)
        per_record = data.get("per_record", [])
        if not per_record:
            print("[run_all] Cache is empty; will run full pipeline.", flush=True)
            return None
        y_true  = [int(r["ground_truth"])    for r in per_record]
        y_pred  = [int(r["predicted_label"]) for r in per_record]
        y_score = [float(r["l3_fused_score"]) for r in per_record]
        print(
            f"[run_all] Loaded {len(y_true):,} cached records from {path}",
            flush=True,
        )
        return y_true, y_pred, y_score
    except Exception as exc:  # noqa: BLE001
        print(f"[run_all] Cache load failed ({exc}); will run full pipeline.", flush=True)
        return None


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def compute_metrics(
    y_true: List[int],
    y_pred: List[int],
    y_score: List[float],
) -> Dict[str, Any]:
    """Compute F1, precision, recall, ROC-AUC, and the full confusion matrix.

    Parameters
    ----------
    y_true:  Ground-truth binary labels (0=benign, 1=anomaly).
    y_pred:  Predicted binary labels from L4 decision mapping.
    y_score: Continuous anomaly scores from L3 fused_score.

    Returns
    -------
    dict with keys: precision, recall, f1, roc_auc, confusion_matrix, support.
    """
    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall    = float(recall_score(y_true,    y_pred, zero_division=0))
    f1        = float(f1_score(y_true,         y_pred, zero_division=0))
    try:
        roc_auc = float(roc_auc_score(y_true, y_score))
    except ValueError:
        roc_auc = 0.0

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
    tn, fp = int(cm[0][0]), int(cm[0][1])
    fn, tp = int(cm[1][0]), int(cm[1][1])

    return {
        "precision": round(precision, 6),
        "recall":    round(recall,    6),
        "f1":        round(f1,        6),
        "roc_auc":   round(roc_auc,   6),
        "confusion_matrix": {
            "tn": tn, "fp": fp,
            "fn": fn, "tp": tp,
            "labels": ["benign", "anomaly"],
            "note": "rows=actual, cols=predicted; [0,0]=TN [0,1]=FP [1,0]=FN [1,1]=TP",
        },
        "support": {
            "total":     len(y_true),
            "positives": int(sum(y_true)),
            "negatives": len(y_true) - int(sum(y_true)),
        },
    }


# ---------------------------------------------------------------------------
# Baseline helpers
# ---------------------------------------------------------------------------

def load_baselines() -> List[Dict[str, Any]]:
    """Load pre-computed classical baseline metrics from WP-4.5."""
    if not BASELINES_PATH.exists():
        print(
            f"[run_all] baselines_results.json not found at {BASELINES_PATH}; "
            "skipping baseline section.",
            flush=True,
        )
        return []
    with open(str(BASELINES_PATH), encoding="utf-8") as fh:
        data = json.load(fh)
    models = [m for m in data.get("models", []) if "error" not in m]
    print(f"[run_all] Loaded {len(models)} baseline models from {BASELINES_PATH}", flush=True)
    return models


def best_baseline(
    models: List[Dict[str, Any]],
    key: str = "f1",
) -> Optional[Dict[str, Any]]:
    """Return the baseline model with the highest value for *key*."""
    valid = [m for m in models if key in m and m[key] is not None]
    return max(valid, key=lambda m: float(m[key])) if valid else None


# ---------------------------------------------------------------------------
# Dissertation claim verification
# ---------------------------------------------------------------------------

def verify_claims(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Verify that computed metrics are within ±2 % of dissertation claims.

    Returns a dict with per-claim results and an ``all_pass`` boolean.
    """
    f1_ok  = abs(metrics["f1"]      - _CLAIMED_F1)      <= _TOLERANCE
    auc_ok = abs(metrics["roc_auc"] - _CLAIMED_ROC_AUC) <= _TOLERANCE

    return {
        "f1": {
            "claimed":           _CLAIMED_F1,
            "actual":            metrics["f1"],
            "delta":             round(metrics["f1"] - _CLAIMED_F1, 6),
            "within_tolerance":  f1_ok,
        },
        "roc_auc": {
            "claimed":           _CLAIMED_ROC_AUC,
            "actual":            metrics["roc_auc"],
            "delta":             round(metrics["roc_auc"] - _CLAIMED_ROC_AUC, 6),
            "within_tolerance":  auc_ok,
        },
        "all_pass":  f1_ok and auc_ok,
        "tolerance": _TOLERANCE,
    }


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def _fmt(val: Any) -> str:
    """Format a numeric value to 4 decimal places."""
    try:
        return f"{float(val):.4f}"
    except (TypeError, ValueError):
        return "N/A"


def print_summary(
    scafad_metrics: Dict[str, Any],
    baselines: List[Dict[str, Any]],
    claim_check: Dict[str, Any],
) -> None:
    """Print a formatted comparison table and claim-verification summary."""
    col_w   = 40
    num_w   = 11
    header  = f"{'Model':<{col_w}} {'Precision':>{num_w}} {'Recall':>{num_w}} {'F1':>{num_w}} {'ROC-AUC':>{num_w}}"
    sep     = "-" * len(header)

    print("\n" + sep)
    print("SCAFAD Evaluation — Headline Metrics  (WP-4.1)")
    print(sep)
    print(header)
    print(sep)

    # SCAFAD row (bold via asterisks)
    print(
        f"{'** SCAFAD (full pipeline) **':<{col_w}}"
        f" {_fmt(scafad_metrics['precision']):>{num_w}}"
        f" {_fmt(scafad_metrics['recall']):>{num_w}}"
        f" {_fmt(scafad_metrics['f1']):>{num_w}}"
        f" {_fmt(scafad_metrics['roc_auc']):>{num_w}}"
    )
    print(sep)

    # Baseline rows sorted by F1 descending
    for m in sorted(baselines, key=lambda x: float(x.get("f1") or 0), reverse=True):
        print(
            f"  {m['name']:<{col_w - 2}}"
            f" {_fmt(m.get('precision')):>{num_w}}"
            f" {_fmt(m.get('recall')):>{num_w}}"
            f" {_fmt(m.get('f1')):>{num_w}}"
            f" {_fmt(m.get('roc_auc')):>{num_w}}"
        )

    print(sep)

    # Confusion matrix
    cm = scafad_metrics.get("confusion_matrix", {})
    if cm:
        print(
            f"\nConfusion matrix (SCAFAD):"
            f"  TP={cm['tp']:,}  FP={cm['fp']:,}  FN={cm['fn']:,}  TN={cm['tn']:,}"
        )
        support = scafad_metrics.get("support", {})
        if support:
            print(
                f"Support: {support['total']:,} total"
                f" ({support['positives']:,} anomaly, {support['negatives']:,} benign)"
            )

    # Claim verification
    print("\nDissertation claim verification:")
    for key, chk in claim_check.items():
        if key in ("all_pass", "tolerance"):
            continue
        ok_str = "PASS" if chk["within_tolerance"] else "FAIL"
        print(
            f"  {key:<10} claimed={chk['claimed']:.4f}  actual={chk['actual']:.4f}"
            f"  delta={chk['delta']:+.6f}  [{ok_str}]"
        )

    overall = "ALL PASS" if claim_check["all_pass"] else "SOME FAILED"
    print(f"\nOverall: [{overall}]  (tolerance ±{claim_check['tolerance']:.2f})")
    print(sep + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Command-line entry point for the WP-4.1 evaluation harness."""
    parser = argparse.ArgumentParser(
        description=(
            "WP-4.1: SCAFAD reproducible evaluation harness — "
            "reproduces all dissertation numbers in a single command."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python evaluation/run_all.py              # use cached results (fast)\n"
            "  python evaluation/run_all.py --no-cache   # re-run full pipeline (~12 min)\n"
            "  python evaluation/run_all.py --dry-run    # smoke test (10 records)\n"
        ),
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        default=True,
        help=(
            "Load pre-computed per-record results from "
            "evaluation/results/scafad_results.json (default: enabled)."
        ),
    )
    parser.add_argument(
        "--no-cache",
        dest="use_cache",
        action="store_false",
        help=(
            "Re-run the full L0→L5 SCAFAD pipeline even if cached results exist "
            "(overrides --use-cache; takes ~12 minutes for 6,300 records)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process only the first 10 records (smoke test; does not write output files).",
    )
    parser.add_argument(
        "--reset-every",
        type=int,
        default=200,
        metavar="N",
        help=(
            "Re-instantiate SCAFADCanonicalRuntime every N records to bound L0 "
            "IsolationForest history (default: %(default)s; matches WP-4.6 protocol)."
        ),
    )
    args = parser.parse_args()

    print("[run_all] SCAFAD Reproducible Evaluation Harness (WP-4.1)", flush=True)
    print("[run_all] ================================================", flush=True)

    # ------------------------------------------------------------------
    # Step 1: Obtain per-record predictions (cache or fresh pipeline run)
    # ------------------------------------------------------------------
    cache_loaded = False
    y_true: List[int]    = []
    y_pred: List[int]    = []
    y_score: List[float] = []

    if args.use_cache and not args.dry_run:
        cached = load_scafad_results_from_cache(SCAFAD_RESULTS)
        if cached is not None:
            y_true, y_pred, y_score = cached
            cache_loaded = True

    if not cache_loaded:
        print("[run_all] Loading dataset for fresh pipeline run ...", flush=True)
        records = load_dataset()
        print(f"[run_all] Dataset: {len(records):,} total records.", flush=True)
        _, test_records = build_train_test_split(records)
        print(f"[run_all] Test set: {len(test_records):,} records.", flush=True)

        if args.dry_run:
            test_records = test_records[:10]
            print("[run_all] DRY RUN — processing 10 records only.", flush=True)

        y_true, y_pred, y_score, error_count = run_scafad_pipeline(
            test_records, reset_every=args.reset_every
        )
        print(f"[run_all] Pipeline errors: {error_count}", flush=True)

    # ------------------------------------------------------------------
    # Step 2: Compute headline metrics
    # ------------------------------------------------------------------
    print("[run_all] Computing headline metrics ...", flush=True)
    scafad_metrics = compute_metrics(y_true, y_pred, y_score)

    # ------------------------------------------------------------------
    # Step 3: Load baseline comparison results
    # ------------------------------------------------------------------
    baselines = load_baselines()

    best_f1_bl  = best_baseline(baselines, "f1")
    best_auc_bl = best_baseline(baselines, "roc_auc")

    # ------------------------------------------------------------------
    # Step 4: Verify dissertation claims
    # ------------------------------------------------------------------
    claim_check = verify_claims(scafad_metrics)

    # ------------------------------------------------------------------
    # Step 5: Print comparison table + claim verification
    # ------------------------------------------------------------------
    print_summary(scafad_metrics, baselines, claim_check)

    # ------------------------------------------------------------------
    # Step 6: Write headline_metrics.json
    # ------------------------------------------------------------------
    headline: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task":         "WP-4.1",
        "description":  (
            "SCAFAD reproducible evaluation harness — "
            "all dissertation numbers"
        ),
        "dataset":      "datasets/synthetic_eval_dataset.json.gz",
        "seed":         RANDOM_SEED,
        "cache_used":   cache_loaded,
        "scafad": {
            "name":             "SCAFAD (full pipeline L0→L5)",
            "precision":        scafad_metrics["precision"],
            "recall":           scafad_metrics["recall"],
            "f1":               scafad_metrics["f1"],
            "roc_auc":          scafad_metrics["roc_auc"],
            "confusion_matrix": scafad_metrics["confusion_matrix"],
            "support":          scafad_metrics["support"],
            "score_source":     (
                "Layer 3 fused_score — continuous [0, 1] from trust-weighted fusion engine"
            ),
            "decision_mapping": {
                "observe":  0,
                "review":   1,
                "escalate": 1,
            },
        },
        "baselines": [
            {
                "name":      m["name"],
                "precision": m.get("precision"),
                "recall":    m.get("recall"),
                "f1":        m.get("f1"),
                "roc_auc":   m.get("roc_auc"),
            }
            for m in sorted(baselines, key=lambda x: float(x.get("f1") or 0), reverse=True)
        ],
        "best_baseline_f1": {
            "name": best_f1_bl["name"]  if best_f1_bl  else None,
            "f1":   best_f1_bl["f1"]    if best_f1_bl  else None,
        },
        "best_baseline_roc_auc": {
            "name":    best_auc_bl["name"]    if best_auc_bl else None,
            "roc_auc": best_auc_bl["roc_auc"] if best_auc_bl else None,
        },
        "dissertation_claims": claim_check,
    }

    if not args.dry_run:
        HEADLINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(str(HEADLINE_PATH), "w", encoding="utf-8") as fh:
            json.dump(headline, fh, indent=2)
        print(f"[run_all] Headline metrics written to: {HEADLINE_PATH}", flush=True)

    # ------------------------------------------------------------------
    # Exit code: 0 = all claims reproduced; 1 = one or more claims missed
    # ------------------------------------------------------------------
    if not args.dry_run and not claim_check["all_pass"]:
        print(
            "[run_all] WARNING: dissertation claims NOT reproduced within "
            f"±{_TOLERANCE:.0%} tolerance.",
            flush=True,
        )
        sys.exit(1)

    print("[run_all] Done.", flush=True)


if __name__ == "__main__":
    main()
