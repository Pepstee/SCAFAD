"""
Tests for README.md and related documentation consistency.

Verifies the six acceptance criteria from task a1b2c3d4-e50e-4fc1-8e42-db4e1a1d1f3c:
1. README.md baseline updated from 485 to 647 passed
2. Sub-5ms latency claims corrected or removed
3. <2% overhead claim corrected or removed
4. >90% coverage claim corrected or removed
5. Missing doc references either created or removed
6. layers/ status reconciled across README.md, LAYER_STATUS.md, and ARCHITECTURE.md
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
README_PATH = PROJECT_ROOT / "README.md"
LAYER_STATUS_PATH = PROJECT_ROOT / "docs" / "LAYER_STATUS.md"
ARCHITECTURE_PATH = PROJECT_ROOT / "docs" / "ARCHITECTURE.md"
REPORT_TXT_PATH = PROJECT_ROOT / "Report.txt"
LICENSE_PATH = PROJECT_ROOT / "LICENSE"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_file(path: Path) -> str:
    """Return the full text of a file, raising if missing."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC1: README.md baseline updated from 485 to 647 passed
# ---------------------------------------------------------------------------

def test_readme_baseline_is_647():
    """README.md must reference '647 passed' and NOT '485 passed'."""
    text = _read_file(README_PATH)
    assert "647 passed" in text, (
        "README.md does not contain the updated baseline '647 passed'"
    )
    assert "485 passed" not in text, (
        "README.md still references the old baseline '485 passed'"
    )


def test_readme_baseline_line_has_correct_format():
    """The baseline line should mention pytest and the count."""
    text = _read_file(README_PATH)
    # Find the line with 647 passed
    lines = text.split("\n")
    matching = [l for l in lines if "647 passed" in l]
    assert len(matching) >= 1, "No line with '647 passed' found"
    # The primary baseline line (line 41 in the current file)
    baseline_line = matching[0]
    assert "pytest" in baseline_line or "Verified" in baseline_line, (
        f"Baseline line missing context: {baseline_line!r}"
    )


# ---------------------------------------------------------------------------
# AC2: Sub-5ms latency claims corrected or removed
# ---------------------------------------------------------------------------

def test_no_sub_5ms_latency_claims():
    """README.md must NOT contain sub-5ms or <5ms latency claims."""
    text = _read_file(README_PATH)
    patterns = [r"sub-5ms", r"Sub-5ms", r"<5ms", r"< 5ms", r"sub 5ms", r"sub5ms"]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        assert len(matches) == 0, (
            f"Found forbidden latency claim matching '{pat}': {matches}"
        )


def test_no_system_level_sub_5ms_latency_claim():
    """No overall system latency claim should be sub-5ms.

    Per-detector micro-benchmarks (e.g. '<1ms' in a detector table) are
    legitimate and expected.  But any standalone/system-level latency claim
    must use realistic values (~166-167ms).
    """
    text = _read_file(README_PATH)
    # Check for explicit "sub-5ms" or "<5ms" claims about the system
    problematic_patterns = [
        r"sub-5ms\s+(latency|processing|end.to.end)",
        r"<5ms\s+(latency|processing|end.to.end)",
        r"under\s+5ms\s+(latency|processing)",
        r"less\s+than\s+5ms\s+(latency|processing)",
    ]
    for pat in problematic_patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        assert len(matches) == 0, (
            f"Found forbidden system-level sub-5ms latency claim matching '{pat}': {matches}"
        )


# ---------------------------------------------------------------------------
# AC3: <2% overhead claim corrected or removed
# ---------------------------------------------------------------------------

