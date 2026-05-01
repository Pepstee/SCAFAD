# SCAFAD Analyst Console (`scafad/gui`)

> Phase 1 + Phase 2 of the corporate-grade analyst console for SCAFAD.
> Backend: FastAPI on `:8088`. Frontend: Vite + React on `:5173`.

This package adds an HTTP/JSON surface and a web UI on top of the SCAFAD
canonical runtime (`scafad.runtime.SCAFADCanonicalRuntime`). Phase 1
delivered the Operations Dashboard, Detection Detail, and a polished
shell for the rest of the navigation. **Phase 2 turns the placeholder
Inbox and Cases pages into a working triage and investigation flow:**
filter-aware Inbox with saved views, bulk actions, CSV export, and a
slide-over Case drawer with comments and lifecycle audit trail.

---

## 1 Architecture

```
project/scafad-r-core/
├── scafad/                   ← detection pipeline (read-only from GUI)
└── scafad/gui/               ← THIS PACKAGE
    ├── backend/              ← FastAPI app
    │   ├── main.py           ← app factory + uvicorn entrypoint
    │   ├── config.py         ← env-driven GUISettings
    │   ├── runtime_adapter.py← thin wrapper around SCAFADCanonicalRuntime
    │   ├── store.py          ← SQLite-backed DetectionStore
    │   ├── schemas.py        ← Pydantic v2 DTOs
    │   ├── event_bus.py      ← in-process pub/sub for SSE
    │   ├── seed.py           ← demo seeder (real runtime, ~200 events)
    │   └── routes/
    │       ├── health.py
    │       ├── detections.py
    │       ├── ingest.py
    │       └── stream.py     ← SSE endpoint (registered before /{id})
    └── frontend/             ← Vite + React + TypeScript app
        ├── package.json      ← scripts: dev, build, test
        ├── vite.config.ts    ← /api proxy → 127.0.0.1:8088
        ├── tailwind.config.ts
        └── src/
            ├── main.tsx
            ├── App.tsx
            ├── routes.tsx
            ├── styles/{tokens,globals}.css
            ├── lib/{api,types,format,keyboard}.ts        ← keyboard added in Phase 2
            ├── components/
            │   ├── shell/{AppShell,Sidebar,TopBar,EnvBadge}.tsx
            │   ├── ui/{Card,Badge,KPI,SeverityChip,DataTable,Empty,Skeleton}.tsx
            │   ├── inbox/                                ← Phase 2
            │   │   ├── FilterBar.tsx
            │   │   ├── SavedViews.tsx
            │   │   ├── BulkToolbar.tsx
            │   │   ├── InboxTable.tsx
            │   │   └── CaseBadge.tsx
            │   └── cases/                                ← Phase 2
            │       ├── CaseDrawer.tsx
            │       ├── StatePill.tsx
            │       ├── AssigneePicker.tsx
            │       ├── Comments.tsx
            │       └── LifecycleAuditList.tsx
            ├── pages/
            │   ├── Dashboard.tsx
            │   ├── DetectionDetail.tsx
            │   ├── Inbox.tsx                             ← rewritten in Phase 2
            │   ├── Cases.tsx                             ← rewritten in Phase 2
            │   └── {Functions,ThreatMap,SystemStatus,Settings,Audit}.tsx
            └── __tests__/
                ├── dashboard.smoke.test.tsx
                ├── severity-chip.test.tsx
                ├── sidebar.test.tsx
                ├── format.test.ts
                ├── inbox.smoke.test.tsx                  ← Phase 2
                ├── filter-bar.test.tsx                   ← Phase 2
                ├── saved-views.test.tsx                  ← Phase 2
                ├── bulk-toolbar.test.tsx                 ← Phase 2
                ├── case-drawer.test.tsx                  ← Phase 2
                ├── comments.test.tsx                     ← Phase 2
                └── keyboard-nav.test.tsx                 ← Phase 2
```

### Boundary rules

* `scafad/gui/` may import from `scafad.runtime` and `scafad.layer0.telemetry`.
* `scafad/gui/` **must not** write into any `scafad/layer*` or
  `scafad/runtime` module — Phase 1 was built without modifying any of them.
* The frontend never talks to `scafad/` directly. Only via the FastAPI HTTP
  layer.

---

## 2 Running it

### 2.1 One-command dev launcher

```bash
make gui-dev                       # backend on :8088 + frontend on :5173
make gui-dev SEED=0                # skip the demo seed step
```

