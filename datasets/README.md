# datasets/

This directory contains synthetic and archived telemetry datasets used by the
SCAFAD test suite and evaluation harness.

## archived_payloads/

**Provenance:** Captured from live SCAFAD Layer 0 runs on 2025-08-09 during
pre-dissertation exploratory experiments. Files are committed to the repository
as permanent regression anchors.

**Format:** Each `payload_*.json` file is a single AWS Lambda invocation
telemetry record in the SCAFAD Layer 0 native format.  The companion
`invocation_master_log.jsonl` is the corresponding batch log from the same run.

**Migration:** These files were originally stored under
`legacy/archive/generated/telemetry/payloads/` and were moved here by WP-2.4
(DL-025, 2026-04-20) as part of the Phase 2 dependency and CI hygiene phase.

**Tests:** `tests/test_005_archived_dataset_pipeline.py` loads these files and
exercises the full L0 → L1 pipeline against them.  The test falls back to
synthetic data automatically if the directory contains fewer than 16 payloads,
so the permanent test set remains green even in environments where the NTFS
mount does not expose new files from Linux.

## serverless_traces.py

Synthetic trace generator used by the i-GNN and graph analysis unit tests.
