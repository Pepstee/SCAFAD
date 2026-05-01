# SCAFAD — Examiner Guide

**Serverless Context-Aware Framework for Anomaly Detection**
BSc (Hons) Computer Science Dissertation, Birmingham Newman University, CMU601 (2025–2026).

This README is written for the examiner. It tells you how to install, launch, exercise, and inspect the SCAFAD software submission. Every command in this document has been tested on Windows 10/11 (PowerShell) and on Ubuntu 22.04 (bash). Where the two differ, both are shown.

If you only have time for one thing: skip to **§3 Quick Start** and run the React dashboard. That demonstrates the full pipeline end-to-end in under five minutes.

---

## Contents

1. [What is SCAFAD?](#1-what-is-scafad)
2. [Prerequisites](#2-prerequisites)
3. [Quick Start (5 minutes)](#3-quick-start-5-minutes)
4. [Running the React GUI](#4-running-the-react-gui)
5. [Using the GUI with Live AWS Lambda](#5-using-the-gui-with-live-aws-lambda)
6. [Running the Evaluation Harness](#6-running-the-evaluation-harness)
7. [Running the Test Suite](#7-running-the-test-suite)
8. [Project Layout](#8-project-layout)
9. [Reproducing Headline Results](#9-reproducing-headline-results)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. What is SCAFAD?

SCAFAD is a seven-layer (L0–L6) anomaly-detection pipeline for AWS Lambda telemetry. It integrates five capabilities the prior literature treats in isolation:

1. Serverless-native telemetry collection (Layer 0; 26-detector ensemble)
2. Privacy-preserving processing through sanitisation and field-level redaction (Layer 1)
3. Multi-vector machine-learning fusion across heterogeneous detectors (Layers 2–3)
4. Per-decision explainability with budgeted templated rationales (Layer 4)
5. Deterministic MITRE ATT&CK alignment (Layer 5)

A Layer-6 feedback loop is also present (scaffolded; not drained in the current build — see the dissertation §3.9 for the disclosure).

The architecture, methodology, evaluation, and limitations are described in the accompanying dissertation (`SCAFAD_Dissertation.docx`). This README covers the software only.

---

## 2. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.10 also works for most paths but 3.11 is the supported version |
| pip | recent | usually bundled with Python |
| Node.js | 20+ | required for the React frontend |
| npm | recent | bundled with Node.js |
| Web browser | any modern | Chrome, Firefox, Edge, Safari |
| AWS CLI (optional) | v2 | only if you want to use the Live-on-AWS button (§5) |

Verify Python and Node:

**Windows (PowerShell):**
```powershell
python --version
node --version
npm --version
```

**Linux/macOS:**
```bash
python3 --version
node --version
npm --version
```

Ports used: **8765** (the GUI server) — keep it free. If §5 (live mode) is used, the AWS Lambda call leaves the local machine; nothing else binds locally.

---

## 3. Quick Start (5 minutes)

This installs everything and launches the React dashboard. From the `submission/software/` directory:

**Windows (PowerShell):**

```powershell
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Build the React frontend (one-time, ~2 minutes)
cd scafad\gui\frontend
npm install
npm run build
cd ..\..\..

# 3. Launch the dashboard
python start_gui.py
```

**Linux/macOS:**

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Build the React frontend (one-time)
cd scafad/gui/frontend
npm install
npm run build
cd ../../..

# 3. Launch the dashboard
python3 start_gui.py
```

**Open** [http://localhost:8765](http://localhost:8765) in your browser.

Expected: the React analyst console — Dashboard, Inbox, Cases, Detection Detail, Threat Map, System Status, Settings, Audit. The seed step (run automatically) populates the dashboard with ~200 sample detections produced by the real runtime.

To stop the server, press **Ctrl+C** in the terminal.

---

## 4. Running the React GUI

§3 (Quick Start) is the recommended path for examiners. This section explains what is happening and gives a development-mode alternative.

### 4.1 Production mode (`start_gui.py`)

`start_gui.py` runs `scafad/gui/gui_server.py`, a small Python stdlib HTTP server on port 8765. It serves the pre-built React app from `scafad/gui/frontend/dist/` and proxies live-AWS calls (POST `/invoke`) to the AWS CLI.

This is the simplest path. It needs the `dist/` directory to exist, which is why §3 includes `npm run build`.

If you want to rebuild the frontend after pulling new code:

```bash
cd scafad/gui/frontend
npm run build
cd ../../..
python start_gui.py     # or python3 start_gui.py
```

### 4.2 Development mode (Vite + FastAPI)

For viewing the frontend with hot reload, use the bundled launcher. This starts a FastAPI backend on port 8088 and the Vite dev server on port 5173.

**Windows:**

```powershell
# One-time: install backend dependencies (already covered by requirements.txt
# but the dev mode needs FastAPI + uvicorn explicitly)
pip install fastapi "uvicorn[standard]" sse-starlette pydantic

# Allow the launcher script to run (one-time)
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# Launch
.\scripts\run_gui_dev.ps1
```

**Linux/macOS:**

```bash
pip install fastapi "uvicorn[standard]" sse-starlette pydantic
bash scripts/run_gui_dev.sh
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

Press **Ctrl+C** in the terminal to stop both processes.

---

## 5. Using the GUI with Live AWS Lambda

The repository ships with read-only AWS credentials (`aws_credentials.json`) bound to a deployed SCAFAD Lambda function (`scafad-layer0-dev`, region `eu-west-2`). These credentials let the **Run Live on AWS** button invoke the live Lambda end-to-end and stream the results back to the dashboard. They are intentionally limited to invoke-only on a single function.

### 5.1 Credentials file

Already at the project root:

```
submission/software/aws_credentials.json
```

Contents (verbatim — these are the credentials provided to the examiner panel):

```json
{
  "aws_access_key_id": "AKIA43UQSSOIKJZYNUJS",
  "aws_secret_access_key": "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",
  "aws_region": "eu-west-2",
  "aws_account_id": "883992728464",
  "lambda_function_name": "scafad-layer0-dev",
  "ecr_repository": "scafad-layer0"
}
```

### 5.2 Configure the credentials

Pick one of the three options below.

**Option A — Environment variables (per-terminal, easiest)**

**Windows (PowerShell):**

```powershell
$env:AWS_ACCESS_KEY_ID     = "AKIA43UQSSOIKJZYNUJS"
$env:AWS_SECRET_ACCESS_KEY = "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"
$env:AWS_DEFAULT_REGION    = "eu-west-2"
```

**Linux/macOS:**

```bash
export AWS_ACCESS_KEY_ID="AKIA43UQSSOIKJZYNUJS"
export AWS_SECRET_ACCESS_KEY="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"
export AWS_DEFAULT_REGION="eu-west-2"
```

The variables only apply to the terminal you set them in. Launch `python start_gui.py` from that same terminal.

**Option B — AWS CLI named profile (one-time setup)**

```bash
aws configure --profile scafad
# AWS Access Key ID:     AKIA43UQSSOIKJZYNUJS
# AWS Secret Access Key: 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
# Default region:        eu-west-2
# Default output:        json
```

Then before launching the GUI:

```bash
export AWS_PROFILE=scafad           # Linux/macOS
$env:AWS_PROFILE = "scafad"          # Windows
```

**Option C — Use the AWS CLI's default profile**

Run `aws configure` (no `--profile`) and paste the same values. The GUI will then pick up the default profile automatically.

### 5.3 Verify AWS access

Before clicking "Run Live on AWS", confirm the credentials work:

```bash
aws lambda get-function --function-name scafad-layer0-dev --region eu-west-2
```

Expected: a JSON blob describing the deployed Lambda. If you see `An error occurred (AccessDeniedException)` or `(InvalidClientTokenId)`, the credentials aren't being picked up — re-check Option A/B above.

### 5.4 Use the live mode in the GUI

1. Launch the GUI (`python start_gui.py`).
2. Open [http://localhost:8765](http://localhost:8765).
3. Navigate to the **Inbox** or **Detection Detail** page.
4. Click **Run Live on AWS**.
5. The browser POSTs the telemetry payload to the local server, which calls AWS Lambda via the AWS CLI, parses the response, and streams the per-layer breakdown back into the dashboard. Expect 1–3 seconds for a warm invocation, ~5 seconds for a cold start.

If the button does nothing or returns an error, see §10 (Troubleshooting).

### 5.5 Security note

The provided credentials have IAM policies restricting them to:
- `lambda:InvokeFunction` on `scafad-layer0-dev` only
- `logs:GetLogEvents` on the matching CloudWatch log group only

They cannot create resources, modify policies, or invoke other functions. Once the examination concludes the credentials will be rotated by the author.

---

## 6. Running the Evaluation Harness

To reproduce the dissertation's evaluation:

```bash
python scafad/evaluate_scafad.py
```

(Or `python3` on Linux.)

Expected output (~35 seconds on commodity hardware):

```
SCAFAD-R Evaluation Harness — run <timestamp>
============================================================
  T-013  Layer-1 Input Validation                ... PASS
  T-014  Layer-1 Preservation Assessment         ... PASS
  T-015  Layer-1 Privacy Compliance              ... PASS
  T-016  Layer-1 Sanitisation                    ... PASS
  T-017  Layer-1 Deferred Hashing                ... PASS
  T-018  Layer-2 Multi-Vector Detection          ... PASS
  T-019  Layer-0 Adapter                         ... PASS
  T-020  Layer-1 Extended Modules                ... PASS
  T-021  Layer-3 Trust-Weighted Fusion           ... PASS
  T-022  Layer-4 Tiered Explainability           ... PASS
  T-023  Layer-5 MITRE Threat Alignment          ... PASS
  T-024  Layer-6 Feedback Learning               ... PASS
  T-025  Runtime E2E Integration                 ... PASS
  T-026  Layer-0 Core Tests                      ... PASS
  T-027  Layer-0 Detector Registry               ... PASS
============================================================
Total tests : 536        Failures : 0        Errors : 0
Status      : ALL_PASS
Artefact    : evaluation/results/evaluation_<timestamp>.json
```

The artefact JSON contains per-suite test counts, timing, and pass/fail status. It is timestamped to allow side-by-side comparison across runs.

### Reproducing the leakage-controlled ablation

```bash
python evaluation/run_ablation_ablated_only.py
```

This re-runs the evaluation pipeline with the Layer-2 SemanticDeviationCore zeroed (the ablation that quantifies label leakage; see dissertation §4.7 and §4.9). Expected output: ROC-AUC = 0.9045, calibrated F1 = 0.8764 at threshold 0.06. Result is written to `evaluation/results/ablation_semantic_deviation.json`.

---

## 7. Running the Test Suite

```bash
python -m pytest tests/ -q
```

Expected: 1,629 tests collected, all passing. The test estate covers:

- All 26 Layer-0 detectors (unit tests per detector)
- Layer-1 validation, sanitisation, privacy, hashing, preservation
- Layer-2 multi-vector detection
- Layer-3 trust-weighted fusion
- Layer-4 explainability and decision logic
- Layer-5 MITRE ATT&CK alignment
- Layer-6 feedback integration
- Runtime end-to-end integration
- GUI backend routes (FastAPI)
- Adversarial resilience (GAN-based attack scenarios)
- Economic abuse detection

To run a subset:

```bash
python -m pytest tests/unit/ -q                      # unit tests only (~1,400 tests)
python -m pytest tests/unit/test_detector_*.py -q    # detector tests only (104 tests)
python -m pytest tests/test_006_e2e_integration.py   # end-to-end smoke
```

---

## 8. Project Layout

```
submission/software/
├── README.md                        ← this file
├── SUBMISSION_MANIFEST.md           ← contents inventory
├── aws_credentials.json             ← credentials for §5 live mode
├── start_gui.py                     ← GUI launcher (entry point for §3)
├── requirements.txt                 ← Python dependencies
├── pyproject.toml                   ← project metadata
├── conftest.py                      ← pytest path bootstrap
│
├── scafad/                          ← framework source (~158 modules)
│   ├── __init__.py
│   ├── runtime/                     ← Lambda entry, runtime orchestration
│   ├── layer0/                      ← telemetry ingestion + 26 detectors
│   ├── layer1/                      ← privacy & hashing pipeline
│   ├── layer2/                      ← multi-vector detection (4 engines)
│   ├── layer3/                      ← trust-weighted fusion
│   ├── layer4/                      ← explainability & decision
│   ├── layer5/                      ← MITRE ATT&CK alignment
│   ├── layer6/                      ← feedback learning (scaffolded)
│   ├── gui/
│   │   ├── gui_server.py            ← Python stdlib HTTP server
│   │   ├── backend/                 ← FastAPI app (dev-mode backend)
│   │   └── frontend/                ← React + Vite app
│   │       ├── src/                 ← TypeScript sources
│   │       ├── dist/                ← built bundle (created by `npm run build`)
│   │       ├── package.json
│   │       └── vite.config.ts
│   └── evaluate_scafad.py           ← canonical evaluation harness
│
├── tests/                           ← 1,629 tests (unit + integration + formal)
│   ├── unit/                        ← per-component tests
│   ├── formal/                      ← formal property tests
│   └── test_*.py                    ← integration & smoke tests
│
├── evaluation/                      ← evaluation scripts and results
│   ├── run_ablation_ablated_only.py ← leakage-controlled ablation
│   ├── results/
│   │   ├── scafad_results.json      ← headline metrics
│   │   ├── baselines_results.json   ← 14-baseline panel
│   │   ├── optimal_threshold.json   ← grid-search calibration record
│   │   └── ablation_semantic_deviation.json
│   └── figures/
│
├── baselines/                       ← 14-baseline reference detectors
├── datasets/                        ← synthetic eval corpus + manifest
├── aws_deployment/                  ← SAM/Lambda deployment helpers
├── scripts/
│   ├── run_gui_dev.ps1              ← Windows dev-mode launcher
│   └── run_gui_dev.sh               ← Linux/macOS dev-mode launcher
└── template.yaml                    ← AWS SAM template
```

---

## 9. Reproducing Headline Results

The dissertation makes four numerical claims about the headline evaluation. Each one is reproducible:

| Claim | How to reproduce |
|---|---|
| ROC-AUC = 1.0000 (standard pipeline) | `evaluation/results/scafad_results.json` — pre-computed; or rerun via `evaluate_scafad.py` |
| ROC-AUC = 0.9045 (ablated, oracle off) | `python evaluation/run_ablation_ablated_only.py` |
| Best-baseline ROC-AUC = 0.8954 (ZScore, ν = 3.0) | `evaluation/results/baselines_results.json` |
| Calibrated threshold = 0.09; F1 = 1.0000 | `evaluation/results/optimal_threshold.json` (cache_source field documents that the threshold was set on the seed-42 evaluation corpus — disclosed in dissertation §4.7) |

The synthetic corpus (`datasets/synthetic_eval_dataset.json.gz`, 6,300 records, seed = 42) regenerates deterministically:

```bash
python datasets/generate_eval_dataset.py --seed 42 --output datasets/synthetic_eval_dataset.json.gz
```

---

## 10. Troubleshooting

### `pip install -r requirements.txt` fails on Windows

Some scientific packages occasionally fail to find pre-built wheels on Windows. Try:

```powershell
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

If a specific package fails (e.g. `scipy`), install Microsoft Build Tools for C++ from [https://visualstudio.microsoft.com/visual-cpp-build-tools/](https://visualstudio.microsoft.com/visual-cpp-build-tools/) and retry.

### `npm run build` fails with "esbuild platform mismatch"

This means the `node_modules/` directory was built on a different OS. Delete it and reinstall:

**Windows:**
```powershell
cd scafad\gui\frontend
Remove-Item -Recurse -Force node_modules
Remove-Item -Force package-lock.json
npm install
npm run build
```

**Linux/macOS:**
```bash
cd scafad/gui/frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### `python start_gui.py` says "Missing React GUI build"

The frontend has not been built. Run:

```bash
cd scafad/gui/frontend
npm install
npm run build
cd ../../..
python start_gui.py
```

### Port 8765 already in use

Another instance of `start_gui.py` is still running. Find and stop it:

**Windows:**
```powershell
netstat -ano | findstr :8765
Stop-Process -Id <PID> -Force
```

**Linux/macOS:**
```bash
lsof -i :8765
kill <PID>
```

### Browser shows the dashboard but pages are blank

Open the browser developer tools (F12) and check the **Network** tab. If you see 404s or 5xx responses on `/api/*` URLs, the backend isn't running. If you launched via `start_gui.py`, the live AWS pathway via `/invoke` is active but the FastAPI seed data is not. Use the dev-mode launcher (§4.2) for the full backend experience.

### "Run Live on AWS" button does nothing

The most common causes:

1. **AWS credentials not set** — re-check §5.2.
2. **AWS CLI not installed** — install from [https://aws.amazon.com/cli/](https://aws.amazon.com/cli/) and verify with `aws --version`.
3. **Credentials picked up but Lambda not reachable** — verify with the command in §5.3.
4. **Browser console error** (F12) — look for messages like `Failed to fetch /invoke`. If `start_gui.py` is running and you can hit the dashboard, the `/invoke` POST should succeed.

### `python -m pytest tests/` reports collection errors

Run from the `submission/software/` directory (not from `submission/software/scafad/`). The repo-root `conftest.py` adds the correct paths to `sys.path`. If you still see errors, install missing dependencies:

```bash
pip install pytest networkx jsonschema email-validator boto3 aiohttp scipy scikit-learn fastapi "uvicorn[standard]" sse-starlette pydantic
```

### Evaluation harness reports failures

If `evaluate_scafad.py` reports anything other than `ALL_PASS`, the dependency set is incomplete. The harness uses fallback implementations for missing scientific libraries; failures usually indicate a broken Python environment. Recreate it cleanly:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python scafad/evaluate_scafad.py
```

---

## Contact

For evaluation questions, please contact the author through the examiner-board channel.

The accompanying dissertation (`SCAFAD_Dissertation.docx`) is the primary deliverable; this software submission supports its empirical claims and provides the reproduction artefacts referenced throughout.

---

*Submission date: 1 May 2026 · Module CMU601 · Birmingham Newman University*
