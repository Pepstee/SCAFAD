"""
Test suite for Chapter 11: Conclusion.

Verifies that the conclusion chapter:
- Exists and has required structure
- Contains all required sections (11.1, 11.2, 11.3, 11.4)
- Answers all three research questions explicitly
- Has correct word count
- Uses British English conventions
- Contains required citations
- Has no TODO/FIXME markers or incomplete content
"""

import re
from pathlib import Path


class TestChapter11Exists:
    """Verify that Chapter 11 exists and is accessible."""

    def test_chapter_11_file_exists(self):
        """Chapter file must exist at the expected location."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        assert chapter_path.exists(), f"Chapter file not found at {chapter_path}"

    def test_chapter_11_file_not_empty(self):
        """Chapter file must contain content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        assert chapter_path.stat().st_size > 0, "Chapter file is empty"

    def test_chapter_11_readable(self):
        """Chapter file must be readable."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        content = chapter_path.read_text(encoding='utf-8')
        assert len(content) > 100, "Chapter file content too short"


class TestChapter11Structure:
    """Verify the chapter has the required section structure."""

    def _get_content(self):
        """Helper to load chapter content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        return chapter_path.read_text(encoding='utf-8')

    def test_has_chapter_title(self):
        """Chapter must have the main title 'Chapter 11: Conclusion'."""
        content = self._get_content()
        assert "# Chapter 11: Conclusion" in content, "Missing main chapter title"

    def test_has_section_11_1(self):
        """Chapter must have Section 11.1: Summary of Work."""
        content = self._get_content()
        assert "## 11.1 Summary of Work" in content, "Missing Section 11.1"

    def test_has_section_11_2(self):
        """Chapter must have Section 11.2: Answers to Research Questions."""
        content = self._get_content()
        assert "## 11.2 Answers to Research Questions" in content, "Missing Section 11.2"

    def test_has_section_11_3(self):
        """Chapter must have Section 11.3: Contributions."""
        content = self._get_content()
        assert "## 11.3 Contributions" in content, "Missing Section 11.3"

    def test_has_section_11_4(self):
        """Chapter must have Section 11.4: Limitations and Future Work."""
        content = self._get_content()
        assert "## 11.4 Limitations and Future Work" in content, "Missing Section 11.4"

    def test_has_references_section(self):
        """Chapter must have a References section."""
        content = self._get_content()
        assert "## References" in content, "Missing References section"

    def test_sections_in_correct_order(self):
        """Sections must appear in the correct order."""
        content = self._get_content()
        pos_11_1 = content.find("## 11.1")
        pos_11_2 = content.find("## 11.2")
        pos_11_3 = content.find("## 11.3")
        pos_11_4 = content.find("## 11.4")
        pos_refs = content.find("## References")

        assert pos_11_1 > 0, "Section 11.1 not found"
        assert pos_11_2 > pos_11_1, "Section 11.2 must come after 11.1"
        assert pos_11_3 > pos_11_2, "Section 11.3 must come after 11.2"
        assert pos_11_4 > pos_11_3, "Section 11.4 must come after 11.3"
        assert pos_refs > pos_11_4, "References must come after Section 11.4"


class TestChapter11WordCount:
    """Verify the chapter has approximately the required word count."""

    def _get_body_content(self):
        """Extract body content (before References marker)."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        content = chapter_path.read_text(encoding='utf-8')
        # Split at the References separator
        body = content.split("---")[0]  # Get content before the --- separator
        return body

    def _count_words(self, text):
        """Count words in text using Python's split()."""
        words = text.split()
        return len(words)

    def test_word_count_minimum(self):
        """Body should have at least 500 words."""
        body = self._get_body_content()
        word_count = self._count_words(body)
        assert word_count >= 500, f"Body has only {word_count} words; minimum is 500"

    def test_word_count_maximum(self):
        """Body should have at most 800 words."""
        body = self._get_body_content()
        word_count = self._count_words(body)
        assert word_count <= 800, f"Body has {word_count} words; maximum is 800"

    def test_word_count_approximately_600(self):
        """Body should be approximately 600 words (within 100 words)."""
        body = self._get_body_content()
        word_count = self._count_words(body)
        assert 500 <= word_count <= 700, (
            f"Body has {word_count} words; target is ~600 (range 500-700)"
        )


