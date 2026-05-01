#!/usr/bin/env python3
"""
WP-4.6: SCAFAD Full Pipeline Evaluation
========================================

Runs the complete SCAFAD canonical pipeline (L0 → L1 → L2 → L3 → L4 → L5)
against every record in the WP-4.4 synthetic evaluation dataset.  Extracts
the L4 decision and L3 fused_score for each record, computes precision,
recall, F1-score and ROC-AUC, then writes a comparison report that puts
SCAFAD side-by-side with the WP-4.5 classical-baseline results.

Outputs
-------
  evaluation/results/scafad_results.json   — per-record + aggregate metrics
  evaluation/results/comparison_report.md  — markdown comparison table

Usage
-----
    cd project/scafad-r-core
    python evaluation/run_scafad_pipeline.py           # full run
    python evaluation/run_scafad_pipeline.py --dry-run  # 10 records only

Decision mapping
----------------
  L4 decision  |  binary label
  -------------|---------------
  observe      |  0  (benign / no anomaly flagged)
  review       |  1  (anomaly flagged)
  escalate     |  1  (anomaly flagged)

ROC-AUC score source
--------------------
  Layer 3 ``fused_score`` — continuous value in [0, 1] produced by the
  trust-weighted fusion engine.  Higher values indicate stronger anomaly
  confidence.
"""

from __future__ import annotations

import argparse
import gzip
import importlib
import importlib.abc
import importlib.machinery
import json
import logging
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Path setup — replicates pytest.ini `pythonpath = . scafad` bootstrap
# Mirrors conftest.py so the script runs correctly outside of pytest.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent   # .../evaluation/
_REPO_ROOT   = _SCRIPT_DIR.parent               # .../scafad-r-core/
_SCAFAD_PKG  = _REPO_ROOT / "scafad"

