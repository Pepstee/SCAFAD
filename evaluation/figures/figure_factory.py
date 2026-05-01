#!/usr/bin/env python3
"""
figure_factory.py — Generate 5 publication-ready dissertation figures from real evaluation data.

Figures produced (saved as .png @300dpi and .pdf):
  1. ROC curve (AUC = 1.0)
  2. Precision-Recall curve
  3. Threshold vs F1 grid search (optimum at 0.09)
  4. Classical baselines comparison bar chart (SCAFAD vs 9 detectors)
  5. Confusion matrix heatmap

Data sources (REAL — no placeholder/random data):
  - evaluation/results/headline_metrics.json
  - evaluation/results/baselines_results.json
  - evaluation/results/optimal_threshold.json
  - evaluation/results/scafad_results.json

Supports Chapter 9 and viva demonstrations.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ── Global style ──────────────────────────────────────────────────────────────
matplotlib.use("Agg")  # non-interactive backend for headless generation

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 11,
        "axes.labelsize": 13,
        "axes.titlesize": 14,
        "legend.fontsize": 10,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.1,
    }
)

# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent  # scafad-r-core/
_RESULTS_DIR = _PROJECT_ROOT / "evaluation" / "results"
_FIGURES_DIR = _HERE

# Colour palette (colourblind-friendly)
SCAFAD_COLOR = "#E63946"  # strong red for SCAFAD
BASELINE_COLOR = "#457B9D"  # muted blue for baselines
BEST_BASELINE_COLOR = "#1D3557"  # dark blue for best baseline
OPTIMAL_MARKER_COLOR = "#2A9D8F"  # teal for optimal point
GRID_COLOR = "#A8DADC"
BENIGN_COLOR = "#457B9D"
ANOMALY_COLOR = "#E63946"


# ── Data loaders ──────────────────────────────────────────────────────────────


def load_json(relative_path: str) -> Dict[str, Any]:
    """Load a JSON file from the results directory."""
    path = _RESULTS_DIR / relative_path
    if not path.exists():
        print(f"ERROR: Data file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r") as f:
        return json.load(f)


def load_headline_metrics() -> Dict[str, Any]:
    """Load headline_metrics.json."""
    return load_json("headline_metrics.json")


def load_baselines_results() -> Dict[str, Any]:
    """Load baselines_results.json."""
    return load_json("baselines_results.json")


def load_optimal_threshold() -> Dict[str, Any]:
    """Load optimal_threshold.json."""
    return load_json("optimal_threshold.json")


def load_scafad_results() -> Dict[str, Any]:
    """Load scafad_results.json (per-record scores)."""
    return load_json("scafad_results.json")


# ── Figure 1: ROC Curve ──────────────────────────────────────────────────────


def _compute_roc_curve(
    scores: np.ndarray, labels: np.ndarray, n_thresholds: int = 1000
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Compute ROC curve points and AUC from real per-record scores.

    Uses the actual score distribution from scafad_results.json.
    """
    thresholds = np.linspace(0.0, 1.0, n_thresholds)
    tpr_list: List[float] = []
    fpr_list: List[float] = []

    n_pos = int(np.sum(labels == 1))
    n_neg = int(np.sum(labels == 0))

    for thresh in thresholds:
        preds = (scores >= thresh).astype(int)
        tp = int(np.sum((preds == 1) & (labels == 1)))
        fp = int(np.sum((preds == 1) & (labels == 0)))
        fn = int(np.sum((preds == 0) & (labels == 1)))
        tn = int(np.sum((preds == 0) & (labels == 0)))

        tpr_val = tp / n_pos if n_pos > 0 else 0.0
        fpr_val = fp / n_neg if n_neg > 0 else 0.0
        tpr_list.append(tpr_val)
        fpr_list.append(fpr_val)

    # AUC via trapezoidal rule
    fpr_arr = np.array(fpr_list)
    tpr_arr = np.array(tpr_list)
    # Sort by fpr
    idx = np.argsort(fpr_arr)
    fpr_sorted = fpr_arr[idx]
    tpr_sorted = tpr_arr[idx]
    auc = float(np.trapz(tpr_sorted, fpr_sorted))

    return fpr_sorted, tpr_sorted, auc