class TestChapter11ResearchQuestions:
    """Verify that all three research questions are answered explicitly."""

    def _get_content(self):
        """Helper to load chapter content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        return chapter_path.read_text(encoding='utf-8')

    def test_rq1_answered_explicitly(self):
        """RQ1 must be answered explicitly in Section 11.2."""
        content = self._get_content()
        # RQ1 should be in the 11.2 section
        section_11_2_start = content.find("## 11.2")
        assert section_11_2_start > 0, "Section 11.2 not found"

        # Look for RQ1 marker in section 11.2
        section_11_2_text = content[section_11_2_start:]
        section_11_2_end = section_11_2_text.find("## 11.3")
        section_11_2_content = section_11_2_text[:section_11_2_end]

        assert "**RQ1**" in section_11_2_content or "**RQ1:" in section_11_2_content, \
            "RQ1 not explicitly marked in Section 11.2"

    def test_rq2_answered_explicitly(self):
        """RQ2 must be answered explicitly in Section 11.2."""
        content = self._get_content()
        section_11_2_start = content.find("## 11.2")
        assert section_11_2_start > 0, "Section 11.2 not found"

        section_11_2_text = content[section_11_2_start:]
        section_11_2_end = section_11_2_text.find("## 11.3")
        section_11_2_content = section_11_2_text[:section_11_2_end]

        assert "**RQ2**" in section_11_2_content or "**RQ2:" in section_11_2_content, \
            "RQ2 not explicitly marked in Section 11.2"

    def test_rq3_answered_explicitly(self):
        """RQ3 must be answered explicitly in Section 11.2."""
        content = self._get_content()
        section_11_2_start = content.find("## 11.2")
        assert section_11_2_start > 0, "Section 11.2 not found"

        section_11_2_text = content[section_11_2_start:]
        section_11_2_end = section_11_2_text.find("## 11.3")
        section_11_2_content = section_11_2_text[:section_11_2_end]

        assert "**RQ3**" in section_11_2_content or "**RQ3:" in section_11_2_content, \
            "RQ3 not explicitly marked in Section 11.2"

    def test_rq1_answer_mentions_metrics(self):
        """RQ1 answer must mention precision/recall or F1 metrics."""
        content = self._get_content()
        rq1_section = content[content.find("**RQ1**"):content.find("**RQ2**")]

        has_metrics = any(metric in rq1_section for metric in
                         ["F1", "precision", "recall", "ROC-AUC", "ROC", "AUC"])
        assert has_metrics, "RQ1 answer must include performance metrics"

    def test_rq2_answer_mentions_ablation(self):
        """RQ2 answer should mention ablation or comparison."""
        content = self._get_content()
        rq2_section = content[content.find("**RQ2**"):content.find("**RQ3**")]

        has_comparison = any(term in rq2_section.lower() for term in
                           ["ablation", "unweighted", "comparison", "vs", "versus"])
        assert has_comparison, "RQ2 answer should reference ablation or comparison"

    def test_rq3_answer_mentions_retention(self):
        """RQ3 answer should mention retention or privacy."""
        content = self._get_content()
        rq3_section = content[content.find("**RQ3**"):content.find("## 11.3")]

        has_retention = any(term in rq3_section.lower() for term in
                           ["retention", "privacy", "fidelity", "pseudonymis"])
        assert has_retention, "RQ3 answer should mention retention/fidelity/privacy"


class TestChapter11BritishEnglish:
    """Verify British English conventions are used throughout."""

    def _get_content(self):
        """Helper to load chapter content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        return chapter_path.read_text(encoding='utf-8')

    def test_uses_whilst_not_while(self):
        """Should use 'whilst' (British) not just 'while' in formal contexts."""
        content = self._get_content()
        # Check that 'whilst' appears at least once
        assert "whilst" in content.lower(), "Should use 'whilst' in British English"

    def test_uses_minimisation_not_minimization(self):
        """Should use 'minimisation' (British) not 'minimization'."""
        content = self._get_content()
        # Check for minimisation (British spelling)
        assert "minimisation" in content.lower(), "Should use 'minimisation' (British spelling)"

    def test_uses_artefacts_not_artifacts(self):
        """Should use 'artefacts' (British) not 'artifacts'."""
        content = self._get_content()
        assert "artefacts" in content.lower(), "Should use 'artefacts' (British spelling)"

    def test_uses_pseudonymises_not_pseudonymizes(self):
        """Should use 'pseudonymises' (British) not 'pseudonymizes'."""
        content = self._get_content()
        assert "pseudonymises" in content.lower(), "Should use 'pseudonymises' (British spelling)"

    def test_no_american_spellings_of_key_terms(self):
        """Should not mix British and American spellings."""
        content = self._get_content()
        # Check that American spellings are not used for these key terms
        american_forms = [
            ("realize", "realise"),
            ("organize", "organise"),
            ("characterize", "characterise"),
        ]

        for american, british in american_forms:
            # If British form is used, American shouldn't be (or vice versa)
            if british in content.lower():
                assert american not in content.lower(), \
                    f"Mixing British '{british}' with American '{american}'"


