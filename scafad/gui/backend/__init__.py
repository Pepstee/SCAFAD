"""scafad.gui.backend — FastAPI service for the analyst console.

The backend exposes:

* ``GET  /api/health``                — liveness + version + commit
* ``GET  /api/system/status``         — layer-by-layer health snapshot
* ``GET  /api/detections``            — list with severity/type/since filters
* ``GET  /api/detections/summary``    — KPI aggregates for the Dashboard
* ``GET  /api/detections/{id}``       — full layer-by-layer evidence trail
* ``POST /api/ingest``                — drive the runtime, persist the result
* ``GET  /api/detections/stream``     — Server-Sent Events feed of new rows

Persistence is handled by :class:`scafad.gui.backend.store.DetectionStore`
(SQLite, WAL mode).  The backend never writes into any ``scafad.layer*`` or
``scafad.runtime`` module.
"""

from .config import GUISettings, get_settings

__all__ = ["GUISettings", "get_settings"]