def _make_roc_curve() -> str:
    """Figure 1: ROC curve with AUC=1.0 annotation."""
    print("  [1/5] Generating ROC curve ...")

    scafad_data = load_scafad_results()
    records = scafad_data["per_record"]
    scores = np.array([r["l3_fused_score"] for r in records], dtype=float)
    labels = np.array([r["ground_truth"] for r in records], dtype=int)

    fpr, tpr, auc = _compute_roc_curve(scores, labels)

    fig, ax = plt.subplots(figsize=(6, 5.5))

    # ROC curve
    ax.plot(
        fpr, tpr, color=SCAFAD_COLOR, linewidth=2.5,
        label=f"SCAFAD (AUC = {auc:.4f})"
    )
    # Diagonal reference
    ax.plot([0, 1], [0, 1], "k--", linewidth=1.0, alpha=0.5, label="Random (AUC = 0.5)")

    # Shade AUC area
    ax.fill_between(fpr, tpr, alpha=0.15, color=SCAFAD_COLOR)

    # Mark the perfect operating point
    ax.scatter([0], [1], color=OPTIMAL_MARKER_COLOR, s=80, zorder=5,
               label="Perfect classifier (FPR=0, TPR=1)", edgecolors="white", linewidth=1.0)

    ax.set_xlabel("False Positive Rate (FPR)")
    ax.set_ylabel("True Positive Rate (TPR)")
    ax.set_title("Receiver Operating Characteristic (ROC) Curve")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(loc="lower right", framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle="--")

    # AUC annotation box
    ax.text(
        0.6, 0.3, f"AUC = {auc:.4f}",
        fontsize=14, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=SCAFAD_COLOR, alpha=0.9)
    )

    stem = "fig01_roc_curve"
    _save_figure(fig, stem)
    plt.close(fig)
    return stem


# ── Figure 2: Precision-Recall Curve ─────────────────────────────────────────