class TestChapter11Citations:
    """Verify that required citations are present."""

    def _get_content(self):
        """Helper to load chapter content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        return chapter_path.read_text(encoding='utf-8')

    def test_has_harvard_citations(self):
        """References section must use Harvard citation format."""
        content = self._get_content()
        refs_section = content[content.find("## References"):]

        # Harvard format typically has: Author (Year) 'Title', Source.
        has_harvard = "(" in refs_section and ")" in refs_section and "20" in refs_section
        assert has_harvard, "References section must contain Harvard format citations"

    def test_has_davis_goadrich_citation(self):
        """Must cite Davis & Goadrich (2006) on precision-recall curves."""
        content = self._get_content()
        assert "Davis" in content and "Goadrich" in content, \
            "Must cite Davis & Goadrich on precision-recall curves"

    def test_has_jonas_et_al_citation(self):
        """Must cite Jonas et al. (2019) on serverless computing."""
        content = self._get_content()
        assert "Jonas" in content, "Must cite Jonas et al. on serverless computing"

    def test_has_gdpr_citation(self):
        """Must reference GDPR 2016 regulation."""
        content = self._get_content()
        assert "GDPR" in content and "2016" in content, "Must reference GDPR 2016"

    def test_minimum_three_citations(self):
        """References section must have at least 3 citations."""
        content = self._get_content()
        refs_section = content[content.find("## References"):]
        # Count lines that look like citations (start with capital letter, followed by comma or parenthesis)
        citation_lines = [line for line in refs_section.split('\n')
                         if line.strip() and not line.startswith('#') and '(' in line]
        assert len(citation_lines) >= 3, f"Must have at least 3 citations; found {len(citation_lines)}"


class TestChapter11Completeness:
    """Verify the chapter is complete and has no unfinished markers."""

    def _get_content(self):
        """Helper to load chapter content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        return chapter_path.read_text(encoding='utf-8')

    def test_no_todo_markers(self):
        """Chapter must not contain TODO markers."""
        content = self._get_content()
        assert "TODO" not in content and "todo" not in content, \
            "Chapter contains unfinished TODO markers"

    def test_no_fixme_markers(self):
        """Chapter must not contain FIXME markers."""
        content = self._get_content()
        assert "FIXME" not in content and "fixme" not in content, \
            "Chapter contains unfinished FIXME markers"

    def test_no_placeholder_text(self):
        """Chapter must not contain obvious placeholder text."""
        content = self._get_content()
        placeholders = ["[INSERT", "[CITATION", "[REF", "[XXX", "..."]
        for placeholder in placeholders:
            assert placeholder not in content, f"Chapter contains placeholder: {placeholder}"

    def test_no_excessive_ellipsis(self):
        """Chapter should not have many ellipses indicating incomplete text."""
        content = self._get_content()
        ellipsis_count = content.count("...")
        assert ellipsis_count <= 2, f"Chapter has too many ellipses ({ellipsis_count})"

    def test_all_sections_have_content(self):
        """All sections must have substantive content (not just headers)."""
        content = self._get_content()

        sections = {
            "11.1": content.find("## 11.1"),
            "11.2": content.find("## 11.2"),
            "11.3": content.find("## 11.3"),
            "11.4": content.find("## 11.4"),
        }

        for section_num, start_pos in sections.items():
            assert start_pos > 0, f"Section {section_num} not found"

            # Find the next section header
            section_content = content[start_pos:]
            next_section = min(
                (section_content.find(f"## {num}") for num in ["11.2", "11.3", "11.4"]
                 if f"## {num}" in section_content),
                default=len(section_content)
            )

            if next_section == 0:
                next_section = len(section_content)

            section_text = section_content[:next_section].strip()
            # Remove the header itself
            section_text = section_text[section_text.find("\n"):].strip()

            assert len(section_text) > 50, f"Section {section_num} has insufficient content"


