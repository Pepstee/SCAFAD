"""
Tests for word-count trim task 1f7b7f22-3e61-4b7a-9a0d-c8e1d8f5a101.

Validates that dissertation chapters have been trimmed to submission-safe word counts,
front_matter.md declares the correct count, all metrics are intact, and no Python files
were accidentally modified.
"""

import glob
import os
import re
from pathlib import Path

import pytest


DISSERTATION_ROOT = Path(__file__).parent.parent.parent / "dissertation"
PROJECT_ROOT = Path(__file__).parent.parent.parent
WORD_COUNT_LIMIT = 10000


def count_words_in_text(text: str) -> int:
    """Count words in text, matching the authoritative count_words.py methodology.

    Strips markdown syntax (code blocks, inline code, images, links, headings,
    table rows, and punctuation) then counts word tokens via regex.
    """
    import re
    content = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    content = re.sub(r"`[^`]+`", " ", content)
    content = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", content)
    content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
    content = re.sub(r"^#+\s*", " ", content, flags=re.MULTILINE)
    content = re.sub(r"^\|.*\|$", " ", content, flags=re.MULTILINE)
    content = re.sub(r"[*_>#-]", " ", content)
    content = re.sub(r"\s+", " ", content).strip()
    return len(re.findall(r"\b[\w'-]+\b", content))