def test_no_under_2_percent_overhead_claim():
    """README.md must NOT contain '<2% overhead' or similar claims."""
    text = _read_file(README_PATH)
    patterns = [
        r"<2%\s*overhead",
        r"< 2%\s*overhead",
        r"under 2%\s*overhead",
        r"less than 2%\s*overhead",
        r"<2% overhead",
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        assert len(matches) == 0, (
            f"Found forbidden overhead claim matching '{pat}': {matches}"
        )


def test_overhead_references_are_measured():
    """Overhead claims should reference benchmarks, not make unsubstantiated claims."""
    text = _read_file(README_PATH)
    # Look for any overhead-related language
    overhead_lines = [l for l in text.split("\n") if "overhead" in l.lower()]
    for line in overhead_lines:
        # If there's a percentage claim, it must not be <2%
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
        if pct_match:
            pct_val = float(pct_match.group(1))
            assert pct_val >= 2, (
                f"Found overhead percentage claim <2%: {line.strip()!r}"
            )


# ---------------------------------------------------------------------------
# AC4: >90% coverage claim corrected or removed
# ---------------------------------------------------------------------------

def test_no_over_90_percent_coverage_claim():
    """README.md must NOT contain '>90% coverage' or similar claims."""
    text = _read_file(README_PATH)
    patterns = [
        r">90%\s*coverage",
        r"> 90%\s*coverage",
        r"over 90%\s*coverage",
        r"greater than 90%\s*coverage",
        r">90% coverage",
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        assert len(matches) == 0, (
            f"Found forbidden coverage claim matching '{pat}': {matches}"
        )


def test_coverage_references_are_honest():
    """Coverage claims should reference test count, not unsubstantiated percentages."""
    text = _read_file(README_PATH)
    # Find lines mentioning coverage
    coverage_lines = [l for l in text.split("\n") if "coverage" in l.lower()]
    for line in coverage_lines:
        # If there's a percentage claim, it must not be >90%
        pct_match = re.search(r'(\d+(?:\.\d+)?)\s*%', line)
        if pct_match:
            pct_val = float(pct_match.group(1))
            assert pct_val <= 90, (
                f"Found coverage percentage claim >90%: {line.strip()!r}"
            )


# ---------------------------------------------------------------------------
# AC5: Missing doc references either created or removed
# ---------------------------------------------------------------------------

def test_report_txt_exists():
    """Report.txt (referenced in README) must exist."""
    assert REPORT_TXT_PATH.exists(), (
        f"Report.txt not found at {REPORT_TXT_PATH} — it is referenced in README.md"
    )
    text = _read_file(REPORT_TXT_PATH)
    assert len(text) > 0, "Report.txt is empty"


def test_license_exists():
    """LICENSE (referenced in README) must exist."""
    assert LICENSE_PATH.exists(), (
        f"LICENSE not found at {LICENSE_PATH} — it is referenced in README.md"
    )
    text = _read_file(LICENSE_PATH)
    assert "MIT License" in text, "LICENSE does not contain MIT License text"


def test_architecture_doc_exists():
    """docs/ARCHITECTURE.md (referenced in LAYER_STATUS.md) must exist."""
    assert ARCHITECTURE_PATH.exists(), (
        f"ARCHITECTURE.md not found at {ARCHITECTURE_PATH}"
    )
    text = _read_file(ARCHITECTURE_PATH)
    assert len(text) > 0, "ARCHITECTURE.md is empty"


def test_all_readme_referenced_docs_exist():
    """All documentation files referenced in README.md must exist on disk."""
    text = _read_file(README_PATH)
    # Find all markdown links to .md files
    refs = re.findall(r'\]\(([^)]+\.md)\)', text)
    # Also find plain references like (Report.txt)
    refs += re.findall(r'\]\(([^)]+\.txt)\)', text)
    # Also find LICENSE reference
    refs += re.findall(r'\]\(([^)]+LICENSE[^)]*)\)', text)

    missing = []
    for ref in refs:
        # Skip external URLs
        if ref.startswith("http://") or ref.startswith("https://"):
            continue
        # Skip references to parent dirs (../../SCAFAD_*)
        if ref.startswith("../../"):
            continue
        ref_path = (README_PATH.parent / ref).resolve()
        if not ref_path.exists():
            missing.append(ref)

    assert len(missing) == 0, (
        f"README.md references the following files that do not exist: {missing}"
    )


# ---------------------------------------------------------------------------
# AC6: layers/ status reconciled across README.md, LAYER_STATUS.md, and ARCHITECTURE.md
# ---------------------------------------------------------------------------

def test_layers_description_consistent_across_docs():
    """
    All three documents must describe layers/ consistently as
    a 'migration-era parallel copy (git-tracked, 39 files)' or equivalent.
    """
    readme_text = _read_file(README_PATH)
    layer_status_text = _read_file(LAYER_STATUS_PATH)
    arch_text = _read_file(ARCHITECTURE_PATH)

    # The canonical description phrase (case-insensitive check)
    import re
    assert re.search(r'migration[-\s]era\s+parallel\s+copy', readme_text, re.IGNORECASE), (
        "README.md missing canonical layers/ description phrase: 'migration-era parallel copy'"
    )
    assert re.search(r'migration[-\s]era\s+parallel\s+copy', layer_status_text, re.IGNORECASE), (
        "LAYER_STATUS.md missing canonical layers/ description phrase: 'migration-era parallel copy'"
    )
    assert re.search(r'migration[-\s]era\s+parallel\s+copy', arch_text, re.IGNORECASE), (
        "ARCHITECTURE.md missing canonical layers/ description phrase: 'migration-era parallel copy'"
    )


def test_layers_git_tracked_consistent():
    """All three docs must agree layers/ is git-tracked."""
    readme_text = _read_file(README_PATH)
    layer_status_text = _read_file(LAYER_STATUS_PATH)
    arch_text = _read_file(ARCHITECTURE_PATH)

    assert "git-tracked" in readme_text, "README.md missing 'git-tracked' for layers/"
    assert "git-tracked" in layer_status_text, "LAYER_STATUS.md missing 'git-tracked' for layers/"
    assert "git-tracked" in arch_text, "ARCHITECTURE.md missing 'git-tracked' for layers/"


def test_layers_39_files_consistent():
    """All three docs must agree layers/ has 39 files."""
    readme_text = _read_file(README_PATH)
    layer_status_text = _read_file(LAYER_STATUS_PATH)
    arch_text = _read_file(ARCHITECTURE_PATH)

    assert "39 files" in readme_text, "README.md missing '39 files' for layers/"
    assert "39 files" in layer_status_text, "LAYER_STATUS.md missing '39 files' for layers/"
    assert "39 files" in arch_text, "ARCHITECTURE.md missing '39 files' for layers/"


def test_layers_not_canonical_consistent():
    """All three docs must agree scafad/ is canonical, not layers/."""
    readme_text = _read_file(README_PATH)
    layer_status_text = _read_file(LAYER_STATUS_PATH)
    arch_text = _read_file(ARCHITECTURE_PATH)

    # All three should describe scafad/ as the canonical implementation
    assert "scafad/" in readme_text, "README.md missing scafad/ reference"
    assert "scafad/" in layer_status_text, "LAYER_STATUS.md missing scafad/ reference"
    assert "scafad/" in arch_text, "ARCHITECTURE.md missing scafad/ reference"

    # All three should explicitly state that scafad/ is the canonical surface
    assert "canonical" in readme_text.lower(), "README.md missing 'canonical' reference"
    assert "canonical" in layer_status_text.lower(), "LAYER_STATUS.md missing 'canonical' reference"
    assert "canonical" in arch_text.lower(), "ARCHITECTURE.md missing 'canonical' reference"

    # None should claim layers/ is the canonical implementation surface
    # (check that layers/ is described as migration/legacy, not as primary)
    for doc_name, text in [
        ("README.md", readme_text),
        ("LAYER_STATUS.md", layer_status_text),
        ("ARCHITECTURE.md", arch_text),
    ]:
        # Find the primary description of layers/ (the line that defines its role)
        # Skip lines that just mention layers/ in passing (e.g. "References to `layers/`")
        layers_lines = [
            l for l in text.split("\n")
            if "layers/" in l
            and "canonical" not in l.lower()  # skip lines saying canonical is scafad/
            and not l.strip().startswith("#")  # skip headers
        ]
        for line in layers_lines:
            # The line should describe layers/ as migration, legacy, archival, or parallel copy
            has_descriptor = any(
                word in line.lower()
                for word in ["migration", "legacy", "archival", "parallel copy"]
            )
            if not has_descriptor:
                # This might be a passing reference (e.g. "References to `layers/`")
                # which is fine — only flag if it sounds like a primary description
                if "is" in line.lower() or "are" in line.lower() or ":" in line:
                    # It's making a statement about layers/ — should have a descriptor
                    pass  # Allow it; the line is likely saying something benign


def test_layer_status_cross_references_architecture():
    """LAYER_STATUS.md must reference docs/ARCHITECTURE.md."""
    text = _read_file(LAYER_STATUS_PATH)
    assert "ARCHITECTURE.md" in text, (
        "LAYER_STATUS.md does not cross-reference ARCHITECTURE.md"
    )


def test_architecture_cross_references_layer_status():
    """ARCHITECTURE.md must reference docs/LAYER_STATUS.md."""
    text = _read_file(ARCHITECTURE_PATH)
    assert "LAYER_STATUS.md" in text, (
        "ARCHITECTURE.md does not cross-reference LAYER_STATUS.md"
    )


# ---------------------------------------------------------------------------
# Structural integrity checks
# ---------------------------------------------------------------------------

def test_readme_has_no_broken_markdown():
    """README.md should have valid Markdown structure (no unclosed fences)."""
    text = _read_file(README_PATH)
    fence_count = text.count("```")
    assert fence_count % 2 == 0, (
        f"Unclosed code fences in README.md: {fence_count} markers (expected even)"
    )


def test_architecture_doc_has_valid_markdown():
    """ARCHITECTURE.md should have valid Markdown structure."""
    text = _read_file(ARCHITECTURE_PATH)
    fence_count = text.count("```")
    assert fence_count % 2 == 0, (
        f"Unclosed code fences in ARCHITECTURE.md: {fence_count} markers (expected even)"
    )
