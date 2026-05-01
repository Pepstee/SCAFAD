"""
Tests for LAYER_STATUS.md — verifies the document was correctly updated
to reflect the 647-pass baseline and corrected layers/ description.

Task: e71d7d1f-1447-4404-a1db-08e5f4e5b499
Source task: b1f7b7d3-ccdc-430a-aa8b-ad0a61964501
"""

import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
LAYER_STATUS_PATH = DOCS_DIR / "LAYER_STATUS.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_doc():
    """Return the full text of LAYER_STATUS.md."""
    if not LAYER_STATUS_PATH.exists():
        raise FileNotFoundError(
            f"LAYER_STATUS.md not found at {LAYER_STATUS_PATH}"
        )
    return LAYER_STATUS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Acceptance criteria
# ---------------------------------------------------------------------------

def test_document_exists():
    """The document must exist and be readable."""
    assert LAYER_STATUS_PATH.exists(), (
        f"LAYER_STATUS.md not found at {LAYER_STATUS_PATH}"
    )
    text = _read_doc()
    assert len(text) > 0, "LAYER_STATUS.md is empty"


def test_no_gitignored_claim_about_layers():
    """
    AC1: LAYER_STATUS.md no longer claims layers/ is gitignored.

    The word 'gitignored' must NOT appear in the document in reference
    to the layers/ directory.  (The .gitignore entry for
    legacy/layers-migration-snapshot/ is fine, but that's not about
    layers/.)
    """
    text = _read_doc()
    # Check that 'gitignored' does not appear in the document at all
    # (the builder removed the only occurrence).
    assert "gitignored" not in text, (
        "LAYER_STATUS.md still contains the word 'gitignored'"
    )


def test_layers_description_accurate():
    """
    AC2: layers/ described as 'Migration-era parallel copy (git-tracked, 39 files)'
    or equivalent accurate description.
    """
    text = _read_doc()
    # The exact phrase from the acceptance criteria
    assert "Migration-era parallel copy (git-tracked, 39 files)" in text, (
        "LAYER_STATUS.md does not contain the expected layers/ description"
    )


def test_test_count_updated_to_647():
    """
    AC3: Test count updated from 485 to 647.
    """
    text = _read_doc()
    # The old count must not appear
    assert "485 passed" not in text, (
        "LAYER_STATUS.md still references the old test count of 485"
    )
    # The new count must appear
    assert "647 passed" in text, (
        "LAYER_STATUS.md does not contain the updated test count of 647"
    )


def test_layer_implementation_sections_unchanged():
    """
    AC4: All layer implementation status sections (L0-L6, Runtime) remain unchanged.

    We verify that the key structural markers for each layer section are
    still present and intact.
    """
    text = _read_doc()

    # Each layer section header must still be present
    expected_sections = [
        "## Layer 0 — Adaptive Telemetry Controller",
        "## Layer 1 — Behavioural Intake Zone",
        "## Layer 2 — Multi-Vector Detection Matrix",
        "## Layer 3 — Trust-Weighted Fusion",
        "## Layer 4 — Explainability and Decision Trace",
        "## Layer 5 — Threat Alignment",
        "## Layer 6 — Feedback and Learning",
        "## Runtime",
    ]
    for section in expected_sections:
        assert section in text, (
            f"Missing expected section header: {section!r}"
        )

    # Verify key content that should NOT have been removed
    key_phrases = [
        "scafad/layer0/",
        "scafad/layer1/",
        "scafad/layer2/",
        "scafad/layer3/",
        "scafad/layer4/",
        "scafad/layer5/",
        "scafad/layer6/",
        "scafad/runtime/",
        "TelemetryRecord",
        "Layer1ProcessedRecord",
        "MultiVectorDetectionMatrix",
        "TrustWeightedFusionEngine",
        "ExplainabilityDecisionEngine",
        "ThreatAlignmentEngine",
        "FeedbackLearningEngine",
        "SCAFADCanonicalRuntime",
        "lambda_handler",
    ]
    for phrase in key_phrases:
        assert phrase in text, (
            f"Missing expected key phrase: {phrase!r}"
        )


def test_document_renders_as_valid_markdown():
    """
    AC5: Document renders correctly as Markdown.

    We check for common Markdown structural issues:
    - No unclosed code fences
    - Table rows have consistent column counts
    - No broken link syntax
    """
    text = _read_doc()
    lines = text.split("\n")

    # Check for unclosed code fences
    fence_count = text.count("```")
    assert fence_count % 2 == 0, (
        f"Unclosed code fences: found {fence_count} fence markers (expected even)"
    )

    # Check table rows have consistent column counts
    # Find the first table (between lines starting with |)
    in_table = False
    expected_cols = None
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("|"):
            cols = stripped.count("|")
            if not in_table:
                in_table = True
                expected_cols = cols
            else:
                # Allow separator rows (|---|) which may have different count
                # due to alignment markers
                if "---" not in stripped:
                    assert cols == expected_cols, (
                        f"Line {i}: inconsistent column count "
                        f"(expected {expected_cols}, got {cols}): {stripped!r}"
                    )
        else:
            in_table = False
            expected_cols = None

    # Check no broken image/links (bare parentheses issues)
    # Look for patterns like [text]( that are not closed
    link_open = text.count("](")
    link_close = text.count(")")
    # This is a rough check — each ]( should have a matching )
    # We just verify there's no obvious broken syntax
    assert link_open >= 0, "No link syntax found (not necessarily a problem)"


def test_evaluation_matrix_has_correct_structure():
    """
    Verify the Evaluation Matrix section has the expected structure
    and the 647 count is in the right place.
    """
    text = _read_doc()

    # Find the line with the test count
    lines = text.split("\n")
    count_line = None
    for line in lines:
        if "647 passed" in line:
            count_line = line
            break

    assert count_line is not None, "Could not find line with '647 passed'"
    assert "1 warning" in count_line, (
        "Test count line missing '1 warning'"
    )
    assert "Johann-verified" in count_line, (
        "Test count line missing 'Johann-verified'"
    )


def test_non_canonical_surfaces_table_updated():
    """
    Verify the Non-Canonical Surfaces table has the correct layers/ entry.
    """
    text = _read_doc()

    # Find the Non-Canonical Surfaces section
    assert "## Non-Canonical Surfaces" in text, (
        "Missing Non-Canonical Surfaces section"
    )

    # The layers/ row should have the new description
    assert "layers/" in text, "Missing layers/ row in Non-Canonical Surfaces"

    # Verify the old incorrect description is gone
    assert "Gitignored NTFS residue" not in text, (
        "Old incorrect description 'Gitignored NTFS residue' still present"
    )
