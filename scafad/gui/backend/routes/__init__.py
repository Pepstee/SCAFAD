"""HTTP routes for the SCAFAD GUI backend.

Each module under ``scafad.gui.backend.routes`` exports a ``router`` (an
:class:`fastapi.APIRouter`) registered by :func:`scafad.gui.backend.main.create_app`.
"""

from . import cases, detections, functions, health, inbox, ingest, stream, threat_map, views  # noqa: F401

__all__ = ["health", "detections", "ingest", "stream", "cases", "inbox", "views", "functions", "threat_map"]
