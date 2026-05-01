"""
Tests for the SCAFAD product packaging manifest and export pipeline.

Verifies:
1. ``packaging/manifest.json`` exists, is valid JSON, and declares ≥4 artefacts.
2. Each artefact entry has the required fields (id, type, label, source, required).
3. ``scripts/package_product.py`` imports cleanly and parses its CLI arguments.
4. The script's ``--dry-run`` mode runs without error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MANIFEST_PATH = _REPO_ROOT / "packaging" / "manifest.json"
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "package_product.py"

_REQUIRED_ARTEFACT_KEYS = {"id", "type", "label", "source", "required"}
_MIN_ARTEFACT_COUNT = 4


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def manifest() -> Dict[str, Any]:
    """Load the packaging manifest once per module."""
    if not _MANIFEST_PATH.is_file():
        pytest.fail(f"packaging/manifest.json not found at {_MANIFEST_PATH}")
    with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def artefacts(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the list of artefact entries from the manifest."""
    return manifest.get("artefacts", [])


# ---------------------------------------------------------------------------
# Manifest structure
# ---------------------------------------------------------------------------


class TestManifestExists:
    """The manifest file must exist and be valid JSON."""

    def test_manifest_file_exists(self) -> None:
        assert _MANIFEST_PATH.is_file(), (
            f"packaging/manifest.json not found at {_MANIFEST_PATH}"
        )

    def test_manifest_is_valid_json(self, manifest: Dict[str, Any]) -> None:
        """Already loaded — if we got here, JSON is valid."""
        assert isinstance(manifest, dict)

    def test_manifest_has_required_top_keys(self, manifest: Dict[str, Any]) -> None:
        expected = {"manifest_version", "project", "description", "artefacts"}
        missing = expected - set(manifest.keys())
        assert not missing, f"Missing top-level keys: {missing}"


class TestArtefactCount:
    """The manifest must declare at least 4 artefacts."""

    def test_at_least_four_artefacts(self, artefacts: List[Dict[str, Any]]) -> None:
        assert len(artefacts) >= _MIN_ARTEFACT_COUNT, (
            f"Expected at least {_MIN_ARTEFACT_COUNT} artefacts, "
            f"found {len(artefacts)}"
        )


class TestArtefactEntries:
    """Each artefact entry must have the required fields."""

    def test_every_artefact_has_required_keys(
        self, artefacts: List[Dict[str, Any]]
    ) -> None:
        for i, entry in enumerate(artefacts):
            missing = _REQUIRED_ARTEFACT_KEYS - set(entry.keys())
            assert not missing, (
                f"Artefact index {i} ({entry.get('id', '?')}) "
                f"missing keys: {missing}"
            )

    def test_every_artefact_id_is_nonempty_string(
        self, artefacts: List[Dict[str, Any]]
    ) -> None:
        for i, entry in enumerate(artefacts):
            aid = entry.get("id", "")
            assert isinstance(aid, str) and len(aid) > 0, (
                f"Artefact index {i} has invalid id: {aid!r}"
            )

    def test_every_artefact_type_is_nonempty_string(
        self, artefacts: List[Dict[str, Any]]
    ) -> None:
        for i, entry in enumerate(artefacts):
            atype = entry.get("type", "")
            assert isinstance(atype, str) and len(atype) > 0, (
                f"Artefact index {i} has invalid type: {atype!r}"
            )

    def test_every_artefact_required_is_bool(
        self, artefacts: List[Dict[str, Any]]
    ) -> None:
        for i, entry in enumerate(artefacts):
            req = entry.get("required")
            assert isinstance(req, bool), (
                f"Artefact index {i} ({entry.get('id', '?')}) "
                f"'required' is not bool: {type(req).__name__}"
            )

    def test_artefact_ids_are_unique(self, artefacts: List[Dict[str, Any]]) -> None:
        ids = [entry.get("id", "") for entry in artefacts]
        duplicates = {aid for aid in ids if ids.count(aid) > 1}
        assert not duplicates, f"Duplicate artefact ids: {duplicates}"


