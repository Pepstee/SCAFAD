"""Tests for the GUI demo seeder."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from scafad.gui.backend.config import GUISettings  # noqa: E402
from scafad.gui.backend.seed import generate_event, seed_database  # noqa: E402
from scafad.gui.backend.store import DetectionStore  # noqa: E402


def test_generate_event_returns_dict() -> None:
    rng = random.Random(0)
    for i in range(20):
        evt = generate_event(i, rng)
        assert "event_id" in evt
        assert "function_id" in evt
        assert "anomaly" in evt
        assert "duration" in evt


def test_generate_event_anomaly_distribution_includes_archetypes() -> None:
    rng = random.Random(42)
    seen = {generate_event(i, rng)["anomaly"] for i in range(400)}
    expected = {
        "benign", "memory_spike", "cpu_burst", "network_anomaly",
        "cold_start", "economic_abuse", "cascade_failure",
        "security_anomaly", "silent_failure",
    }
    # All eight anomaly archetypes plus benign baseline should appear.
    assert expected.issubset(seen), f"missing: {expected - seen}"


def test_seed_database_writes_rows(tmp_path: Path) -> None:
    settings = GUISettings(db_path=tmp_path / "seed.db", env="test", seed_event_count=8)
    written = seed_database(settings=settings, count=8, seed=7)
    assert written == 8
    store = DetectionStore(settings.db_path)
    assert store.total_count() == 8


def test_seed_database_truncates_by_default(tmp_path: Path) -> None:
    settings = GUISettings(db_path=tmp_path / "seed.db", env="test")
    seed_database(settings=settings, count=4, seed=1)
    seed_database(settings=settings, count=4, seed=2)
    store = DetectionStore(settings.db_path)
    assert store.total_count() == 4  # second run truncated the first