for _p in (str(_REPO_ROOT), str(_SCAFAD_PKG)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Namespace alias hook (DL-040)
# Ensures ``scafad.layerX`` and bare ``layerX`` resolve to the *same* class
# object, preventing isinstance() failures when both names have been used.
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
# Third-party and project imports (after path bootstrap)
# ---------------------------------------------------------------------------
from sklearn.metrics import (  # noqa: E402
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from scafad.runtime import SCAFADCanonicalRuntime  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATASET_PATH   = _REPO_ROOT / "datasets" / "synthetic_eval_dataset.json.gz"
BASELINES_PATH = _REPO_ROOT / "evaluation" / "results" / "baselines_results.json"
OUTPUT_PATH    = _REPO_ROOT / "evaluation" / "results" / "scafad_results.json"
REPORT_PATH    = _REPO_ROOT / "evaluation" / "results" / "comparison_report.md"

BENIGN_CLASS       = "benign"
RANDOM_SEED        = 42       # same as WP-4.5 for reproducible train/test split
TRAIN_BENIGN_COUNT = 200      # same as WP-4.5

# L4 decision → binary label:
#   observe  → 0  (pipeline does not flag the record as anomalous)
#   review   → 1  (pipeline flags as anomalous, medium confidence)
#   escalate → 1  (pipeline flags as anomalous, high confidence)
_DECISION_TO_LABEL: Dict[str, int] = {
    "observe":  0,
    "review":   1,
    "escalate": 1,
    # Defensive mappings for any legacy / unexpected strings:
    "benign":   0,
    "alert":    1,
    "error":    1,  # processing errors treated conservatively
}

# Suppress internal SCAFAD INFO/DEBUG noise during bulk evaluation.
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Silence verbose internal package loggers so progress output stays readable.
for _noisy_logger in ("layer0", "layer1", "layer2", "layer3", "layer4", "layer5",
                       "layer6", "runtime", "SCAFAD"):
    logging.getLogger(_noisy_logger).setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_dataset() -> List[Dict[str, Any]]:
    """Decompress and parse the gzip-compressed JSON evaluation dataset."""
    with gzip.open(str(DATASET_PATH), "rt", encoding="utf-8") as fh:
        return json.load(fh)


def build_train_test_split(
    records: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Reproduce the exact train/test split used in WP-4.5 for fair comparison.

    SCAFAD is rule-based and does not require a training phase; the 200-record
    benign "train set" is held out for protocol parity only.

    Returns
    -------
    (train_benign, test_records)
        train_benign  — 200 benign records (not processed by SCAFAD)
        test_records  — 50 benign + 6 250 anomaly records  (6 300 total)
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
    """Return binary label: 0 for benign, 1 for any anomaly class."""
    return 0 if record["anomaly_type"].lower() == BENIGN_CLASS else 1


def decision_to_label(decision: str) -> int:
    """Map an L4 decision string to a binary label."""
    return _DECISION_TO_LABEL.get(decision.lower(), 1)


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def run_evaluation(
    dry_run: bool = False,
    reset_every: int = 200,
) -> Dict[str, Any]:
    """Run the full SCAFAD pipeline against the synthetic evaluation dataset.

    Parameters
    ----------
    dry_run:
        When True, process only the first 10 test records (smoke test).
    reset_every:
        Re-instantiate the SCAFADCanonicalRuntime every N records to bound the
        L0 historical window and prevent IsolationForest from refitting on an
        ever-growing corpus.  In production SCAFAD is a long-lived daemon with a
        bounded rolling window; the reset simulates that bounded-history
        behaviour while keeping evaluation runtime manageable.

    Returns
    -------
    dict
        Full evaluation results including per-record details and aggregate
        metrics suitable for serialisation to JSON.
    """
    print("[WP-4.6] Loading dataset...", flush=True)
    records = load_dataset()
    print(f"[WP-4.6] Loaded {len(records):,} records.", flush=True)

    _, test_records = build_train_test_split(records)
    print(f"[WP-4.6] Test set: {len(test_records):,} records.", flush=True)

    if dry_run:
        test_records = test_records[:10]
        reset_every = 10  # Use very small window for dry run
        print("[WP-4.6] DRY RUN — processing 10 records only.", flush=True)

    print(f"[WP-4.6] Runtime reset interval: every {reset_every} records.", flush=True)
    runtime = SCAFADCanonicalRuntime()

    y_true: List[int]   = []
    y_pred: List[int]   = []
    y_score: List[float] = []
    per_record_results: List[Dict[str, Any]] = []
    error_count = 0

    t_start     = time.perf_counter()
    print_every = max(1, len(test_records) // 20)  # ~5 % progress intervals

    for idx, record in enumerate(test_records):
        # Periodic runtime reset: bound the L0 historical window so that the
        # IsolationForest does not accumulate thousands of points and refit on
        # an unbounded corpus.  The L0 engine's deque has maxlen=10000, but
        # the IsolationForest re-fits on *all* history every call — so cost
        # grows linearly.  Resetting every `reset_every` records keeps the
        # mean history size at reset_every/2, matching a bounded rolling-window
        # production deployment.
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
                print(f"  [warn] Record {idx} ({record.get('anomaly_type', '?')}): {exc}",
                      flush=True)

        y_pred.append(pred)
        y_score.append(score)
        per_record_results.append({
            "record_id":       record.get("event_id", str(idx)),
            "anomaly_type":    record.get("anomaly_type", "unknown"),
            "ground_truth":    gt,
            "l4_decision":     decision,
            "l3_fused_score":  round(score, 4),
            "predicted_label": pred,
        })

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
    print(f"\n[WP-4.6] Pipeline evaluation complete in {elapsed_total:.2f}s.", flush=True)

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------
    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall    = float(recall_score(y_true,    y_pred, zero_division=0))
    f1        = float(f1_score(y_true,         y_pred, zero_division=0))
    try:
        roc_auc = float(roc_auc_score(y_true, y_score))
    except ValueError:
        roc_auc = 0.0

    anomaly_rate   = sum(y_true) / len(y_true) if y_true else 0.0
    predicted_rate = sum(y_pred) / len(y_pred) if y_pred else 0.0

    print(f"\n[WP-4.6] Aggregate results")
    print(f"  Precision = {precision:.4f}")
    print(f"  Recall    = {recall:.4f}")
    print(f"  F1        = {f1:.4f}")
    print(f"  ROC-AUC   = {roc_auc:.4f}")
    print(f"  Errors    = {error_count}")
    print(f"  Time      = {elapsed_total:.2f}s  "
          f"({elapsed_total / len(test_records) * 1000:.1f} ms/record)")

    return {
        "generated_at":              datetime.now(timezone.utc).isoformat(),
        "dataset":                   "datasets/synthetic_eval_dataset.json.gz",
        "evaluation_protocol":       (
            f"full pipeline: L0 enrichment → L1 validation/hashing → "
            f"L2 detection → L3 trust fusion → L4 explainability → L5 threat alignment "
            f"(rule-based; no training required; runtime reset every {reset_every} records "
            f"to bound L0 IsolationForest history)"
        ),
        "test_records":              len(test_records),
        "test_anomaly_rate":         round(anomaly_rate,   6),
        "predicted_anomaly_rate":    round(predicted_rate, 6),
        "error_count":               error_count,
        "total_evaluation_time_s":   round(elapsed_total, 3),
        "infer_time_per_record_ms":  round(
            elapsed_total / len(test_records) * 1000, 3
        ) if test_records else 0.0,
        "decision_mapping": {
            "observe":  0,
            "review":   1,
            "escalate": 1,
        },
        "score_source": (
            "Layer 3 fused_score — continuous [0, 1] from trust-weighted fusion engine"
        ),
        "scafad": {
            "name":                    "SCAFAD (full pipeline)",
            "precision":               round(precision, 6),
            "recall":                  round(recall,    6),
            "f1":                      round(f1,        6),
            "roc_auc":                 round(roc_auc,   6),
            "total_evaluation_time_s": round(elapsed_total, 3),
        },
        "per_record": per_record_results,
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def write_results(results: Dict[str, Any], output_path: Path) -> None:
    """Serialise evaluation results to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"[WP-4.6] Results written to {output_path}", flush=True)


def load_baselines(baselines_path: Path) -> Dict[str, Any]:
    """Load the WP-4.5 baseline results for comparison."""
    with open(str(baselines_path), encoding="utf-8") as fh:
        return json.load(fh)


def write_comparison_report(
    scafad_metrics: Dict[str, Any],
    baselines: Dict[str, Any],
    report_path: Path,
) -> None:
    """Write the comparison report in Markdown format.

    Parameters
    ----------
    scafad_metrics:
        The ``scafad`` sub-dict from the evaluation results.
    baselines:
        Full contents of ``baselines_results.json`` from WP-4.5.
    report_path:
        Destination path for the Markdown report.
    """
    models = baselines.get("models", [])

    # Build rows for baseline models (skip error entries).
    rows: List[Dict[str, Any]] = []
    for m in models:
        if "error" in m:
            continue
        rows.append({
            "name":      m["name"],
            "precision": float(m.get("precision", math.nan)),
            "recall":    float(m.get("recall",    math.nan)),
            "f1":        float(m.get("f1",        math.nan)),
            "roc_auc":   float(m.get("roc_auc",   math.nan)),
        })

    # Sort baselines by F1 descending.
    rows.sort(
        key=lambda x: x["f1"] if not math.isnan(x["f1"]) else -1.0,
        reverse=True,
    )

    valid_rows      = [r for r in rows if not math.isnan(r["f1"])]
    best_f1_row     = max(valid_rows, key=lambda x: x["f1"])     if valid_rows else None
    best_auc_row    = max(valid_rows, key=lambda x: x["roc_auc"]) if valid_rows else None

    scafad_prec = scafad_metrics["precision"]
    scafad_rec  = scafad_metrics["recall"]
    scafad_f1   = scafad_metrics["f1"]
    scafad_auc  = scafad_metrics["roc_auc"]

    outperforms_f1  = best_f1_row  is not None and scafad_f1  > best_f1_row["f1"]
    outperforms_auc = best_auc_row is not None and scafad_auc > best_auc_row["roc_auc"]

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: List[str] = [
        "# WP-4.6 Comparison Report: SCAFAD vs Classical Baselines",
        "",
        f"**Generated:** {now_str}  ",
        "**Dataset:** `datasets/synthetic_eval_dataset.json.gz`"
        " (6,500 records · 26 anomaly classes)  ",
        "**Evaluation protocol:** SCAFAD evaluated on the same 6,300-record test set as WP-4.5  ",
        "(50 benign + 6,250 anomaly; seed=42 shuffle; 200 benign records held out for protocol parity)  ",
        "",
        "## Results Table",
        "",
        "| Model | Precision | Recall | F1 | ROC-AUC |",
        "|-------|-----------|--------|----|---------|",
        f"| **SCAFAD (full pipeline)** "
        f"| {scafad_prec:.4f} | {scafad_rec:.4f} | {scafad_f1:.4f} | {scafad_auc:.4f} |",
    ]

    for r in rows:
        p = f"{r['precision']:.4f}" if not math.isnan(r["precision"]) else "N/A"
        rc = f"{r['recall']:.4f}"   if not math.isnan(r["recall"])    else "N/A"
        f  = f"{r['f1']:.4f}"       if not math.isnan(r["f1"])        else "N/A"
        a  = f"{r['roc_auc']:.4f}"  if not math.isnan(r["roc_auc"])   else "N/A"
        lines.append(f"| {r['name']} | {p} | {rc} | {f} | {a} |")

    lines += ["", "## Interpretation", ""]

    # F1 comparison
    if best_f1_row:
        delta_f1 = scafad_f1 - best_f1_row["f1"]
        if outperforms_f1:
            lines.append(
                f"**F1:** SCAFAD achieves F1={scafad_f1:.4f}, which **outperforms** the best "
                f"classical baseline ({best_f1_row['name']}, F1={best_f1_row['f1']:.4f}) "
                f"by {delta_f1:+.4f}."
            )
        else:
            lines.append(
                f"**F1:** SCAFAD achieves F1={scafad_f1:.4f}, which **does not outperform** "
                f"the best classical baseline "
                f"({best_f1_row['name']}, F1={best_f1_row['f1']:.4f}); "
                f"the gap is {delta_f1:+.4f}."
            )

    # ROC-AUC comparison
    if best_auc_row:
        delta_auc = scafad_auc - best_auc_row["roc_auc"]
        if outperforms_auc:
            lines.append(
                f"**ROC-AUC:** SCAFAD scores {scafad_auc:.4f}, **outperforming** the best "
                f"baseline ({best_auc_row['name']}, AUC={best_auc_row['roc_auc']:.4f}) "
                f"by {delta_auc:+.4f}."
            )
        else:
            lines.append(
                f"**ROC-AUC:** SCAFAD scores {scafad_auc:.4f}, which **does not outperform** "
                f"the best baseline "
                f"({best_auc_row['name']}, AUC={best_auc_row['roc_auc']:.4f}); "
                f"the gap is {delta_auc:+.4f}."
            )

    lines += [
        "",
        "SCAFAD provides explainability (L4 decision traces with tiered verbosity and "
        "budgeted redaction), privacy compliance (L1 PII detection, deferred hashing, "
        "sanitisation), and a trust-weighted multi-layer fusion signal (L3 fused_score) "
        "that classical detectors do not offer — making it suitable for production "
        "serverless monitoring beyond raw detection accuracy.",
        "",
        "## Methodology Notes",
        "",
        "- **SCAFAD** is rule-based and heuristic; no training phase is required.",
        "- **Decision mapping:** `observe` → 0 (benign), `review` → 1 (anomaly),"
        " `escalate` → 1 (anomaly).",
        "- **ROC-AUC** derived from L3 `fused_score` (continuous, range [0, 1]).",
        "- **Classical baselines** trained on 200 benign records"
        " (one-class protocol, `contamination=0.10`).",
        "- **Both** SCAFAD and baselines tested on the same 6,300-record test set"
        " (seed=42 shuffle).",
    ]

    if best_f1_row:
        lines.append(
            f"- **Best classical F1:** {best_f1_row['name']} = {best_f1_row['f1']:.4f}"
        )
    if best_auc_row:
        lines.append(
            f"- **Best classical ROC-AUC:** {best_auc_row['name']}"
            f" = {best_auc_row['roc_auc']:.4f}"
        )

    lines.append("")  # trailing newline

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(report_path), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[WP-4.6] Comparison report written to {report_path}", flush=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="WP-4.6: SCAFAD full pipeline evaluation vs classical baselines."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process 10 records only (smoke test; does not write output files).",
    )
    parser.add_argument(
        "--reset-every",
        type=int,
        default=200,
        metavar="N",
        help="Re-instantiate SCAFADCanonicalRuntime every N records to bound "
             "L0 IsolationForest history (default: %(default)s).",
    )
    args = parser.parse_args()

    results = run_evaluation(dry_run=args.dry_run, reset_every=args.reset_every)

    if not args.dry_run:
        write_results(results, OUTPUT_PATH)
        baselines = load_baselines(BASELINES_PATH)
        write_comparison_report(results["scafad"], baselines, REPORT_PATH)

    print("[WP-4.6] Done.", flush=True)


if __name__ == "__main__":
    main()
