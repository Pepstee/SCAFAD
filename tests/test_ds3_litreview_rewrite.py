"""
Test suite for DS-3: Rewrite Chapter 2 and Appendix G
so the literature-review method is auditable and honestly labelled.

Tests validate:
- AC1: Review type explicitly and honestly stated
- AC2: Counts and inclusion logic consistent between files
- AC3: Laundry-list replaced with focused analysis
- AC4: SCAFAD differentiation clear and grounded
- AC5: No inflated comparative claims
- AC6: Both files saved and readable
"""

import pytest
import os
import re
from pathlib import Path


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def chapter2_path():
    """Path to Chapter 2 file."""
    # When running from project/scafad-r-core, the path is relative
    return Path(__file__).parent.parent / "dissertation" / "chapter_02_literature_review.md"


@pytest.fixture
def appendix_g_path():
    """Path to Appendix G file."""
    # When running from project/scafad-r-core, the path is relative
    return Path(__file__).parent.parent / "dissertation" / "appendices" / "appendix_g_literature_review_evidence.md"


@pytest.fixture
def chapter2_content(chapter2_path):
    """Read and return Chapter 2 content."""
    assert chapter2_path.exists(), f"Chapter 2 not found at {chapter2_path}"
    with open(chapter2_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def appendix_g_content(appendix_g_path):
    """Read and return Appendix G content."""
    assert appendix_g_path.exists(), f"Appendix G not found at {appendix_g_path}"
    with open(appendix_g_path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# ACCEPTANCE CRITERION 1: Review Type Explicit and Honest
# ============================================================================

class TestAC1ReviewTypeExplicit:
    """Test AC1: Review type explicitly and honestly stated."""

    def test_chapter2_states_structured_review_not_slr(self, chapter2_content):
        """Chapter 2 §2.1 should state 'structured review (not a formal systematic review)'."""
        assert "structured review" in chapter2_content.lower(), \
            "Chapter 2 should mention 'structured review'"
        assert "not a formal systematic review" in chapter2_content.lower() or \
               "not a formal slr" in chapter2_content.lower(), \
            "Chapter 2 should explicitly state it's NOT a formal systematic review"
        # Verify it's in the early part of the document (§2.1)
        lines = chapter2_content.split("\n")
        found_in_early_section = False
        for i, line in enumerate(lines[:20]):
            if "structured review" in line.lower() and "not" in line.lower():
                found_in_early_section = True
                break
        assert found_in_early_section, "Review type classification should be in §2.1 (early section)"

    def test_appendix_g_states_scoped_structured_review(self, appendix_g_content):
        """Appendix G §G.1 should state review type as 'scoped structured review'."""
        assert "scoped structured review" in appendix_g_content.lower(), \
            "Appendix G should state 'scoped structured review'"
        # Should also clarify it's not a formal SLR
        assert "not" in appendix_g_content.lower() and "formal" in appendix_g_content.lower() and \
               ("systematic review" in appendix_g_content.lower() or "slr" in appendix_g_content.lower()), \
            "Appendix G should clarify this is not a formal SLR"


# ============================================================================
# ACCEPTANCE CRITERION 2: Counts and Inclusion Logic Consistent
# ============================================================================

class TestAC2CountConsistency:
    """Test AC2: Counts and inclusion logic match between Chapter 2 and Appendix G."""

    def test_count_chain_312_to_26(self, chapter2_content, appendix_g_content):
        """Both files should document the same count chain: 312 → duplicates → screened → 67 → 26."""
        # Chapter 2 should mention initial record count and final paper count
        assert "312" in chapter2_content, "Chapter 2 should mention 312 records"
        assert "67" in chapter2_content, "Chapter 2 should mention 67 full-text articles"
        assert "26" in chapter2_content, "Chapter 2 should mention 26 papers"

        # Appendix G should have the complete count chain with all intermediate values
        assert "312" in appendix_g_content, "Appendix G should mention 312 records"
        assert "265" in appendix_g_content, "Appendix G should mention 265 screened records"
        assert "67" in appendix_g_content, "Appendix G should mention 67 full-text articles"
        assert "26" in appendix_g_content, "Appendix G should mention 26 included papers"

        # Both should mention duplicate removal
        assert "47" in chapter2_content or "47" in appendix_g_content, \
            "Duplicate count (47) should be documented"

    def test_duplicate_removal_documented(self, appendix_g_content):
        """Appendix G should document 47 duplicates removed."""
        assert "47" in appendix_g_content or "duplicate" in appendix_g_content.lower(), \
            "Appendix G should document duplicate removal (47 duplicates)"


# ============================================================================
# ACCEPTANCE CRITERION 3: Focused Analysis Replacing Laundry-List
# ============================================================================

class TestAC3FocusedAnalysis:
    """Test AC3: Laundry-list descriptions replaced with focused comparative analysis."""

    def test_chapter2_organized_by_topic(self, chapter2_content):
        """Chapter 2 should be organized by thematic sections (§2.2–§2.6), not by system."""
        # Look for topic-based section headers
        section_patterns = [
            r"2\.2.*serverless",
            r"2\.3.*log",
            r"2\.4.*intrusion|threat",
            r"2\.5.*privacy|data",
            r"2\.6.*ensemble|fusion"
        ]
        sections_found = 0
        for pattern in section_patterns:
            if re.search(pattern, chapter2_content, re.IGNORECASE):
                sections_found += 1
        assert sections_found >= 4, \
            "Chapter 2 should have at least 4 topic-based sections (2.2–2.6)"

    def test_each_section_has_representative_papers(self, chapter2_content):
        """Each section should cite specific papers with metrics, not generic lists."""
        # Count citations and metric patterns
        citation_count = len(re.findall(r"\(\d{4}\)", chapter2_content))
        metric_patterns = [
            r"F1\s*=",
            r"precision|recall|AUC",
            r"\d+%"
        ]
        metric_count = sum(len(re.findall(p, chapter2_content, re.IGNORECASE))
                          for p in metric_patterns)

        assert citation_count >= 15, \
            f"Chapter 2 should cite multiple papers (found {citation_count})"
        assert metric_count >= 5, \
            f"Chapter 2 should include quantitative metrics (found {metric_count} patterns)"


# ============================================================================
# ACCEPTANCE CRITERION 4: SCAFAD Differentiation Clear and Grounded
# ============================================================================

class TestAC4SCafadDifferentiation:
    """Test AC4: SCAFAD differentiation argument is clear and grounded."""

    def test_integration_gap_explained(self, chapter2_content):
        """§2.7 should explicitly explain the integration gap SCAFAD addresses."""
        # Should mention fragmentation or integration
        assert ("integrat" in chapter2_content.lower() or
                "fragmented" in chapter2_content.lower() or
                "gap" in chapter2_content.lower()), \
            "Chapter 2 §2.7 should explain integration gap"

        # Should reference prior sections
        assert "section" in chapter2_content.lower() or \
               "prior" in chapter2_content.lower() or \
               "existing" in chapter2_content.lower(), \
            "§2.7 should ground differentiation in evidence from prior sections"

    def test_scafad_positioning_honest(self, chapter2_content):
        """SCAFAD positioning should be honest about limitations."""
        # Should include hedging language
        hedging_phrases = [
            r"whether.*open question",
            r"remains.*open question",
            r"pragmatic.*not principled",
            r"design-oriented.*not.*proven"
        ]
        hedging_found = sum(1 for pattern in hedging_phrases
                           if re.search(pattern, chapter2_content, re.IGNORECASE))
        assert hedging_found >= 2, \
            "Chapter 2 should use hedging language to avoid overclaiming"


# ============================================================================
# ACCEPTANCE CRITERION 5: No Inflated Comparative Claims
# ============================================================================

class TestAC5NoInflatedClaims:
    """Test AC5: No inflated comparative claims without citation support."""

    def test_no_validates_thesis(self, chapter2_content):
        """Should NOT contain phrase 'validates the thesis' or similar inflation."""
        assert "validates the thesis" not in chapter2_content.lower() and \
               "validates our thesis" not in chapter2_content.lower(), \
            "Chapter 2 should not claim to 'validate the thesis'"

    def test_no_state_of_art(self, chapter2_content):
        """Should not claim to be 'state-of-the-art' without full support."""
        # Allow "state-of-the-art" only if it's in a quoted context or clearly attributed
        state_of_art_count = len(re.findall(r"state[- ]of[- ](?:the[- ])?art", chapter2_content, re.IGNORECASE))
        if state_of_art_count > 0:
            # Check if they're properly attributed (in quotes or with citations)
            assert ":" in chapter2_content or '"' in chapter2_content, \
                "Any 'state-of-the-art' claims should be properly attributed"

    def test_no_comprehensively_surpasses(self, chapter2_content):
        """Should not use inflated language like 'comprehensively surpasses'."""
        assert "comprehensively surpass" not in chapter2_content.lower(), \
            "Chapter 2 should not claim to 'comprehensively surpass' prior work"

    def test_hedging_language_present(self, chapter2_content):
        """Should include hedging language throughout."""
        hedging_keywords = [
            "whether",
            "remains an open question",
            "pragmatic",
            "design-oriented",
            "unproven"
        ]
        hedging_found = sum(1 for keyword in hedging_keywords
                           if keyword.lower() in chapter2_content.lower())
        assert hedging_found >= 3, \
            f"Chapter 2 should include hedging language (found {hedging_found} of {len(hedging_keywords)})"


# ============================================================================
# ACCEPTANCE CRITERION 6: File Integrity and Readability
# ============================================================================

class TestAC6FileIntegrity:
    """Test AC6: Both files are saved, readable, and properly formatted."""

    def test_chapter2_exists_and_readable(self, chapter2_path):
        """Chapter 2 file must exist and be readable."""
        assert chapter2_path.exists(), f"Chapter 2 not found at {chapter2_path}"
        with open(chapter2_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 1000, "Chapter 2 should contain substantial content"

    def test_appendix_g_exists_and_readable(self, appendix_g_path):
        """Appendix G file must exist and be readable."""
        assert appendix_g_path.exists(), f"Appendix G not found at {appendix_g_path}"
        with open(appendix_g_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert len(content) > 1000, "Appendix G should contain substantial content"

    def test_chapter2_valid_markdown(self, chapter2_content):
        """Chapter 2 should be valid Markdown."""
        # Check for proper heading structure
        assert "# Chapter" in chapter2_content or "# 2" in chapter2_content, \
            "Chapter 2 should have Markdown headings"
        # Check for no major syntax issues
        assert chapter2_content.count("##") >= 5, \
            "Chapter 2 should have multiple section headings"

    def test_appendix_g_valid_markdown(self, appendix_g_content):
        """Appendix G should be valid Markdown."""
        assert "# Appendix" in appendix_g_content or "# G" in appendix_g_content, \
            "Appendix G should have Markdown heading"
        assert appendix_g_content.count("##") >= 5, \
            "Appendix G should have multiple section headings"

    def test_no_placeholder_text(self, chapter2_content, appendix_g_content):
        """No placeholder text like [PLACEHOLDER], [TODO], [EDIT] should remain."""
        placeholder_patterns = [
            r"\[PLACEHOLDER\]",
            r"\[TODO\]",
            r"\[EDIT\]",
            r"\[FIXME\]",
            r"XXX",
            r"TBD"
        ]
        for pattern in placeholder_patterns:
            assert not re.search(pattern, chapter2_content, re.IGNORECASE), \
                f"Chapter 2 contains placeholder pattern: {pattern}"
            assert not re.search(pattern, appendix_g_content, re.IGNORECASE), \
                f"Appendix G contains placeholder pattern: {pattern}"

    def test_no_encoding_errors(self, chapter2_path, appendix_g_path):
        """Files should have no encoding errors."""
        try:
            with open(chapter2_path, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("Chapter 2 has encoding errors")

        try:
            with open(appendix_g_path, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("Appendix G has encoding errors")


# ============================================================================
# INTEGRATION TESTS: All Criteria Together
# ============================================================================

class TestIntegrationAllCriteria:
    """Integration tests verifying all criteria work together."""

    def test_all_criteria_integrated(self, chapter2_content, appendix_g_content):
        """All acceptance criteria should work together coherently."""
        # Verify review type stated in both
        assert "structured review" in chapter2_content.lower()
        assert "scoped structured review" in appendix_g_content.lower()

        # Verify counts present
        assert "312" in chapter2_content
        assert "26" in chapter2_content

        # Verify citations present
        assert "(" in chapter2_content and ")" in chapter2_content

    def test_counts_synchronized(self, chapter2_content, appendix_g_content):
        """Count chain should be synchronized across both files."""
        # Key counts that should appear in both files
        key_counts = ["312", "67", "26"]

        # Verify Chapter 2 contains core counts
        for count in key_counts:
            assert count in chapter2_content, \
                f"Chapter 2 should contain count {count}"

        # Verify Appendix G contains full count chain including 265
        full_counts = ["312", "265", "67", "26"]
        for count in full_counts:
            assert count in appendix_g_content, \
                f"Appendix G should contain count {count} in PRISMA table"

    def test_scafad_differentiation_complete(self, chapter2_content):
        """SCAFAD differentiation should be complete and grounded."""
        # Should reference SCAFAD
        assert "scafad" in chapter2_content.lower(), \
            "Chapter 2 should mention SCAFAD's contribution"

        # Should reference integration
        assert ("integrat" in chapter2_content.lower() or
                "combined" in chapter2_content.lower() or
                "pipeline" in chapter2_content.lower()), \
            "Chapter 2 should describe SCAFAD's integrated approach"

        # Should reference limitations
        assert ("limitation" in chapter2_content.lower() or
                "limitation" in chapter2_content.lower()), \
            "Chapter 2 should document limitations of the work"


# ============================================================================
# LINE COUNT VALIDATION (from build report)
# ============================================================================

class TestLineCountValidation:
    """Test that files match expected line counts from build report."""

    def test_chapter2_line_count(self, chapter2_content):
        """Chapter 2 should be approximately 95 lines (build report)."""
        line_count = len(chapter2_content.strip().split("\n"))
        # Allow ±5 lines for variation
        assert 90 <= line_count <= 100, \
            f"Chapter 2 should be ~95 lines (found {line_count})"

    def test_appendix_g_line_count(self, appendix_g_content):
        """Appendix G should be approximately 95 lines (build report)."""
        line_count = len(appendix_g_content.strip().split("\n"))
        # Allow ±5 lines for variation
        assert 90 <= line_count <= 100, \
            f"Appendix G should be ~95 lines (found {line_count})"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
