"""
Tests for Chapter 7 §7.6 showreel/demo fix.

Verify that:
1. The false demo.mp4 claim has been removed
2. Section 7.6 now contains truthful text
3. All referenced evaluation artefacts exist
4. Word count remains within acceptable bounds
5. No broken paths or references exist
"""

import json
from pathlib import Path


class TestChapter7ShowreelFix:
    """Test suite for Chapter 7 §7.6 showreel/demo availability claim fix."""

    @staticmethod
    def get_chapter_7_path():
        """Get the path to Chapter 7 file."""
        return Path(__file__).parent.parent.parent / "dissertation" / "chapter_07_implementation.md"

    @staticmethod
    def get_chapter_7_content():
        """Read Chapter 7 file content."""
        path = TestChapter7ShowreelFix.get_chapter_7_path()
        return path.read_text(encoding='utf-8')

    @staticmethod
    def get_section_7_6():
        """Extract Section 7.6 from Chapter 7."""
        content = TestChapter7ShowreelFix.get_chapter_7_content()
        # Find section 7.6
        start_idx = content.find("## 7.6")
        if start_idx == -1:
            return None
        # Find next section (7.7 or References)
        next_section = content.find("## 7.7", start_idx)
        if next_section == -1:
            next_section = content.find("## References", start_idx)
        if next_section == -1:
            next_section = len(content)
        return content[start_idx:next_section]

    def test_chapter_7_file_exists(self):
        """Test that Chapter 7 file exists and is readable."""
        path = self.get_chapter_7_path()
        assert path.exists(), f"Chapter 7 file not found at {path}"
        assert path.is_file(), f"Chapter 7 path is not a file: {path}"

    def test_section_7_6_exists(self):
        """Test that Section 7.6 exists in the chapter."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found in Chapter 7"
        assert len(section) > 0, "Section 7.6 is empty"

    def test_false_demo_mp4_path_removed(self):
        """Test that the false demo.mp4 path is no longer in the chapter."""
        content = self.get_chapter_7_content()
        assert "demo.mp4" not in content, "Chapter 7 still contains reference to demo.mp4"
        assert "manuscript/appendix/demo.mp4" not in content, "Chapter 7 still contains false demo.mp4 path"

    def test_false_showreel_heading_removed(self):
        """Test that the false 'Showreel Video Reference' heading is removed."""
        content = self.get_chapter_7_content()
        assert "Showreel Video Reference" not in content, "Chapter 7 still contains 'Showreel Video Reference' heading"

    def test_section_7_6_heading_is_correct(self):
        """Test that Section 7.6 has the correct new heading."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "Evaluation Artefacts and Reproducibility Evidence" in section, \
            "Section 7.6 does not have the correct heading"

    def test_section_7_6_signposts_showreel(self):
        """Test that Section 7.6 signposts the showreel script and MP4 path.

        WP-5.12 replaced the original 'No demonstration video has been
        produced' sentence with a conditional signpost pointing at
        ``presentation/showreel.md`` (narrated script) and
        ``presentation/showreel.mp4`` (the recording, once produced).
        This test verifies that the replacement is present and the
        removed text has not been re-introduced.
        """
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "presentation/showreel.md" in section, (
            "Section 7.6 does not reference presentation/showreel.md — "
            "the WP-5.12 signpost is missing"
        )
        assert "showreel.mp4" in section, (
            "Section 7.6 does not reference showreel.mp4 — "
            "the conditional video reference is missing"
        )
        assert "No demonstration video has been produced" not in section, (
            "Section 7.6 still contains the removed 'No demonstration video "
            "has been produced' text that WP-5.12 replaced"
        )

    def test_section_7_6_references_scafad_results_json(self):
        """Test that Section 7.6 references scafad_results.json."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "scafad_results.json" in section, "Section 7.6 does not reference scafad_results.json"

    def test_section_7_6_references_headline_metrics_json(self):
        """Test that Section 7.6 references headline_metrics.json."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "headline_metrics.json" in section, "Section 7.6 does not reference headline_metrics.json"

    def test_section_7_6_references_baselines_summary_md(self):
        """Test that Section 7.6 references baselines_summary.md."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "baselines_summary.md" in section, "Section 7.6 does not reference baselines_summary.md"

    def test_section_7_6_references_evaluation_results_directory(self):
        """Test that Section 7.6 references evaluation/results/."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "evaluation/results/" in section, "Section 7.6 does not reference evaluation/results/"

    def test_scafad_results_json_actually_exists(self):
        """Test that scafad_results.json file actually exists."""
        path = Path(__file__).parent.parent.parent / "evaluation" / "results" / "scafad_results.json"
        assert path.exists(), f"scafad_results.json does not exist at {path}"
        assert path.is_file(), f"scafad_results.json is not a file: {path}"
        # Verify it's valid JSON
        content = path.read_text(encoding='utf-8')
        data = json.loads(content)
        assert isinstance(data, dict), "scafad_results.json does not parse as valid JSON dict"

    def test_headline_metrics_json_actually_exists(self):
        """Test that headline_metrics.json file actually exists."""
        path = Path(__file__).parent.parent.parent / "evaluation" / "results" / "headline_metrics.json"
        assert path.exists(), f"headline_metrics.json does not exist at {path}"
        assert path.is_file(), f"headline_metrics.json is not a file: {path}"
        # Verify it's valid JSON and contains expected metrics
        content = path.read_text(encoding='utf-8')
        data = json.loads(content)
        assert isinstance(data, dict), "headline_metrics.json does not parse as valid JSON dict"
        # Verify F1 and ROC-AUC are 1.0 as claimed in the chapter
        if "scafad" in data:
            assert data["scafad"].get("f1") == 1.0, "headline_metrics.json F1 is not 1.0"
            assert data["scafad"].get("roc_auc") == 1.0, "headline_metrics.json ROC-AUC is not 1.0"

    def test_baselines_summary_md_actually_exists(self):
        """Test that baselines_summary.md file actually exists."""
        path = Path(__file__).parent.parent.parent / "evaluation" / "results" / "baselines_summary.md"
        assert path.exists(), f"baselines_summary.md does not exist at {path}"
        assert path.is_file(), f"baselines_summary.md is not a file: {path}"
        # Verify it's readable and non-empty
        content = path.read_text(encoding='utf-8')
        assert len(content) > 0, "baselines_summary.md is empty"

    def test_no_manuscript_appendix_directory_exists(self):
        """Test that manuscript/appendix/ directory does not exist."""
        path = Path(__file__).parent.parent.parent / "manuscript" / "appendix"
        assert not path.exists(), f"False manuscript/appendix/ directory still exists at {path}"

    def test_no_demo_files_in_repository(self):
        """Test that no demo.* files exist in the repository."""
        repo_root = Path(__file__).parent.parent.parent
        demo_files = list(repo_root.glob("**/demo.*"))
        assert len(demo_files) == 0, f"Found demo files that should not exist: {demo_files}"

    def test_chapter_7_word_count_within_bounds(self):
        """Test that Chapter 7 body word count is within acceptable bounds [1050, 1400].

        Note: Chapter 7 was intentionally trimmed in task 1f7b7f22 (dissertation
        word-count reduction to 9,500–10,500 submission band), reducing the body
        from ~1875 words to ~1155 words.  The bounds have been updated to reflect
        the post-trim chapter state.  The maximum preserves room for minor future
        additions without re-triggering over-length checks.
        """
        content = self.get_chapter_7_content()
        # Extract body (everything before ## References)
        body = content.split("## References")[0]
        # Remove section headers and empty lines
        lines = [l for l in body.split('\n') if l.strip() and not l.startswith('#')]
        # Count words
        words = len(' '.join(lines).split())

        min_bound = 1050
        max_bound = 1400

        assert words >= min_bound, f"Chapter 7 body has {words} words, below minimum {min_bound}"
        assert words <= max_bound, f"Chapter 7 body has {words} words, above maximum {max_bound}"

    def test_british_english_preserved(self):
        """Test that British English spellings are used in the chapter."""
        content = self.get_chapter_7_content()

        # Check for British spellings that should be present
        assert "behaviour" in content, "Chapter 7 should use British 'behaviour' not 'behavior'"

        # Check that American spelling is not used (at least in sections that were changed)
        section_7_6 = self.get_section_7_6()
        if section_7_6:
            # The replacement uses "behaviour" explicitly
            assert "behaviour" in section_7_6 or "behavior" not in section_7_6, \
                "Section 7.6 uses American spelling when British should be used"

    def test_section_7_6_mentions_reproducibility(self):
        """Test that Section 7.6 mentions reproducibility or evidence."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        # Check for reproducibility-related keywords
        text_lower = section.lower()
        assert "reproducibility" in text_lower or "evidence" in text_lower, \
            "Section 7.6 does not mention reproducibility or evidence"

    def test_section_7_6_mentions_six300_records(self):
        """Test that Section 7.6 mentions the 6,300-record cache."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "6,300" in section or "6300" in section, "Section 7.6 does not mention 6,300-record cache"

    def test_section_7_6_mentions_lambda_invocation(self):
        """Test that Section 7.6 mentions Lambda invocation."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "Lambda" in section, "Section 7.6 should mention Lambda invocation"

    def test_section_7_6_mentions_l6_analyst_feedback(self):
        """Test that Section 7.6 mentions L6 analyst feedback."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        assert "L6" in section or "analyst feedback" in section, \
            "Section 7.6 should mention L6 analyst feedback"

    def test_no_broken_evaluation_results_paths(self):
        """Test that paths to evaluation/results/ files are not broken."""
        content = self.get_chapter_7_content()
        # Check for common typos or missing slashes
        assert "evaluation results" not in content or "evaluation/results/" in content, \
            "Chapter 7 may have broken paths to evaluation/results/"

    def test_references_section_unchanged(self):
        """Test that References section still exists and has expected citations."""
        content = self.get_chapter_7_content()
        assert "## References" in content, "References section missing from Chapter 7"
        assert "Beck" in content, "Beck citation missing from Chapter 7"
        assert "Fowler" in content, "Fowler citation missing from Chapter 7"
        assert "Martin" in content, "Martin citation missing from Chapter 7"
        assert "Pressman" in content, "Pressman citation missing from Chapter 7"

    def test_section_7_1_through_7_5_unchanged(self):
        """Test that sections 7.1 through 7.5 still exist."""
        content = self.get_chapter_7_content()
        for i in range(1, 6):
            section_heading = f"## 7.{i}"
            assert section_heading in content, f"Section 7.{i} missing from Chapter 7"

    def test_section_7_7_conclusion_unchanged(self):
        """Test that Section 7.7 Conclusion still exists."""
        content = self.get_chapter_7_content()
        assert "## 7.7" in content, "Section 7.7 Conclusion missing from Chapter 7"

    def test_section_7_6_section_is_complete(self):
        """Test that Section 7.6 is a complete, well-formed paragraph."""
        section = self.get_section_7_6()
        assert section is not None, "Section 7.6 not found"
        # Should have a heading
        assert "## 7.6" in section, "Section 7.6 missing heading"
        # Should have substantial body text
        body = section.split("## 7.6")[1].strip()
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        assert len(lines) > 0, "Section 7.6 body is empty"
        # Body should have multiple sentences
        sentences = [s for l in lines for s in l.split('.') if s.strip()]
        assert len(sentences) >= 2, "Section 7.6 should have multiple sentences"

    def test_headline_metrics_f1_and_rocauc_values(self):
        """Test that headline_metrics.json has expected F1 and ROC-AUC values of 1.0."""
        path = Path(__file__).parent.parent.parent / "evaluation" / "results" / "headline_metrics.json"
        content = path.read_text(encoding='utf-8')
        data = json.loads(content)

        # The chapter mentions "F1 = 1.0000, ROC-AUC = 1.0000"
        if "scafad" in data:
            scafad_metrics = data["scafad"]
            assert scafad_metrics.get("f1") == 1.0, \
                f"Expected F1=1.0 but got {scafad_metrics.get('f1')}"
            assert scafad_metrics.get("roc_auc") == 1.0, \
                f"Expected ROC-AUC=1.0 but got {scafad_metrics.get('roc_auc')}"