PowerShell equivalent:

```powershell
./scripts/run_gui_dev.ps1
./scripts/run_gui_dev.ps1 -NoSeed
```

The launcher seeds the SQLite store via the real runtime (~200 events),
starts `uvicorn` for the backend, then runs `npm run dev` for the frontend.
Ctrl+C tears both down.

### 2.2 Backend only

```bash
make gui-backend                   # uvicorn --reload on :8088
# or
PYTHONPATH=.:scafad python -m uvicorn scafad.gui.backend.main:app \
  --host 127.0.0.1 --port 8088 --reload
```

### 2.3 Frontend only (assumes backend is up)

```bash
cd scafad/gui/frontend
npm install                        # one-time, ~60s
npm run dev                        # http://localhost:5173
```

### 2.4 Demo seeder

```bash
make gui-seed                      # ~200 events through the real runtime
# or
PYTHONPATH=.:scafad python -m scafad.gui.backend.seed --count 200
```

The seeder mixes nine event archetypes (benign baseline + 8 anomaly classes
including memory_spike, cpu_burst, network_anomaly, cold_start,
economic_abuse, cascade_failure, security_anomaly, silent_failure) so the
dashboard shows realistic severity distribution.

### 2.5 Tests

```bash
make gui-test                      # backend pytest + frontend vitest
# Backend only:
PYTHONPATH=.:scafad python -m pytest tests/unit/test_gui_backend_*.py \
  tests/integration/test_gui_e2e_ingest_to_query.py
# Frontend only:
cd scafad/gui/frontend && npm run test
```

### 2.6 Environment doctor

```bash
make gui-doctor                    # verify Python/Node/required deps
```

---

## 3 HTTP API contract (Phase 1)

All routes are mounted under `/api`. OpenAPI lives at `/openapi.json`,
Swagger UI at `/docs`.

| Method | Path                          | Purpose                                     | Response                                                                        |
|--------|-------------------------------|---------------------------------------------|---------------------------------------------------------------------------------|
| GET    | `/api/health`                 | liveness + version + commit                 | `{ ok, version, commit, started_at, env, db_path }`                             |
| GET    | `/api/system/status`          | per-layer health snapshot                   | `{ layers: LayerStatus[], detector_count, db_size_bytes, last_ingest_at, detections_total }` |
| GET    | `/api/detections`             | list with filters                           | `{ items: DetectionSummary[], total, page, page_size }`                         |
| GET    | `/api/detections/summary`     | KPI tiles + 24h severity histogram          | `{ open_count, severity_mix, ingest_rate_1h, layer_p95_ms, hist24h }`           |
| GET    | `/api/detections/{id}`        | full layer-by-layer evidence trail          | `DetectionDetail` (summary fields + `layer_payload`)                            |
| POST   | `/api/ingest`                 | run the runtime on an event and persist     | `{ id, severity, anomaly_type, mitre_techniques: [...] }` (201)                 |
| GET    | `/api/detections/stream`      | SSE feed of new detections / cases / bulks  | `event: detection|case|bulk\ndata: …` plus periodic `keepalive`                 |

Note the SSE route is registered **before** `/api/detections/{id}` so the
literal path `stream` is matched first.

### Filterable list

`GET /api/detections?severity=escalate&anomaly_type=memory_spike&since=2026-04-26T00:00:00Z&page_size=20`

Phase 2 ADDS optional query params (the existing four are unchanged):

* `mitre_technique=T1059` — substring match against the techniques column
* `decision=escalate` / `risk_band=high` — exact match
* `text=<needle>` — case-insensitive search across `event_id`,
  `function_id`, `correlation_id`
* `until=<iso>` — exclusive upper bound on `ingested_at`
* `case_status=open|triage|contained|closed|none` — joins through
  `case_detections`/`cases`; `none` matches detections with no linked case

`GET /api/detections/{id}` gains an OPTIONAL `case` field (a `CaseSummary`
or `null`) at the top level of the response.

### Phase-2 endpoints

