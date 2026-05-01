"""Time window parsing and bin sizing for Phase 3 temporal aggregation.

This module provides utilities for Functions and ThreatMap pages to specify
time windows and bin the data accordingly.

The window spec is one of:
- "24h" → (now - 24h, now)
- "7d"  → (now - 7d, now)
- "30d" → (now - 30d, now)
- "custom" → (custom_since, custom_until), must satisfy since < until and span ≤ 90d
- None → defaults to "7d"

Empty windows (both None) are invalid; `parse_window()` raises ValueError.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple


def parse_window(
    spec: Optional[str] = None,
    *,
    custom_since: Optional[datetime] = None,
    custom_until: Optional[datetime] = None,
) -> Tuple[datetime, datetime]:
    """Parse a time-window spec into (since, until) datetimes.

    Args:
        spec: One of "24h", "7d", "30d", "custom", or None (defaults to "7d").
        custom_since: For spec="custom", the inclusive lower bound.
        custom_until: For spec="custom", the exclusive upper bound.

    Returns:
        Tuple of (since, until) UTC datetimes.

    Raises:
        ValueError: If spec is invalid, custom times are missing/invalid,
                   or span > 90 days.
    """
    now = datetime.now(timezone.utc)

    # Default to 7d if not specified
    if spec is None:
        spec = "7d"

    if spec == "24h":
        since = now - timedelta(hours=24)
        until = now
    elif spec == "7d":
        since = now - timedelta(days=7)
        until = now
    elif spec == "30d":
        since = now - timedelta(days=30)
        until = now
    elif spec == "custom":
        if custom_since is None or custom_until is None:
            raise ValueError("custom window requires custom_since and custom_until")
        since = custom_since
        until = custom_until
    else:
        raise ValueError(f"Invalid window spec: {spec}")

    # Validate custom range
    if since >= until:
        raise ValueError("Window since must be < until")

    span_seconds = (until - since).total_seconds()
    max_span_seconds = 90 * 24 * 60 * 60  # 90 days
    if span_seconds > max_span_seconds:
        raise ValueError(f"Window span exceeds 90 days: {span_seconds / (24 * 60 * 60):.1f}d")

    return since, until


def default_bins_for_window(window_seconds: int) -> str:
    """Return the default bin size (granularity) for a window duration.

    Args:
        window_seconds: Duration of the window in seconds.

    Returns:
        One of "1h", "6h", "1d", "3d" suitable for binning the window.
    """
    if window_seconds <= 24 * 60 * 60:  # ≤ 24h
        return "1h"
    elif window_seconds <= 7 * 24 * 60 * 60:  # ≤ 7d
        return "6h"
    elif window_seconds <= 30 * 24 * 60 * 60:  # ≤ 30d
        return "1d"
    else:  # ≤ 90d
        return "3d"


def bin_duration_seconds(bin_spec: str) -> int:
    """Return the duration of a bin in seconds.

    Args:
        bin_spec: One of "1h", "6h", "1d", "3d".

    Returns:
        Duration in seconds.

    Raises:
        ValueError: If bin_spec is not recognized.
    """
    durations = {
        "1h": 60 * 60,
        "6h": 6 * 60 * 60,
        "1d": 24 * 60 * 60,
        "3d": 3 * 24 * 60 * 60,
    }
    if bin_spec not in durations:
        raise ValueError(f"Invalid bin spec: {bin_spec}")
    return durations[bin_spec]


__all__ = [
    "parse_window",
    "default_bins_for_window",
    "bin_duration_seconds",
]
