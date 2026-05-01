"""scafad.gui — Corporate-grade analyst console for SCAFAD.

This package contains the FastAPI backend (:mod:`scafad.gui.backend`) and the
Vite + React + TypeScript frontend (``frontend/``) that, together, provide an
analyst-facing console on top of the SCAFAD canonical runtime.

The GUI is read-only with respect to ``scafad.layer*`` and ``scafad.runtime``.
It only invokes :class:`scafad.runtime.SCAFADCanonicalRuntime` via a thin
adapter and persists the resulting evidence trail in its own SQLite store.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