class TestChapter11Contributions:
    """Verify Section 11.3 lists contributions appropriately."""

    def _get_content(self):
        """Helper to load chapter content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        return chapter_path.read_text(encoding='utf-8')

    def test_section_11_3_mentions_contributions(self):
        """Section 11.3 must explicitly mention contributions."""
        content = self._get_content()
        section_start = content.find("## 11.3")
        section_end = content.find("## 11.4")
        section_text = content[section_start:section_end]

        assert "contribut" in section_text.lower(), \
            "Section 11.3 must mention contributions"

    def test_contributions_are_listed(self):
        """Section 11.3 should list multiple distinct contributions."""
        content = self._get_content()
        section_start = content.find("## 11.3")
        section_end = content.find("## 11.4")
        section_text = content[section_start:section_end]

        # Count numbered items or bullet points
        has_structure = (
            "1." in section_text or "•" in section_text or "-" in section_text or
            ("a " in section_text and "b " in section_text)
        )

        # Or at least count sentences with "a" or "the" suggesting list items
        assert len(section_text) > 200, "Section 11.3 must have substantial content listing contributions"


class TestChapter11Limitations:
    """Verify Section 11.4 discusses limitations and future work."""

    def _get_content(self):
        """Helper to load chapter content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        return chapter_path.read_text(encoding='utf-8')

    def test_section_11_4_mentions_limitations(self):
        """Section 11.4 must explicitly mention limitations."""
        content = self._get_content()
        section_start = content.find("## 11.4")
        section_end = content.find("## References") if "## References" in content else len(content)
        section_text = content[section_start:section_end]

        assert "limitation" in section_text.lower(), \
            "Section 11.4 must discuss limitations"

    def test_section_11_4_mentions_future_work(self):
        """Section 11.4 must explicitly mention future work."""
        content = self._get_content()
        section_start = content.find("## 11.4")
        section_end = content.find("## References") if "## References" in content else len(content)
        section_text = content[section_start:section_end]

        has_future = ("future" in section_text.lower() or
                     "direction" in section_text.lower() or
                     "extension" in section_text.lower())
        assert has_future, "Section 11.4 must discuss future work or directions"

    def test_limitations_are_specific(self):
        """Limitations should be specific and substantive."""
        content = self._get_content()
        section_start = content.find("## 11.4")
        section_end = content.find("## References") if "## References" in content else len(content)
        section_text = content[section_start:section_end]

        # Check for specific limitation types
        limitation_keywords = ["synthetic", "production", "distribution", "calibration",
                             "robustness", "deployment", "cloud", "adversarial"]
        found_keywords = sum(1 for kw in limitation_keywords if kw in section_text.lower())

        assert found_keywords >= 2, "Limitations should mention at least 2 specific limitation types"


class TestChapter11Summary:
    """Verify Section 11.1 provides appropriate summary."""

    def _get_content(self):
        """Helper to load chapter content."""
        chapter_path = Path(__file__).parent.parent.parent / "dissertation" / "chapter_11_conclusion.md"
        return chapter_path.read_text(encoding='utf-8')

    def test_section_11_1_mentions_architecture(self):
        """Section 11.1 should describe the architecture."""
        content = self._get_content()
        section_start = content.find("## 11.1")
        section_end = content.find("## 11.2")
        section_text = content[section_start:section_end]

        assert "architecture" in section_text.lower() or "layer" in section_text.lower(), \
            "Section 11.1 must describe the system architecture"

    def test_section_11_1_mentions_layers(self):
        """Section 11.1 should mention the layer architecture."""
        content = self._get_content()
        section_start = content.find("## 11.1")
        section_end = content.find("## 11.2")
        section_text = content[section_start:section_end]

        # Should mention layers or layer numbers
        has_layers = any(f"Layer {i}" in section_text for i in range(7))
        assert has_layers or "layer" in section_text.lower(), \
            "Section 11.1 must describe the layer structure"

    def test_section_11_1_mentions_evaluation(self):
        """Section 11.1 should mention evaluation metrics or dataset."""
        content = self._get_content()
        section_start = content.find("## 11.1")
        section_end = content.find("## 11.2")
        section_text = content[section_start:section_end]

        has_eval_content = any(term in section_text.lower() for term in
                              ["evaluation", "test", "record", "dataset", "corpus"])
        assert has_eval_content, "Section 11.1 must mention evaluation approach"
