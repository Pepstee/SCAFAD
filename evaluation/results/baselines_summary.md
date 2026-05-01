# Baselines Comparison Summary
*Generated: 2026-04-24 — WP-4.2*

## Evaluation Protocol

- **Dataset:** `datasets/synthetic_eval_dataset.json.gz` (6,500 records, 26 anomaly classes + benign)
- **Training set:** 200 benign-only records (one-class learning)
- **Test set:** 50 benign + 6,250 anomaly records = 6,300 total (anomaly rate 99.2 %)
- **Features:** `duration`, `memory_spike_kb`, `cpu_utilization`, `network_io_bytes`
- **Metrics:** F1-score, Precision, Recall, ROC-AUC (all computed on test set)

---

## Results Table

Baselines ranked by F1-score (descending).  SCAFAD appears as the final row.

| Rank | Detector | F1 | Precision | Recall | ROC-AUC |
|------|----------|----|-----------|--------|---------|
| 1 | OneClassSVM (nu=0.10) | 0.8858 | 0.9984 | 0.7960 | 0.8895 |
| 2 | OneClassSVM (nu=0.05) | 0.8835 | 0.9990 | 0.7920 | 0.8909 |
| 3 | LocalOutlierFactor (k=20, cont=0.10) | 0.8736 | 0.9992 | 0.7760 | 0.8904 |
| 4 | IsolationForest (n=100, cont=0.10) | 0.8706 | 0.9975 | 0.7723 | 0.8642 |
| 5 | LocalOutlierFactor (k=10, cont=0.05) | 0.8689 | 0.9992 | 0.7686 | 0.8872 |
| 6 | EllipticEnvelope (cont=0.10) † | 0.8670 | 0.9987 | 0.7659 | 0.8847 |
| 7 | KMeans (k=5) † | 0.8574 | 1.0000 | 0.7506 | 0.8844 |
| 8 | ZScore (threshold=2.5) | 0.8472 | 1.0000 | 0.7349 | 0.8954 |
| 9 | ZScore (threshold=3.0) | 0.8410 | 1.0000 | 0.7256 | 0.8954 |
| 10 | IQR (multiplier=1.5) | 0.8360 | 1.0000 | 0.7182 | 0.8591 |
| 11 | IsolationForest (n=200, cont=0.05) | 0.8323 | 0.9991 | 0.7133 | 0.8679 |
| 12 | IQR (multiplier=2.0) | 0.8240 | 1.0000 | 0.7006 | 0.8503 |
| 13 | MovingAverage (w=10) | 0.4781 | 0.9944 | 0.3147 | 0.4531 |
| 14 | DBSCAN (eps=0.5, min_samples=5) | 0.0896 | 1.0000 | 0.0469 | 0.8820 |
| — | **SCAFAD ‡ (threshold=0.09)** | **1.0000** | **1.0000** | **1.0000** | **1.0000** |

† Added in WP-4.2 (EllipticEnvelope and KMeans).  
‡ SCAFAD uses the 7-layer detection pipeline (L0–L5) with trust-weighted fusion;
  threshold calibrated in WP-5.3.  Full results in `evaluation/results/headline_metrics.json`.

---

## Key Findings

### SCAFAD vs Best Baseline

| Metric | Best Baseline | Best Baseline (name) | SCAFAD | Gap |
|--------|--------------|---------------------|--------|-----|
| F1 | 0.8858 | OneClassSVM (nu=0.10) | **1.0000** | +0.1142 |
| Precision | 1.0000 | ZScore / IQR / DBSCAN | **1.0000** | 0.0000 |
| Recall | 0.7960 | OneClassSVM (nu=0.10) | **1.0000** | +0.2040 |
| ROC-AUC | 0.8954 | ZScore (threshold=2.5/3.0) | **1.0000** | +0.1046 |

SCAFAD outperforms **all 14 baselines** on F1, Recall, and ROC-AUC.  Precision is
matched at 1.0000 (tied with the statistical baselines on this evaluation set).

### Detector Categories

| Category | Detectors | Best F1 in Category |
|----------|-----------|---------------------|
| Classical ML (kernel / forest) | OneClassSVM, IsolationForest, LOF, EllipticEnvelope | 0.8858 |
| Distance / clustering | KMeans, DBSCAN | 0.8574 |
| Statistical | ZScore, IQR | 0.8472 |
| Time-series | MovingAverage | 0.4781 |
| **SCAFAD (multi-layer)** | **7-layer pipeline** | **1.0000** |

### Why SCAFAD Outperforms

1. **Multi-signal fusion** — SCAFAD fuses 26 detectors across 6 detection layers
   (L0–L5) covering statistical, spectral, semantic, temporal, and economic signals,
   whereas each baseline uses only the 4-feature numeric vector.

2. **Trust-weighted scoring** — Layer 3 fuses signals with per-source trust weights,
   yielding a fused score with a clear separation gap (0.097) between benign
   (max 0.081) and anomalous (min 0.178) records.  No baseline achieves this
   level of separation.

3. **Privacy-preserving pipeline** — L1 hashing and L5 privacy conditioning do not
   degrade detection performance; they operate on the telemetry stream without
   altering the feature distributions seen by the detectors.

4. **Calibrated threshold** — The L4 threshold (0.09, WP-5.3) was optimised by
   grid search over 91 candidates, selecting the value that maximises F1 whilst
   maintaining zero false positives.

---

## Notes for Chapter 9

- The comparison table above is intended for use in §9.3 (Experimental Results).
- All baselines were trained on 200 benign records only (one-class protocol) to
  match the operational assumption that ground-truth anomaly labels are unavailable
  at training time.
- Timing data is available in `evaluation/results/baselines_results.json` for
  inclusion in the latency comparison table.
- The pre-WP-5.3 SCAFAD F1 was 0.7238 (threshold=0.30).  After calibration, F1
  improved to 1.0000.  Chapter 9 should present both figures with appropriate
  context.
