"""
Tests for the showreel reception kit (WP-5.12 Phase 1 — Task A).

Verifies that the repository is deterministic about where the showreel MP4
will live, how examiners discover it, and how CI verifies it — without
requiring the MP4 to exist yet.

All tests are tolerant of the PENDING state (i.e. they do NOT require
``presentation/showreel.mp4`` to be present).  Tests that would only make
sense once the recording is committed are deferred to Phase 2a.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Return the ``project/scafad-r-core`` root."""
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestShowreelReceptionKit:
    """Unit tests for the showreel reception kit artefacts."""

    # ------------------------------------------------------------------
    # 1. SHOWREEL_STATUS.md
    # ------------------------------------------------------------------

    def test_showreel_status_file_exists(self):
        """SHOWREEL_STATUS.md must exist and be non-empty."""
        path = _repo_root() / "presentation" / "SHOWREEL_STATUS.md"
        assert path.exists(), (
            f"presentation/SHOWREEL_STATUS.md not found at {path}. "
            "The reception kit must create this file."
        )
        assert path.is_file(), f"{path} is not a regular file"
        content = path.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, "SHOWREEL_STATUS.md is empty"

    def test_showreel_status_contains_yaml_frontmatter(self):
        """SHOWREEL_STATUS.md must begin with YAML front-matter delimiters."""
        path = _repo_root() / "presentation" / "SHOWREEL_STATUS.md"
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---"), (
            "SHOWREEL_STATUS.md does not start with YAML front-matter ('---')"
        )
        # There must be a closing '---' delimiter
        lines = content.splitlines()
        closing = [i for i, ln in enumerate(lines) if ln.strip() == "---" and i > 0]
        assert closing, "SHOWREEL_STATUS.md YAML front-matter is not closed by '---'"

    def test_showreel_status_has_valid_status_token(self):
        """SHOWREEL_STATUS.md front-matter must declare a recognised status."""
        path = _repo_root() / "presentation" / "SHOWREEL_STATUS.md"
        content = path.read_text(encoding="utf-8")
        valid_statuses = {"PENDING", "RECORDED_LOCAL", "RECORDED_EXTERNAL"}
        found = False
        for line in content.splitlines():
            if line.startswith("status:"):
                value = line.split(":", 1)[1].strip()
                assert value in valid_statuses, (
                    f"SHOWREEL_STATUS.md status '{value}' is not one of {valid_statuses}"
                )
                found = True
                break
        assert found, "SHOWREEL_STATUS.md does not contain a 'status:' field in front-matter"

    def test_showreel_status_is_pending(self):
        """SHOWREEL_STATUS.md must currently declare PENDING (no recording yet)."""
        path = _repo_root() / "presentation" / "SHOWREEL_STATUS.md"
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("status:"):
                value = line.split(":", 1)[1].strip()
                assert value == "PENDING", (
                    f"Expected status PENDING but found '{value}'. "
                    "Update this test when the recording is committed (Phase 2a)."
                )
                return
        raise AssertionError("No 'status:' field found in SHOWREEL_STATUS.md front-matter")

    def test_showreel_status_body_references_showreel_md(self):
        """SHOWREEL_STATUS.md body must point readers at presentation/showreel.md."""
        path = _repo_root() / "presentation" / "SHOWREEL_STATUS.md"
        content = path.read_text(encoding="utf-8")
        assert "showreel.md" in content, (
            "SHOWREEL_STATUS.md does not reference showreel.md in its body"
        )

    # ------------------------------------------------------------------
    # 2. showreel_url.txt.template
    # ------------------------------------------------------------------

    def test_showreel_url_template_exists(self):
        """showreel_url.txt.template must exist and be non-empty."""
        path = _repo_root() / "presentation" / "showreel_url.txt.template"
        assert path.exists(), (
            f"presentation/showreel_url.txt.template not found at {path}"
        )
        assert path.is_file(), f"{path} is not a regular file"
        content = path.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, "showreel_url.txt.template is empty"

    def test_showreel_url_template_documents_https_format(self):
        """showreel_url.txt.template must contain an example https:// URL."""
        path = _repo_root() / "presentation" / "showreel_url.txt.template"
        content = path.read_text(encoding="utf-8")
        has_https = any(
            re.match(r"^https://[^\s]+$", ln.strip())
            for ln in content.splitlines()
            if not ln.strip().startswith("#") and ln.strip()
        )
        assert has_https, (
            "showreel_url.txt.template does not contain an example HTTPS URL line"
        )

    # ------------------------------------------------------------------
    # 3. scripts/verify_showreel.py
    # ------------------------------------------------------------------

    def test_verify_showreel_script_exists(self):
        """scripts/verify_showreel.py must exist."""
        path = _repo_root() / "scripts" / "verify_showreel.py"
        assert path.exists(), f"scripts/verify_showreel.py not found at {path}"
        assert path.is_file(), f"{path} is not a regular file"

    def test_verify_showreel_script_is_valid_python(self):
        """scripts/verify_showreel.py must be syntactically valid Python."""
        path = _repo_root() / "scripts" / "verify_showreel.py"
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"scripts/verify_showreel.py failed syntax check:\n{result.stderr}"
        )

    def test_verify_showreel_exits_zero_in_pending_mode(self):
        """scripts/verify_showreel.py must exit 0 (informational) while PENDING."""
        script = _repo_root() / "scripts" / "verify_showreel.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(_repo_root()),
        )
        assert result.returncode == 0, (
            f"verify_showreel.py exited {result.returncode} in default (non-strict) mode.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_verify_showreel_pending_output_starts_with_pending(self):
        """verify_showreel.py must output a line starting with 'PENDING' while PENDING."""
        script = _repo_root() / "scripts" / "verify_showreel.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(_repo_root()),
        )
        first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        assert first_line.startswith("PENDING"), (
            f"Expected first output line to start with 'PENDING' but got: {first_line!r}"
        )

    def test_verify_showreel_json_mode_returns_valid_json(self):
        """verify_showreel.py --json must emit a valid JSON object."""
        script = _repo_root() / "scripts" / "verify_showreel.py"
        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            capture_output=True,
            text=True,
            cwd=str(_repo_root()),
        )
        assert result.returncode == 0, (
            f"verify_showreel.py --json exited {result.returncode}\n"
            f"stderr: {result.stderr}"
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"verify_showreel.py --json did not produce valid JSON: {exc}\n"
                f"stdout: {result.stdout!r}"
            ) from exc
        assert isinstance(data, dict), "verify_showreel.py --json output is not a JSON object"
        assert "status" in data, "JSON output missing 'status' key"

    def test_verify_showreel_json_mode_status_is_pending(self):
        """verify_showreel.py --json must report status=PENDING while no recording is present."""
        script = _repo_root() / "scripts" / "verify_showreel.py"
        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            capture_output=True,
            text=True,
            cwd=str(_repo_root()),
        )
        data = json.loads(result.stdout)
        assert data["status"] == "PENDING", (
            f"Expected JSON status 'PENDING' but got '{data['status']}'"
        )

    # ------------------------------------------------------------------
    # 4. Top-level README.md
    # ------------------------------------------------------------------

    def test_top_level_readme_mentions_showreel(self):
        """Top-level README.md must reference the showreel or demonstration video."""
        path = _repo_root() / "README.md"
        assert path.exists(), f"Top-level README.md not found at {path}"
        content = path.read_text(encoding="utf-8")
        has_mention = (
            "Showreel" in content
            or "showreel" in content
            or "Demonstration Video" in content
            or "demonstration video" in content
        )
        assert has_mention, (
            "Top-level README.md does not mention the showreel or Demonstration Video"
        )

    def test_top_level_readme_points_to_showreel_md(self):
        """Top-level README.md must link to presentation/showreel.md."""
        path = _repo_root() / "README.md"
        content = path.read_text(encoding="utf-8")
        assert "presentation/showreel.md" in content, (
            "Top-level README.md does not reference presentation/showreel.md"
        )

    # ------------------------------------------------------------------
    # 5. presentation/README.md
    # ------------------------------------------------------------------

    def test_presentation_readme_has_demonstration_video_section(self):
        """presentation/README.md must contain a Demonstration Video section."""
        path = _repo_root() / "presentation" / "README.md"
        assert path.exists(), f"presentation/README.md not found at {path}"
        content = path.read_text(encoding="utf-8")
        assert "Demonstration Video" in content, (
            "presentation/README.md does not contain a 'Demonstration Video' section"
        )

    def test_presentation_readme_contents_table_includes_showreel_md(self):
        """presentation/README.md package-contents table must list showreel.md."""
        path = _repo_root() / "presentation" / "README.md"
        content = path.read_text(encoding="utf-8")
        assert "showreel.md" in content, (
            "presentation/README.md does not list showreel.md in its contents table"
        )

    def test_presentation_readme_contents_table_includes_showreel_status(self):
        """presentation/README.md package-contents table must list SHOWREEL_STATUS.md."""
        path = _repo_root() / "presentation" / "README.md"
        content = path.read_text(encoding="utf-8")
        assert "SHOWREEL_STATUS.md" in content, (
            "presentation/README.md does not list SHOWREEL_STATUS.md in its contents table"
        )