| Method | Path | Purpose |
|---|---|---|
| GET    | `/api/cases`                    | list cases (status, assignee filters) |
| POST   | `/api/cases`                    | open new case (optional initial detections) |
| GET    | `/api/cases/{id}`               | full case |
| PATCH  | `/api/cases/{id}`               | mutate (requires `expected_version`; 409 on conflict) |
| DELETE | `/api/cases/{id}`               | hard delete |
| POST   | `/api/cases/{id}/attach`        | attach detection_ids |
| POST   | `/api/cases/{id}/detach`        | detach detection_ids |
| GET    | `/api/cases/{id}/events`        | append-only lifecycle audit |
| GET    | `/api/cases/{id}/comments`      | list markdown comments |
| POST   | `/api/cases/{id}/comments`      | add a comment |
| GET    | `/api/cases/{id}/detections`    | list linked detections |
| GET    | `/api/inbox/summary`            | filter-aware aggregates for the Inbox header |
| POST   | `/api/inbox/bulk_action`        | apply assign / dismiss / attach / open_case |
| GET    | `/api/inbox/export.csv`         | CSV stream of the active filter |
| GET    | `/api/views`                    | list saved views for the current user |
| POST   | `/api/views`                    | create saved view |
| PATCH  | `/api/views/{id}`               | rename / re-pin / re-filter |
| DELETE | `/api/views/{id}`               | delete |

### Live SSE feed

The stream emits an initial `hello` frame on connect, then:

* `event: detection` per new ingestion (Phase 1 — unchanged)
* `event: case` after any case CRUD (Phase 2)
* `event: bulk` after a bulk-action commit — single coalesced frame per
  ADR-15 to avoid invalidation storms (Phase 2)

…plus a `keepalive` every `SCAFAD_GUI_SSE_KEEPALIVE` seconds (default 25 s).

### Triage workflow

1. Open `/inbox`. Filter the queue with the sticky FilterBar (severity,
   anomaly type, MITRE technique, time window, case status, free text).
2. Save the active filter set as a named view (per-analyst). Pinned views
   surface at the top of the dropdown.
3. Select rows. The bulk toolbar appears; pick *Open new case*, *Attach
   to case*, *Assign to me*, *Dismiss*, or *Export CSV*.
4. From any row's CaseBadge (or the Cases page), open the **Case drawer**
   to inspect Overview, linked Detections, Comments, and the Lifecycle
   audit trail.
5. State transitions use optimistic concurrency: each PATCH carries
   `expected_version`. On conflict the drawer shows a yellow banner and
   refetches the case.

### Keyboard shortcuts

| Key       | Action                                 | Scope        |
|-----------|----------------------------------------|--------------|
| `j` / `↓` | Move row focus down                    | Inbox table  |
| `k` / `↑` | Move row focus up                      | Inbox table  |
| `Space`   | Toggle row selection                   | Inbox table  |
| `Enter`   | Open detection detail                  | Inbox table  |
| `c`       | Open case drawer for focused row       | Inbox table  |
| `a`       | Bulk assign selection to current user  | Inbox table  |
| `Esc`     | Close drawer / dialog                  | global       |

All shortcuts are inert when focus is inside an `input`, `textarea`,
`select`, or `[contenteditable]`.

### Pydantic schemas

See `scafad/gui/backend/schemas.py`. The TypeScript mirror is at
`scafad/gui/frontend/src/lib/types.ts`. Keeping them in sync is currently a
manual exercise; Phase 5 may auto-generate the TS file from the OpenAPI spec.

---

## 4 Configuration

Every setting can be overridden via environment variables:

| Variable                       | Default                          | Notes                                  |
|--------------------------------|----------------------------------|----------------------------------------|
| `SCAFAD_GUI_ENV`               | `dev`                            | shown by the EnvBadge                  |
| `SCAFAD_GUI_HOST`              | `127.0.0.1`                      | uvicorn bind address                   |
| `SCAFAD_GUI_PORT`              | `8088`                           | backend port                           |
| `SCAFAD_GUI_DB_PATH`           | `<repo>/.scafad-gui/dev.db`      | SQLite path; parent dir auto-created   |
| `SCAFAD_GUI_CORS_ORIGINS`      | `http://localhost:5173,http://127.0.0.1:5173` | comma-separated allow-list  |
| `SCAFAD_GUI_VERSION`           | `0.1.0`                          | reported in `/api/health`              |
| `SCAFAD_GUI_COMMIT`            | (auto-detected via git)          | reported in `/api/health`              |
| `SCAFAD_GUI_SSE_KEEPALIVE`     | `25`                             | seconds between SSE keep-alive frames  |
| `SCAFAD_GUI_SEED_COUNT`        | `200`                            | default events for the seeder          |

---

