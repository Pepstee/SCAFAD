"""Unit tests for the comments table on :class:`DetectionStore`."""

from __future__ import annotations

from pathlib import Path

import pytest

from scafad.gui.backend.store import DetectionStore, NotFound, StoreError


def _store(tmp_path: Path) -> DetectionStore:
    return DetectionStore(tmp_path / "comments.db")


def test_add_comment_persists_markdown(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    comment = store.add_comment(case.id, "alice", "**hello**")
    assert comment.id
    assert comment.body_md == "**hello**"
    assert comment.author_id == "alice"


def test_add_comment_writes_case_event(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    store.add_comment(case.id, "alice", "ack")
    events = store.list_case_events(case.id)
    assert any(e.kind == "commented" for e in events)


def test_list_comments_orders_by_created_at(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    store.add_comment(case.id, "alice", "first")
    store.add_comment(case.id, "alice", "second")
    rows = store.list_comments(case.id)
    assert [r.body_md for r in rows] == ["first", "second"]


def test_empty_comment_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    with pytest.raises(StoreError):
        store.add_comment(case.id, "alice", "   ")


def test_comment_on_unknown_case_raises_not_found(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(NotFound):
        store.add_comment("no-such-case", "alice", "hi")


def test_delete_case_removes_its_comments(tmp_path: Path) -> None:
    store = _store(tmp_path)
    case = store.create_case(title="X", created_by="u")
    store.add_comment(case.id, "alice", "hi")
    store.delete_case(case.id, actor_id="u")
    assert store.list_comments(case.id) == []