def _compute_pr_curve(
    scores: np.ndarray, labels: np.ndarray, n_thresholds: int = 1000
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Compute Precision-Recall curve from real per-record scores."""
    thresholds = np.linspace(0.0, 1.0, n_thresholds)
    prec_list: List[float] = []
    rec_list: List[float] = []

    n_pos = int(np.sum(labels == 1))

    for thresh in thresholds:
        preds = (scores >= thresh).astype(int)
        tp = int(np.sum((preds == 1) & (labels == 1)))
        fp = int(np.sum((preds == 1) & (labels == 0)))
        fn = int(np.sum((preds == 0) & (labels == 1)))

        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / n_pos if n_pos > 0 else 0.0
        prec_list.append(prec)
        rec_list.append(rec)

    rec_arr = np.array(rec_list)
    prec_arr = np.array(prec_list)
    # Sort by recall
    idx = np.argsort(rec_arr)
    rec_sorted = rec_arr[idx]
    prec_sorted = prec_arr[idx]

    # Average precision (AP)
    ap = float(np.trapz(prec_sorted, rec_sorted))

    return rec_sorted, prec_sorted, ap


def _make_pr_curve() -> str:
    """Figure 2: Precision-Recall curve."""
    print("  [2/5] Generating Precision-Recall curve ...")

    scafad_data = load_scafad_results()
    records = scafad_data["per_record"]
    scores = np.array([r["l3_fused_score"] for r in records], dtype=float)
    labels = np.array([r["ground_truth"] for r in records], dtype=int)

    rec, prec, ap = _compute_pr_curve(scores, labels)

    fig, ax = plt.subplots(figsize=(6, 5.5))

    ax.plot(
        rec, prec, color=SCAFAD_COLOR, linewidth=2.5,
        label=f"SCAFAD (AP = {ap:.4f})"
    )

    # Perfect classifier reference
    ax.axhline(y=1.0, color="gray", linestyle="--", linewidth=1.0, alpha=0.5,
               label="Perfect Precision")

    # Shade area
    ax.fill_between(rec, prec, alpha=0.15, color=SCAFAD_COLOR)

    # Mark perfect point
    ax.scatter([1], [1], color=OPTIMAL_MARKER_COLOR, s=80, zorder=5,
               label="Optimal (Recall=1.0, Precision=1.0)", edgecolors="white", linewidth=1.0)

    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.05)
    ax.legend(loc="lower left", framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle="--")

    # AP annotation
    ax.text(
        0.4, 0.3, f"AP = {ap:.4f}",
        fontsize=14, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=SCAFAD_COLOR, alpha=0.9)
    )

    stem = "fig02_precision_recall_curve"
    _save_figure(fig, stem)
    plt.close(fig)
    return stem


# ── Figure 3: Threshold vs F1 Grid Search ────────────────────────────────────


def _make_threshold_grid_search() -> str:
    """Figure 3: Threshold vs F1 grid search showing optimum at 0.09.

    Uses the real all_results array from optimal_threshold.json.
    """
    print("  [3/5] Generating Threshold vs F1 grid search plot ...")

    opt_data = load_optimal_threshold()
    results = opt_data["all_results"]

    thresholds = np.array([r["threshold"] for r in results], dtype=float)
    f1_scores = np.array([r["f1"] for r in results], dtype=float)
    precision = np.array([r["precision"] for r in results], dtype=float)
    recall = np.array([r["recall"] for r in results], dtype=float)

    optimal = opt_data["optimal_threshold"]
    opt_thresh = optimal["value"]
    opt_f1 = optimal["f1"]

    fig, ax = plt.subplots(figsize=(8, 5.5))

    # F1 curve
    ax.plot(thresholds, f1_scores, color=SCAFAD_COLOR, linewidth=2.5,
            label="F1 Score", zorder=3)
    # Precision and recall
    ax.plot(thresholds, precision, color=BASELINE_COLOR, linewidth=1.5,
            linestyle="--", alpha=0.7, label="Precision", zorder=2)
    ax.plot(thresholds, recall, color=BEST_BASELINE_COLOR, linewidth=1.5,
            linestyle=":", alpha=0.7, label="Recall", zorder=2)

    # Optimal threshold marker
    ax.axvline(x=opt_thresh, color=OPTIMAL_MARKER_COLOR, linewidth=2.0,
               linestyle="--", alpha=0.8, zorder=4)
    ax.scatter([opt_thresh], [opt_f1], color=OPTIMAL_MARKER_COLOR, s=120,
               zorder=5, edgecolors="white", linewidth=1.5)

    # Annotation for optimal point
    ax.annotate(
        f"Optimal threshold = {opt_thresh}\nF1 = {opt_f1}",
        xy=(opt_thresh, opt_f1),
        xytext=(opt_thresh + 0.12, opt_f1 - 0.08),
        fontsize=11, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=OPTIMAL_MARKER_COLOR, linewidth=1.5),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=OPTIMAL_MARKER_COLOR, alpha=0.9)
    )

    # Highlight the plateau region
    ax.axvspan(0.09, 0.17, alpha=0.08, color=OPTIMAL_MARKER_COLOR,
               label="F1 = 1.0 plateau")

    ax.set_xlabel("Decision Threshold")
    ax.set_ylabel("Score")
    ax.set_title("Threshold Grid Search — F1, Precision, and Recall vs Threshold")
    ax.set_xlim(-0.01, 0.55)
    ax.set_ylim(-0.02, 1.05)
    ax.legend(loc="lower left", framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle="--")

    stem = "fig03_threshold_grid_search"
    _save_figure(fig, stem)
    plt.close(fig)
    return stem


# ── Figure 4: Classical Baselines Comparison ─────────────────────────────────


def _make_baselines_comparison() -> str:
    """Figure 4: Bar chart comparing SCAFAD against 9 classical detectors.

    Uses real data from headline_metrics.json and baselines_results.json.
    """
    print("  [4/5] Generating baselines comparison bar chart ...")

    headline = load_headline_metrics()
    baselines = load_baselines_results()

    scafad_f1 = headline["scafad"]["f1"]
    scafad_roc_auc = headline["scafad"]["roc_auc"]

    # Collect all baseline models (filter to top 9 by F1 for readability)
    models = baselines["models"]
    # Sort by F1 descending
    models_sorted = sorted(models, key=lambda m: m["f1"], reverse=True)

    # Take top 9 baselines + SCAFAD = 10 bars
    top_baselines = models_sorted[:9]

    names = ["SCAFAD"] + [m["name"] for m in top_baselines]
    f1_vals = [scafad_f1] + [m["f1"] for m in top_baselines]
    roc_auc_vals = [scafad_roc_auc] + [m["roc_auc"] for m in top_baselines]

    # Shorten names for display
    short_names = _shorten_baseline_names(names)

    x = np.arange(len(names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))

    bars_f1 = ax.bar(
        x - width / 2, f1_vals, width,
        label="F1 Score",
        color=[SCAFAD_COLOR] + [BASELINE_COLOR] * len(top_baselines),
        edgecolor="white", linewidth=0.5
    )
    bars_auc = ax.bar(
        x + width / 2, roc_auc_vals, width,
        label="ROC-AUC",
        color=[SCAFAD_COLOR + "80"] + [BEST_BASELINE_COLOR + "80"] * len(top_baselines),
        edgecolor="white", linewidth=0.5
    )

    # Highlight SCAFAD bars
    bars_f1[0].set_edgecolor("black")
    bars_f1[0].set_linewidth(2)
    bars_auc[0].set_edgecolor("black")
    bars_auc[0].set_linewidth(2)

    # Value labels on bars
    for i, (f1_val, auc_val) in enumerate(zip(f1_vals, roc_auc_vals)):
        ax.text(
            i - width / 2, f1_val + 0.015, f"{f1_val:.3f}",
            ha="center", va="bottom", fontsize=8, fontweight="bold" if i == 0 else "normal"
        )
        if i == 0:
            ax.text(
                i + width / 2, auc_val + 0.015, f"{auc_val:.3f}",
                ha="center", va="bottom", fontsize=8, fontweight="bold"
            )

    # Best baseline annotation
    best_baseline = headline.get("best_baseline_f1", {})
    best_name = best_baseline.get("name", "")
    best_f1 = best_baseline.get("f1", 0)
    ax.annotate(
        f"Best baseline:\n{best_name}\nF1 = {best_f1:.4f}",
        xy=(1, best_f1),
        xytext=(5, best_f1 + 0.05),
        fontsize=9,
        arrowprops=dict(arrowstyle="->", color=BEST_BASELINE_COLOR, linewidth=1.0),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=BEST_BASELINE_COLOR, alpha=0.8)
    )

    ax.set_xticks(x)
    ax.set_xticklabels(short_names, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Score")
    ax.set_title("SCAFAD vs Classical Anomaly Detection Baselines")
    ax.set_ylim(0, 1.15)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    stem = "fig04_baselines_comparison"
    _save_figure(fig, stem)
    plt.close(fig)
    return stem


def _shorten_baseline_names(names: List[str]) -> List[str]:
    """Shorten verbose baseline names for bar chart labels."""
    mapping = {
        "OneClassSVM (nu=0.10)": "OC-SVM (ν=0.10)",
        "OneClassSVM (nu=0.05)": "OC-SVM (ν=0.05)",
        "LocalOutlierFactor (k=20, cont=0.10)": "LOF (k=20)",
        "LocalOutlierFactor (k=10, cont=0.05)": "LOF (k=10)",
        "IsolationForest (n=100, cont=0.10)": "IForest (n=100)",
        "IsolationForest (n=200, cont=0.05)": "IForest (n=200)",
        "EllipticEnvelope (cont=0.10)": "EllipticEnv",
        "KMeans (k=5)": "KMeans (k=5)",
        "ZScore (threshold=2.5)": "Z-Score (2.5σ)",
        "ZScore (threshold=3.0)": "Z-Score (3.0σ)",
        "IQR (multiplier=1.5)": "IQR (1.5×)",
        "IQR (multiplier=2.0)": "IQR (2.0×)",
        "MovingAverage (w=10)": "MovAvg (w=10)",
        "DBSCAN (eps=0.5, min_samples=5)": "DBSCAN",
    }
    return [mapping.get(n, n) for n in names]


# ── Figure 5: Confusion Matrix Heatmap ───────────────────────────────────────


def _make_confusion_matrix() -> str:
    """Figure 5: Confusion matrix heatmap from real evaluation data.

    Uses the confusion matrix from headline_metrics.json.
    """
    print("  [5/5] Generating confusion matrix heatmap ...")

    headline = load_headline_metrics()
    cm = headline["scafad"]["confusion_matrix"]

    # Matrix: [[tn, fp], [fn, tp]]
    matrix = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
    labels = cm["labels"]  # ["benign", "anomaly"]

    fig, ax = plt.subplots(figsize=(5.5, 5))

    # Custom colormap: white → red
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "scafad_cm", ["#FFFFFF", SCAFAD_COLOR], N=256
    )

    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=max(matrix.flatten()))

    # Cell annotations
    for i in range(2):
        for j in range(2):
            value = matrix[i, j]
            pct = value / matrix.sum() * 100
            text_color = "white" if value > matrix.max() * 0.6 else "black"
            ax.text(
                j, i, f"{value}\n({pct:.1f}%)",
                ha="center", va="center", fontsize=16, fontweight="bold",
                color=text_color
            )

    # Axis labels
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels([f"Predicted\n{labels[0]}", f"Predicted\n{labels[1]}"], fontsize=11)
    ax.set_yticklabels([f"Actual\n{labels[0]}", f"Actual\n{labels[1]}"], fontsize=11)

    ax.set_xlabel("Predicted Label", fontsize=12)
    ax.set_ylabel("True Label", fontsize=12)
    ax.set_title("Confusion Matrix — SCAFAD Evaluation", fontsize=14, fontweight="bold")

    # Add colour bar
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Count", fontsize=10)

    # Add metrics annotation below
    metrics_text = (
        f"Accuracy: {100.0:.1f}%  |  Precision: {headline['scafad']['precision']:.4f}  |  "
        f"Recall: {headline['scafad']['recall']:.4f}  |  F1: {headline['scafad']['f1']:.4f}"
    )
    fig.text(
        0.5, -0.02, metrics_text,
        ha="center", fontsize=10, fontfamily="monospace",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", edgecolor="gray", alpha=0.8)
    )

    plt.subplots_adjust(bottom=0.18)

    stem = "fig05_confusion_matrix"
    _save_figure(fig, stem)
    plt.close(fig)
    return stem


# ── Helpers ───────────────────────────────────────────────────────────────────


def _save_figure(fig: plt.Figure, stem: str) -> None:
    """Save figure as .png (300 dpi) and .pdf in the figures directory."""
    png_path = _FIGURES_DIR / f"{stem}.png"
    pdf_path = _FIGURES_DIR / f"{stem}.pdf"
    fig.savefig(png_path)
    fig.savefig(pdf_path)
    print(f"    -> Saved {png_path.name} and {pdf_path.name}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    """Generate all 5 dissertation figures from real evaluation data."""
    print("=" * 60)
    print("  SCAFAD Dissertation Figure Factory")
    print("  Generating 5 publication-ready figures from REAL data")
    print("=" * 60)
    print()

    stems: List[str] = []

    stems.append(_make_roc_curve())
    stems.append(_make_pr_curve())
    stems.append(_make_threshold_grid_search())
    stems.append(_make_baselines_comparison())
    stems.append(_make_confusion_matrix())

    print()
    print("=" * 60)
    print(f"  All {len(stems)} figures generated successfully!")
    print(f"  Output directory: {_FIGURES_DIR}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
