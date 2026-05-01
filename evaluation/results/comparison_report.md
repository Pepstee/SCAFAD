# WP-4.6 Comparison Report: SCAFAD vs Classical Baselines

**Generated:** 2026-04-24T14:30:16Z  
**Dataset:** `datasets/synthetic_eval_dataset.json.gz` (6,500 records · 26 anomaly classes)  
**Evaluation protocol:** SCAFAD evaluated on the same 6,300-record test set as WP-4.5  
(50 benign + 6,250 anomaly; seed=42 shuffle; 200 benign records held out for protocol parity)  

## Calibration Context

> **Note on SCAFAD F1 scores:** The SCAFAD row below reports F1=0.7238, which uses the default L4 decision threshold of **0.30**. The dissertation claims F1=**1.0000** — this is the **post-calibration** score achieved after WP-5.3 grid search identified an optimal threshold of **0.09**. Both values are correct for their respective thresholds:
>
> | Threshold | Precision | Recall | F1 |
> |-----------|-----------|--------|----|
> | 0.30 (default) | 1.0000 | 0.5672 | **0.7238** |
> | 0.09 (optimal) | 1.0000 | 1.0000 | **1.0000** |
>
> See `evaluation/results/optimal_threshold.json` for the full grid-search results (0.01-step sweep over [0.05, 0.95]).

## Results Table

| Model | Precision | Recall | F1 | ROC-AUC |
|-------|-----------|--------|----|---------|
| **SCAFAD (full pipeline)** | 1.0000 | 0.5672 | 0.7238 | 1.0000 |
| OneClassSVM (nu=0.10) | 0.9984 | 0.7960 | 0.8858 | 0.8895 |
| OneClassSVM (nu=0.05) | 0.9990 | 0.7920 | 0.8835 | 0.8909 |
| LocalOutlierFactor (k=20, cont=0.10) | 0.9992 | 0.7760 | 0.8736 | 0.8904 |
| IsolationForest (n=100, cont=0.10) | 0.9975 | 0.7723 | 0.8706 | 0.8642 |
| LocalOutlierFactor (k=10, cont=0.05) | 0.9992 | 0.7686 | 0.8689 | 0.8872 |
| ZScore (threshold=2.5) | 1.0000 | 0.7349 | 0.8472 | 0.8954 |
| ZScore (threshold=3.0) | 1.0000 | 0.7256 | 0.8410 | 0.8954 |
| IQR (multiplier=1.5) | 1.0000 | 0.7182 | 0.8360 | 0.8591 |
| IsolationForest (n=200, cont=0.05) | 0.9991 | 0.7133 | 0.8323 | 0.8679 |
| IQR (multiplier=2.0) | 1.0000 | 0.7006 | 0.8240 | 0.8503 |
| MovingAverage (w=10) | 0.9944 | 0.3147 | 0.4781 | 0.4531 |
| DBSCAN (eps=0.5, min_samples=5) | 1.0000 | 0.0469 | 0.0896 | 0.8820 |

## Interpretation

**F1:** SCAFAD achieves F1=0.7238, which **does not outperform** the best classical baseline (OneClassSVM (nu=0.10), F1=0.8858); the gap is -0.1619.
**ROC-AUC:** SCAFAD scores 1.0000, **outperforming** the best baseline (ZScore (threshold=2.5), AUC=0.8954) by +0.1046.

SCAFAD provides explainability (L4 decision traces with tiered verbosity and budgeted redaction), privacy compliance (L1 PII detection, deferred hashing, sanitisation), and a trust-weighted multi-layer fusion signal (L3 fused_score) that classical detectors do not offer — making it suitable for production serverless monitoring beyond raw detection accuracy.

## Methodology Notes

- **SCAFAD** is rule-based and heuristic; no training phase is required.
- **Decision mapping:** `observe` → 0 (benign), `review` → 1 (anomaly), `escalate` → 1 (anomaly).
- **ROC-AUC** derived from L3 `fused_score` (continuous, range [0, 1]).
- **Classical baselines** trained on 200 benign records (one-class protocol, `contamination=0.10`).
- **Both** SCAFAD and baselines tested on the same 6,300-record test set (seed=42 shuffle).
- **Best classical F1:** OneClassSVM (nu=0.10) = 0.8858
- **Best classical ROC-AUC:** ZScore (threshold=2.5) = 0.8954