## 5 Persistence schema (SQLite, Phase 1 + Phase 2)

```sql
-- Phase 1
CREATE TABLE detections (
  id               TEXT PRIMARY KEY,
  ingested_at      TEXT NOT NULL,            -- ISO-8601 UTC
  event_id         TEXT NOT NULL,
  function_id      TEXT NOT NULL,
  anomaly_type     TEXT NOT NULL,
  severity         TEXT NOT NULL,            -- observe | review | escalate
  trust_score      REAL NOT NULL,
  mitre_techniques TEXT NOT NULL,            -- JSON array
  decision         TEXT,
  risk_band        TEXT,
  duration_ms      REAL NOT NULL DEFAULT 0,
  correlation_id   TEXT,
  layer_payload    TEXT NOT NULL             -- JSON: full CanonicalRuntimeResult.to_dict()
);

-- Phase 2 (additive — every CREATE uses IF NOT EXISTS)
CREATE TABLE cases (
  id              TEXT PRIMARY KEY,
  title           TEXT NOT NULL,
  status          TEXT NOT NULL,             -- open | triage | contained | closed
  severity_rollup TEXT NOT NULL,
  assignee_id     TEXT,
  opened_at       TEXT NOT NULL,
  closed_at       TEXT,
  created_by      TEXT NOT NULL,
  version         INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE case_detections (
  case_id         TEXT NOT NULL,
  detection_id    TEXT NOT NULL UNIQUE,      -- one-case-per-detection
  attached_at     TEXT NOT NULL,
  attached_by     TEXT NOT NULL,
  PRIMARY KEY (case_id, detection_id)
);
CREATE TABLE comments (
  id          TEXT PRIMARY KEY,
  case_id     TEXT NOT NULL,
  author_id   TEXT NOT NULL,
  body_md     TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
CREATE TABLE case_events (
  id           TEXT PRIMARY KEY,
  case_id      TEXT NOT NULL,
  kind         TEXT NOT NULL,                -- created/state_changed/assigned/…
  payload_json TEXT NOT NULL,
  actor_id     TEXT NOT NULL,
  created_at   TEXT NOT NULL                 -- microsecond precision
);
CREATE TABLE saved_views (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  owner_id    TEXT NOT NULL,
  filter_json TEXT NOT NULL,
  sort_json   TEXT NOT NULL DEFAULT '[]',
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL,
  pinned      INTEGER NOT NULL DEFAULT 0,
  UNIQUE (owner_id, name)
);
```

`layer_payload` carries the full evidence trail as JSON. Phase 4 may add an
FTS5 search index without changing the public API.

---

## 6 Phase 1 acceptance criteria

| # | Criterion                                                        | Status |
|---|------------------------------------------------------------------|--------|
| 1 | `make gui-dev` brings up backend (8088) + frontend (5173)        | ✅      |
| 2 | `GET /api/health` returns 200 with version/commit; `/docs` works | ✅      |
| 3 | `POST /api/ingest` runs the runtime and persists evidence        | ✅      |
| 4 | `GET /api/detections` lists; `/{id}` returns full evidence       | ✅      |
| 5 | Operations Dashboard renders 4 KPIs + feed + 24h chart           | ✅      |
| 6 | Detection Detail renders 7 evidence tabs                         | ✅      |
| 7 | Sidebar shows 8 entries; non-Phase-1 entries are placeholders    | ✅      |
| 8 | Backend pytest suite has ≥ 25 new tests                          | ✅      |
| 9 | Frontend vitest suite has ≥ 5 cases                              | ✅      |
| 10| Existing 924-test regression suite still passes                  | ✅      |
| 11| This README documents architecture, run, API, and seeder         | ✅      |

---

## 7 What this phase deliberately does not do

* **No auth.** A stub user `analyst@scafad.local` is hard-coded behind a
  `users.py` indirection; identity goes in Phase 5. A second stub user
  (`analyst-2@scafad.local`) is exposed via the seeder + AssigneePicker
  for demo purposes.
* **No PostgreSQL.** SQLite is used for Phases 1+2; Phase 4 may swap to
  Postgres behind the same `DetectionStore` interface.
* **No Docker bundle.** Phase 5 ships the GUI as a Docker Compose stack.
* **No Functions / Threat Map / System Status / Settings / Audit pages.**
  These remain placeholders (still flagged with the *Soon* badge in the
  sidebar).  They are decomposed in subsequent phase planners.
