"""Unit tests for the saved_views table on :class:`DetectionStore`."""

from __future__ import annotations

from pathlib import Path

import pytest

from scafad.gui.backend.store import DetectionStore, NotFound, StoreError


def _store(tmp_path: Path) -> DetectionStore:
    return DetectionStore(tmp_path / "views.db")


def test_create_view(tmp_path: Path) -> None:
    store = _store(tmp_path)
    view = store.create_view(
        owner_id="alice",
        name="Critical only",
        filter_json={"severity": ["escalate"]},
    )
    assert view.id
    assert view.name == "Critical only"
    assert view.filter_json == {"severity": ["escalate"]}
    assert view.pinned is False


def test_list_views_filtered_by_owner(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_view(owner_id="alice", name="A", filter_json={})
    store.create_view(owner_id="bob", name="B", filter_json={})
    alice = store.list_views("alice")
    bob = store.list_views("bob")
    assert len(alice) == 1 and alice[0].name == "A"
    assert len(bob) == 1 and bob[0].name == "B"


def test_unique_per_owner(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_view(owner_id="alice", name="A", filter_json={})
    with pytest.raises(StoreError):
        store.create_view(owner_id="alice", name="A", filter_json={})


def test_update_view_changes_pinned_and_filters(tmp_path: Path) -> None:
    store = _store(tmp_path)
    view = store.create_view(owner_id="alice", name="A", filter_json={})
    updated = store.update_view(
        view.id, owner_id="alice", pinned=True, filter_json={"severity": ["review"]}
    )
    assert updated.pinned is True
    assert updated.filter_json == {"severity": ["review"]}


def test_delete_view(tmp_path: Path) -> None:
    store = _store(tmp_path)
    view = store.create_view(owner_id="alice", name="A", filter_json={})
    store.delete_view(view.id, owner_id="alice")
    assert store.get_view(view.id, "alice") is None


def test_delete_unknown_view_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(NotFound):
        store.delete_view("nope", owner_id="alice")


def test_pinned_views_first(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_view(owner_id="alice", name="A", filter_json={})
    store.create_view(owner_id="alice", name="B", filter_json={}, pinned=True)
    rows = store.list_views("alice")
    # pinned first
    assert rows[0].name == "B"
    assert rows[1].name == "A"


def test_owner_isolation_on_update(tmp_path: Path) -> None:
    store = _store(tmp_path)
    view = store.create_view(owner_id="alice", name="A", filter_json={})
    with pytest.raises(NotFound):
        store.update_view(view.id, owner_id="bob", name="hijacked")
