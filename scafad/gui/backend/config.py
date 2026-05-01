"""Runtime configuration for the SCAFAD GUI backend."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Optional


_REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_DIR = _REPO_ROOT_DEFAULT / ".scafad-gui"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "dev.db"


def _detect_commit() -> str:
    """Best-effort short git commit hash for the running checkout.

    Returns the literal string ``"unknown"`` when git is unavailable or the
    working tree is not a git repository.  Never raises.
    """

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_REPO_ROOT_DEFAULT),
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


@dataclass
class GUISettings:
    """Configuration record for the FastAPI app and its dependencies.

    All fields can be overridden via environment variables prefixed with
    ``SCAFAD_GUI_*`` (see :func:`get_settings`).
    """

    env: str = "dev"
    """Short label shown by the EnvBadge component (``dev``/``staging``/``prod``)."""

    host: str = "127.0.0.1"
    port: int = 8088
    db_path: Path = field(default_factory=lambda: _DEFAULT_DB_PATH)
    cors_origins: List[str] = field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    version: str = "0.1.0"
    commit: str = field(default_factory=_detect_commit)
    sse_keepalive_seconds: float = 25.0
    """Heartbeat cadence for the ``/api/detections/stream`` SSE channel."""

    sse_max_history: int = 64
    """Maximum number of pending detections to buffer per SSE subscriber."""

    seed_event_count: int = 200
    """Default number of synthetic events the seeder pushes through the runtime."""

    def ensure_db_directory(self) -> None:
        """Create the parent directory for the SQLite store if it does not exist."""

        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


def _coerce_bool(raw: Optional[str], default: bool) -> bool:
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _build_settings_from_env() -> GUISettings:
    """Materialise a :class:`GUISettings` instance from environment variables."""

    db_path_env = os.environ.get("SCAFAD_GUI_DB_PATH")
    cors_env = os.environ.get("SCAFAD_GUI_CORS_ORIGINS")
    seed_count_env = os.environ.get("SCAFAD_GUI_SEED_COUNT")
    keepalive_env = os.environ.get("SCAFAD_GUI_SSE_KEEPALIVE")

    settings = GUISettings(
        env=os.environ.get("SCAFAD_GUI_ENV", "dev"),
        host=os.environ.get("SCAFAD_GUI_HOST", "127.0.0.1"),
        port=int(os.environ.get("SCAFAD_GUI_PORT", "8088")),
        db_path=Path(db_path_env) if db_path_env else _DEFAULT_DB_PATH,
        cors_origins=[o.strip() for o in cors_env.split(",")] if cors_env else
        ["http://localhost:5173", "http://127.0.0.1:5173"],
        version=os.environ.get("SCAFAD_GUI_VERSION", "0.1.0"),
        commit=os.environ.get("SCAFAD_GUI_COMMIT", _detect_commit()),
        sse_keepalive_seconds=float(keepalive_env) if keepalive_env else 25.0,
        seed_event_count=int(seed_count_env) if seed_count_env else 200,
    )
    settings.ensure_db_directory()
    return settings


@lru_cache(maxsize=1)
def get_settings() -> GUISettings:
    """Return a process-wide cached :class:`GUISettings` instance."""

    return _build_settings_from_env()


def reset_settings_cache() -> None:
    """Clear the :func:`get_settings` cache.

    Used by tests that need to switch the SQLite path between runs.
    """

    get_settings.cache_clear()


__all__ = ["GUISettings", "get_settings", "reset_settings_cache"]