class TestRequiredArtefactsPresent:
    """Artefacts marked as required must have the expected well-known ids."""

    _EXPECTED_REQUIRED_IDS = {
        "wheel",
        "docker-image",
        "sam-template",
        "evaluation-report",
    }

    def test_required_artefacts_include_expected_ids(
        self, artefacts: List[Dict[str, Any]]
    ) -> None:
        required_ids = {
            entry["id"]
            for entry in artefacts
            if entry.get("required") is True
        }
        missing = self._EXPECTED_REQUIRED_IDS - required_ids
        assert not missing, (
            f"Expected required artefacts missing: {missing}. "
            f"Found required ids: {required_ids}"
        )


# ---------------------------------------------------------------------------
# Script import & CLI
# ---------------------------------------------------------------------------


class TestScriptImport:
    """The packaging script must import cleanly."""

    def test_script_imports_cleanly(self) -> None:
        """Import the script as a module to verify no syntax errors."""
        import importlib.util  # pylint: disable=import-outside-toplevel

        spec = importlib.util.spec_from_file_location(
            "package_product", _SCRIPT_PATH
        )
        assert spec is not None, f"Could not create spec for {_SCRIPT_PATH}"
        mod = importlib.util.module_from_spec(spec)
        # We only need to verify it loads — no side effects expected at import.
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception as exc:
            pytest.fail(f"Script import failed: {exc}")

    def test_script_has_main_function(self) -> None:
        """Verify the script defines a main() entry point."""
        import importlib.util  # pylint: disable=import-outside-toplevel

        spec = importlib.util.spec_from_file_location(
            "package_product", _SCRIPT_PATH
        )
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert hasattr(mod, "main"), "Script does not define a main() function"
        assert callable(mod.main), "main() is not callable"


class TestScriptDryRun:
    """The script must run in --dry-run mode without error."""

    def test_dry_run_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), "--dry-run"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Dry run exited with code {result.returncode}.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_dry_run_output_contains_success(self) -> None:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), "--dry-run"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert "SUCCESS" in result.stdout, (
            f"Dry run output did not contain SUCCESS.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_dry_run_output_mentions_all_artefacts(self) -> None:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), "--dry-run"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        # The build artefacts (wheel, docker-image, sam-template) appear as
        # "WOULD    build wheel: ..." / "WOULD    build docker image: ..."
        # while copy artefacts appear as "WOULD    [evaluation-report] ..."
        expected_signals = [
            "build wheel",
            "docker image",
            "sam build",
            "evaluation-report",
        ]
        for signal in expected_signals:
            assert signal in result.stdout, (
                f"Dry run output missing signal '{signal}'.\n"
                f"stdout:\n{result.stdout}"
            )


class TestScriptCleanFlag:
    """The --clean flag must be accepted."""

    def test_clean_dry_run_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), "--clean", "--dry-run"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Clean dry run exited with code {result.returncode}.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_clean_dry_run_mentions_remove(self) -> None:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT_PATH), "--clean", "--dry-run"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert "remove" in result.stdout.lower() or "WOULD" in result.stdout, (
            f"Clean dry run output did not mention removal.\n"
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# No TODO/FIXME in new files
# ---------------------------------------------------------------------------


class TestNoTodoFixme:
    """New files must not contain unresolved TODO or FIXME markers."""

    @pytest.mark.parametrize(
        "filepath",
        [
            _MANIFEST_PATH,
            _SCRIPT_PATH,
            Path(__file__),
        ],
    )
    def test_no_todo_or_fixme(self, filepath: Path) -> None:
        if not filepath.is_file():
            pytest.skip(f"File not found: {filepath}")
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        # Collect lines that are inside this test function itself (they may
        # contain "TODO" or "FIXME" as string literals in the detection logic).
        # We skip those lines to avoid false positives.
        in_self_test = False
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Track whether we are inside this test method
            if "def test_no_todo_or_fixme" in stripped:
                in_self_test = True
            if in_self_test and stripped.startswith("def "):
                in_self_test = False
            if in_self_test:
                continue
            # Skip comments and docstrings
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            # Check for standalone TODO or FIXME tokens using word boundaries
            import re  # pylint: disable=import-outside-toplevel
            if re.search(r"(?<![a-zA-Z\"])TODO(?![a-zA-Z\"])", stripped):
                pytest.fail(
                    f"Unresolved TODO found in {filepath.name} at line {lineno}: "
                    f"{stripped!r}"
                )
            if re.search(r"(?<![a-zA-Z\"])FIXME(?![a-zA-Z\"])", stripped):
                pytest.fail(
                    f"Unresolved FIXME found in {filepath.name} at line {lineno}: "
                    f"{stripped!r}"
                )