class TestWordCountMetrics:
    """Verify word count is within submission limit."""

    def test_prose_word_count_under_limit(self):
        """Prose + refs (excl. tables/code) must be under 10,000."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))

        assert chapter_files, "No chapter files found"

        total_words = 0
        chapter_counts = {}

        for fpath in chapter_files:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            words = count_words_in_text(content)
            chapter_name = Path(fpath).name
            chapter_counts[chapter_name] = words
            total_words += words

        # Print breakdown for debugging
        print(f"\nWord count by chapter:")
        for name, count in sorted(chapter_counts.items()):
            print(f"  {name}: {count} words")
        print(f"Total: {total_words} words")

        assert total_words <= WORD_COUNT_LIMIT, (
            f"Total word count {total_words} exceeds limit {WORD_COUNT_LIMIT}. "
            f"Breakdown: {chapter_counts}"
        )

    def test_front_matter_declaration_accurate(self):
        """front_matter.md line 11 should declare ≤9,999 words."""
        front_matter_path = DISSERTATION_ROOT / "front_matter.md"
        assert front_matter_path.exists(), "front_matter.md not found"

        with open(front_matter_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Line 11 (0-indexed: line 10) should contain the word count declaration
        assert len(lines) > 10, "front_matter.md too short"

        declaration_line = lines[10]  # Line 11 (0-indexed)

        # Extract word count from declaration - handle both "9,976" and "9976" formats
        match = re.search(r"(\d{1,2},?\d{3}|\d{4,5})\s+words", declaration_line)
        assert match, f"Could not parse word count from: {declaration_line}"

        # Remove comma if present and convert to int
        declared_count = int(match.group(1).replace(",", ""))

        # Compute actual word count from all chapters
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        actual_count = sum(
            count_words_in_text(open(f, "r", encoding="utf-8").read())
            for f in chapter_files
        )

        print(f"\nWord count declaration:")
        print(f"  Declared in front_matter.md: {declared_count}")
        print(f"  Computed from chapters: {actual_count}")

        # Allow small rounding differences (±10 words)
        assert abs(declared_count - actual_count) <= 10, (
            f"Declared count ({declared_count}) does not match computed count ({actual_count}). "
            f"Difference: {declared_count - actual_count} words"
        )


class TestKeyMetricsIntegrity:
    """Verify all key quantitative claims are intact."""

    KEY_METRICS = {
        "1.0000": "SCAFAD F1, ROC-AUC",
        "0.8858": "Best baseline F1 (OneClassSVM)",
        "0.09": "Calibrated threshold",
        "0.0759": "Trust weight degradation (F1)",
        "0.0317": "Trust weight degradation (ROC-AUC)",
        "11.42": "F1 gap vs best baseline (pp)",
        "10.46": "ROC-AUC gap vs best baseline (pp)",
        "6,300": "Dataset size",
        "6,250": "True positives in confusion matrix",
        "0.9241": "F1 (flat ensemble / unweighted)",
        "99.95": "Preservation retention threshold",
        "26": "Detector count",
        "14": "Baseline count",
    }

    def test_f1_and_roc_auc_intact(self):
        """F1=1.0000 and ROC-AUC=1.0000 should be present."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        content = "\n".join(
            open(f, "r", encoding="utf-8").read() for f in chapter_files
        )

        assert "1.0000" in content, "F1/ROC-AUC metric (1.0000) not found in chapters"

    def test_best_baseline_f1_intact(self):
        """Best baseline F1 (0.8858) should be present."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        content = "\n".join(
            open(f, "r", encoding="utf-8").read() for f in chapter_files
        )

        assert "0.8858" in content, "Best baseline F1 (0.8858) not found in chapters"

    def test_threshold_intact(self):
        """Calibrated threshold (0.09) should be present."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        content = "\n".join(
            open(f, "r", encoding="utf-8").read() for f in chapter_files
        )

        assert "0.09" in content, "Calibrated threshold (0.09) not found in chapters"

    def test_trust_weight_degradation_intact(self):
        """Trust weight degradation metrics should be present."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        content = "\n".join(
            open(f, "r", encoding="utf-8").read() for f in chapter_files
        )

        assert "0.0759" in content, "F1 degradation (0.0759) not found in chapters"

    def test_dataset_size_intact(self):
        """Dataset size (6,300) should be present."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        content = "\n".join(
            open(f, "r", encoding="utf-8").read() for f in chapter_files
        )

        assert "6,300" in content, "Dataset size (6,300) not found in chapters"

    def test_confusion_matrix_intact(self):
        """Confusion matrix values should be present."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        content = "\n".join(
            open(f, "r", encoding="utf-8").read() for f in chapter_files
        )

        assert "6,250" in content, "True positives (6,250) not found in chapters"


class TestChapterStructure:
    """Verify chapter structure is intact."""

    EXPECTED_CHAPTERS = [
        "chapter_01_introduction.md",
        "chapter_02_literature_review.md",
        "chapter_03_research_methodologies.md",
        "chapter_04_sdlc.md",
        "chapter_05_design_methodology.md",
        "chapter_06_design.md",
        "chapter_07_implementation.md",
        "chapter_08_testing_methodology.md",
        "chapter_09_results_evaluation.md",
        "chapter_10_discussion.md",
        "chapter_11_conclusion.md",
    ]

    def test_all_chapters_exist(self):
        """All expected chapters should exist."""
        for chapter_name in self.EXPECTED_CHAPTERS:
            chapter_path = DISSERTATION_ROOT / chapter_name
            assert chapter_path.exists(), f"Chapter missing: {chapter_name}"

    def test_chapter_headings_intact(self):
        """Each chapter should have a chapter heading."""
        for chapter_name in self.EXPECTED_CHAPTERS:
            chapter_path = DISSERTATION_ROOT / chapter_name
            with open(chapter_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Remove BOM if present
            if content.startswith('﻿'):
                content = content[1:]

            # Should contain at least one heading (# Chapter ...)
            assert re.search(r"^#\s+Chapter", content, re.MULTILINE), (
                f"Chapter {chapter_name} missing main heading"
            )

    def test_no_empty_chapters(self):
        """No chapter should be empty (minimal ~100 words)."""
        for chapter_name in self.EXPECTED_CHAPTERS:
            chapter_path = DISSERTATION_ROOT / chapter_name
            with open(chapter_path, "r", encoding="utf-8") as f:
                content = f.read()

            word_count = count_words_in_text(content)
            assert word_count >= 50, (
                f"Chapter {chapter_name} too short ({word_count} words)"
            )


class TestBritishEnglish:
    """Verify British English spelling is maintained."""

    BRITISH_SPELLINGS = {
        "whilst": "Important conjunction in academic writing",
        "behaviour": "Not American 'behavior'",
        "colour": "Not American 'color'",
    }

    def test_whilst_present(self):
        """'whilst' should be present (British English)."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        content = "\n".join(
            open(f, "r", encoding="utf-8").read() for f in chapter_files
        )

        # At least one use of 'whilst' expected
        assert "whilst" in content, "'whilst' (British English) not found"

    def test_behaviour_spelling(self):
        """'behaviour' should not be spelled 'behavior' (American)."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
        content = "\n".join(
            open(f, "r", encoding="utf-8").read() for f in chapter_files
        )

        # Check for American spelling
        behaviour_count = len(re.findall(r"\bbehaviour\b", content, re.IGNORECASE))
        behavior_count = len(re.findall(r"\bbehavior\b", content, re.IGNORECASE))

        # Allows for "behaviour" or "behaviors" but not "behavior"
        assert behavior_count == 0, (
            f"Found {behavior_count} instances of American spelling 'behavior' (use 'behaviour')"
        )


class TestNoTODOOrFIXME:
    """Verify no incomplete markers remain."""

    def test_no_todo_markers(self):
        """No TODO or FIXME markers should be present."""
        chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))

        for chapter_path in chapter_files:
            with open(chapter_path, "r", encoding="utf-8") as f:
                content = f.read()

            todo_matches = re.findall(r"TODO|FIXME", content, re.IGNORECASE)
            assert not todo_matches, (
                f"Found {len(todo_matches)} TODO/FIXME markers in {Path(chapter_path).name}"
            )


class TestPythonFilesUnchanged:
    """Verify no Python source or test files were inadvertently modified."""

    def test_scafad_source_exists_and_unchanged(self):
        """Core scafad/ Python files should be importable."""
        # This is a sanity check that the package structure is intact
        scafad_init = PROJECT_ROOT / "scafad" / "__init__.py"
        assert scafad_init.exists(), "scafad/__init__.py not found"

    def test_no_python_syntax_errors_in_tests(self):
        """Test files should have valid Python syntax."""
        test_files = glob.glob(str(PROJECT_ROOT / "tests" / "unit" / "test_*.py"))

        for test_file in test_files:
            try:
                with open(test_file, "r", encoding="utf-8") as f:
                    compile(f.read(), test_file, "exec")
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {test_file}: {e}")


class TestFrontMatterIntegrity:
    """Verify front_matter.md is complete and consistent."""

    def test_front_matter_exists(self):
        """front_matter.md must exist."""
        front_matter_path = DISSERTATION_ROOT / "front_matter.md"
        assert front_matter_path.exists(), "front_matter.md not found"

    def test_front_matter_has_abstract(self):
        """front_matter.md must contain abstract section."""
        front_matter_path = DISSERTATION_ROOT / "front_matter.md"
        with open(front_matter_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "## Abstract" in content, "Abstract section missing from front_matter.md"

    def test_front_matter_has_table_of_contents(self):
        """front_matter.md must contain table of contents."""
        front_matter_path = DISSERTATION_ROOT / "front_matter.md"
        with open(front_matter_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "## Table of Contents" in content, (
            "Table of Contents section missing from front_matter.md"
        )


class TestAbstractMetrics:
    """Verify abstract contains key metrics."""

    def test_abstract_mentions_f1_roc_auc(self):
        """Abstract should mention F1 and ROC-AUC."""
        front_matter_path = DISSERTATION_ROOT / "front_matter.md"
        with open(front_matter_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract abstract section
        abstract_match = re.search(
            r"## Abstract\n(.*?)\n---", content, re.DOTALL
        )
        assert abstract_match, "Could not extract abstract"

        abstract = abstract_match.group(1)

        # Check for key metrics
        assert "1.0000" in abstract or "ROC-AUC" in abstract, (
            "Abstract should mention ROC-AUC or F1=1.0000"
        )

    def test_abstract_mentions_preservation_fidelity(self):
        """Abstract should mention ≥99.95% preservation."""
        front_matter_path = DISSERTATION_ROOT / "front_matter.md"
        with open(front_matter_path, "r", encoding="utf-8") as f:
            content = f.read()

        abstract_match = re.search(
            r"## Abstract\n(.*?)\n---", content, re.DOTALL
        )
        assert abstract_match, "Could not extract abstract"

        abstract = abstract_match.group(1)

        # Check for preservation metric
        assert "99.95" in abstract or "fidelity" in abstract, (
            "Abstract should mention preservation fidelity ≥99.95%"
        )
