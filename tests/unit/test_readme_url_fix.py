"""
Test: README.md placeholder URL fix (task a1b2c3d4-0032-4000-8000-000000000032).

Verifies that all 'yourusername' and 'scafad-lambda' references have been
replaced with 'Pepstee' and 'scafad-r-core' respectively in README.md.
"""

import re

README_PATH = "README.md"


def _read_readme():
    with open(README_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_no_yourusername_remaining():
    """No instance of 'yourusername' should remain in README.md."""
    content = _read_readme()
    assert "yourusername" not in content, (
        f"Found {content.count('yourusername')} instance(s) of 'yourusername' "
        f"remaining in README.md"
    )


def test_no_scafad_lambda_remaining():
    """No instance of 'scafad-lambda' should remain in README.md."""
    content = _read_readme()
    assert "scafad-lambda" not in content, (
        f"Found {content.count('scafad-lambda')} instance(s) of 'scafad-lambda' "
        f"remaining in README.md"
    )


def test_ci_badge_points_to_pepstee_scafad_r_core():
    """CI badge URL should point to Pepstee/scafad-r-core."""
    content = _read_readme()
    # Line 8: CI badge
    assert (
        "https://github.com/Pepstee/scafad-r-core/actions/workflows/ci.yml"
        in content
    ), "CI badge URL does not point to Pepstee/scafad-r-core"


def test_architecture_badge_links_to_pepstee_scafad_r_core():
    """Architecture badge link should point to Pepstee/scafad-r-core."""
    content = _read_readme()
    # Find the architecture badge link
    arch_pattern = r"\[!\[Architecture\]\([^)]+\)\]\(https://github\.com/Pepstee/scafad-r-core\)"
    assert re.search(arch_pattern, content), (
        "Architecture badge link does not point to Pepstee/scafad-r-core"
    )


def test_performance_badge_links_to_pepstee_scafad_r_core():
    """Performance badge link should point to Pepstee/scafad-r-core."""
    content = _read_readme()
    perf_pattern = r"\[!\[Performance\]\([^)]+\)\]\(https://github\.com/Pepstee/scafad-r-core\)"
    assert re.search(perf_pattern, content), (
        "Performance badge link does not point to Pepstee/scafad-r-core"
    )


def test_citation_url_points_to_pepstee_scafad_r_core():
    """Citation URL should point to Pepstee/scafad-r-core."""
    content = _read_readme()
    assert (
        "url={https://github.com/Pepstee/scafad-r-core}" in content
    ), "Citation URL does not point to Pepstee/scafad-r-core"


def test_issues_url_points_to_pepstee_scafad_r_core():
    """Issues URL should point to Pepstee/scafad-r-core/issues."""
    content = _read_readme()
    assert (
        "https://github.com/Pepstee/scafad-r-core/issues" in content
    ), "Issues URL does not point to Pepstee/scafad-r-core/issues"


def test_no_github_links_to_wrong_repo():
    """All github.com/Pepstee links should reference scafad-r-core, not scafad-lambda."""
    content = _read_readme()
    # Find all github.com/Pepstee URLs
    pepstee_urls = re.findall(
        r"https://github\.com/Pepstee/[a-zA-Z0-9_.-]+", content
    )
    for url in pepstee_urls:
        assert "scafad-r-core" in url, (
            f"Found Pepstee URL pointing to wrong repo: {url}"
        )
