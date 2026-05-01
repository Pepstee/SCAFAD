"""
Tests for WP-GA3 Ph1: Trim dissertation to ≤10,000 words AND restore Ch10 to ≥2,200w.

Task ID: a1b2c3d4-0001-0001-0001-000000000001
Test Task ID: 1fa9400b-5910-475c-b0e2-aea146a25b95

Validates all acceptance criteria:
1. Body word count (Ch1-Ch11, headings excluded) is ≤10,000 words
2. Ch10 ≥2,200 words
3. Ch2 ≥1,800 words, Ch7 ≥1,200 words
4. front_matter.md declared word count updated to match
5. No TODO/FIXME in modified files
"""

import glob
import os
import re
from pathlib import Path

import pytest

DISSERTATION_ROOT = Path(__file__).parent.parent.parent / "dissertation"
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Target files for this task
TARGET_FILES = [
    "chapter_10_discussion.md",
    "chapter_02_literature_review.md",
    "chapter_06_design.md",
    "front_matter.md",
]

# Chapter word-count floors
CHAPTER_FLOORS = {
    "chapter_02_literature_review.md": 1800,
    "chapter_07_implementation.md": 1200,
    "chapter_10_discussion.md": 2200,
}

BODY_WORD_LIMIT = 10000


def markdown_to_text(content: str) -> str:
    """Strip common markdown syntax for rough word-counting.

    Mirrors the approach in count_words.py to ensure consistent results.
    """
    content = re.sub(r"```.*?```", " ", content, flags=re.DOTALL)
    content = re.sub(r"`[^`]+`", " ", content)
    content = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", content)
    content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
    content = re.sub(r"^#+\s*", " ", content, flags=re.MULTILINE)
    content = re.sub(r"^\|.*\|$", " ", content, flags=re.MULTILINE)
    content = re.sub(r"[*_>#-]", " ", content)
    return re.sub(r"\s+", " ", content).strip()


def count_words_in_text(text: str) -> int:
    """Count words in text using the same methodology as count_words.py."""
    return len(re.findall(r"\b[\w'-]+\b", markdown_to_text(text)))


def get_chapter_word_counts() -> dict:
    """Return dict mapping chapter filename -> word count for all chapter_*.md files."""
    chapter_files = sorted(glob.glob(str(DISSERTATION_ROOT / "chapter_*.md")))
    counts = {}
    for fpath in chapter_files:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        counts[Path(fpath).name] = count_words_in_text(content)
    return counts


class TestBodyWordCount:
    """AC1: Body word count (Ch1-Ch11, headings excluded) is ≤10,000 words."""

    def test_body_word_count_under_limit(self):
        """Total prose across all 11 chapters must be ≤10,000 words."""
        counts = get_chapter_word_counts()
        total = sum(counts.values())

        print(f"\nBody word count by chapter:")
        for name, count in sorted(counts.items()):
            print(f"  {name}: {count} words")
        print(f"Total body: {total} words")

        assert total <= BODY_WORD_LIMIT, (
            f"Body word count {total} exceeds limit {BODY_WORD_LIMIT}. "
            f"Excess: {total - BODY_WORD_LIMIT} words"
        )


class TestChapterFloors:
    """AC2 & AC3: Individual chapter word-count floors."""

    def test_chapter_10_meets_floor(self):
        """Ch10 must be ≥2,200 words."""
        counts = get_chapter_word_counts()
        ch10_count = counts.get("chapter_10_discussion.md", 0)
        print(f"\nChapter 10 word count: {ch10_count}")
        assert ch10_count >= 2200, (
            f"Chapter 10 has {ch10_count} words, but must be ≥2,200. "
            f"Short by {2200 - ch10_count} words"
        )

    def test_chapter_02_meets_floor(self):
        """Ch2 must be ≥1,800 words."""
        counts = get_chapter_word_counts()
        ch2_count = counts.get("chapter_02_literature_review.md", 0)
        print(f"\nChapter 2 word count: {ch2_count}")
        assert ch2_count >= 1800, (
            f"Chapter 2 has {ch2_count} words, but must be ≥1,800. "
            f"Short by {1800 - ch2_count} words"
        )

    def test_chapter_07_meets_floor(self):
        """Ch7 must be ≥1,200 words."""
        counts = get_chapter_word_counts()
        ch7_count = counts.get("chapter_07_implementation.md", 0)
        print(f"\nChapter 7 word count: {ch7_count}")
        assert ch7_count >= 1200, (
            f"Chapter 7 has {ch7_count} words, but must be ≥1,200. "
            f"Short by {1200 - ch7_count} words"
        )


class TestFrontMatterDeclaration:
    """AC4: front_matter.md declared word count updated to match."""

    def test_front_matter_declaration_matches_body(self):
        """Line 11 of front_matter.md must declare a word count matching actual body total."""
        front_matter_path = DISSERTATION_ROOT / "front_matter.md"
        assert front_matter_path.exists(), "front_matter.md not found"

        with open(front_matter_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) > 10, "front_matter.md too short (need at least 11 lines)"

        declaration_line = lines[10]  # Line 11 (0-indexed)
        print(f"\nfront_matter.md line 11: {declaration_line.strip()}")

        # Extract word count from declaration
        match = re.search(r"(\d{1,2},?\d{3}|\d{4,5})\s+words", declaration_line)
        assert match, f"Could not parse word count from: {declaration_line}"

        declared_count = int(match.group(1).replace(",", ""))

        # Compute actual word count from all chapters
        counts = get_chapter_word_counts()
        actual_count = sum(counts.values())

        print(f"Declared: {declared_count}")
        print(f"Actual:   {actual_count}")

        # Allow small rounding differences (±10 words)
        assert abs(declared_count - actual_count) <= 10, (
            f"Declared count ({declared_count}) does not match computed count ({actual_count}). "
            f"Difference: {declared_count - actual_count} words"
        )


class TestNoTodoFixme:
    """AC5: No TODO/FIXME in modified files."""

    @pytest.mark.parametrize("filename", TARGET_FILES)
    def test_no_todo_fixme_in_target_file(self, filename):
        """Target files must not contain TODO or FIXME markers."""
        filepath = DISSERTATION_ROOT / filename
        assert filepath.exists(), f"{filename} not found"

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Case-insensitive search for TODO or FIXME
        matches = re.findall(r"TODO|FIXME", content, re.IGNORECASE)
        assert not matches, (
            f"Found {len(matches)} TODO/FIXME markers in {filename}: {matches}"
        )


class TestTargetFilesExist:
    """Sanity: all target files exist and are readable."""

    @pytest.mark.parametrize("filename", TARGET_FILES)
    def test_target_file_exists(self, filename):
        """Each target file must exist and be non-empty."""
        filepath = DISSERTATION_ROOT / filename
        assert filepath.exists(), f"{filename} not found"
        assert filepath.stat().st_size > 0, f"{filename} is empty"
