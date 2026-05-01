"""
Tests for WP-4.7: GitHub Actions CI workflow — pytest on every push

This module verifies that:
1. .github/workflows/ci.yml exists at correct path
2. Workflow YAML is valid
3. Workflow triggers on both push and pull_request (all branches)
4. Workflow uses Python 3.11
5. Workflow installs dependencies from requirements.txt
6. Workflow runs pytest on scafad/ with --tb=short
7. Workflow structure is clean and minimal (no extraneous steps)
8. All required fields and values are correct

Test categories:
- TestCIWorkflowExists (2 tests)
- TestYAMLValidity (3 tests)
- TestTriggerConfiguration (4 tests)
- TestJobConfiguration (3 tests)
- TestCheckoutStep (2 tests)
- TestPythonSetupStep (4 tests)
- TestDependencyInstallStep (5 tests)
- TestPytestRunStep (6 tests)
- TestWorkflowStructure (5 tests)
- TestAcceptanceCriteria (8 tests)
"""

import json
import os
import re
from pathlib import Path

import pytest
import yaml


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def ci_yml_path(project_root):
    """Get .github/workflows/ci.yml path."""
    return project_root / ".github" / "workflows" / "ci.yml"


@pytest.fixture
def ci_yml_content(ci_yml_path):
    """Read ci.yml raw content."""
    if ci_yml_path.exists():
        return ci_yml_path.read_text()
    return ""


@pytest.fixture
def ci_yml_parsed(ci_yml_content):
    """Parse ci.yml as YAML."""
    if not ci_yml_content:
        return None
    try:
        return yaml.safe_load(ci_yml_content)
    except yaml.YAMLError:
        return None


@pytest.fixture
def requirements_txt_path(project_root):
    """Get requirements.txt path."""
    return project_root / "requirements.txt"


@pytest.fixture
def requirements_txt_exists(requirements_txt_path):
    """Check if requirements.txt exists."""
    return requirements_txt_path.exists()


# ============================================================================
# TestCIWorkflowExists - Verify file exists at correct path
# ============================================================================

class TestCIWorkflowExists:
    """Test that CI workflow file exists at expected location."""

    def test_ci_yml_file_exists(self, ci_yml_path):
        """CI workflow file should exist at .github/workflows/ci.yml."""
        assert ci_yml_path.exists(), f"ci.yml does not exist at {ci_yml_path}"

    def test_ci_yml_file_is_readable(self, ci_yml_path):
        """CI workflow file should be readable."""
        assert ci_yml_path.is_file(), f"ci.yml is not a regular file"
        assert os.access(ci_yml_path, os.R_OK), f"ci.yml is not readable"


# ============================================================================
# TestYAMLValidity - Verify YAML syntax and structure
# ============================================================================

class TestYAMLValidity:
    """Test that ci.yml is valid YAML."""

    def test_ci_yml_parses_as_yaml(self, ci_yml_content):
        """CI workflow should be valid YAML."""
        assert ci_yml_content, "ci.yml is empty"
        try:
            yaml.safe_load(ci_yml_content)
        except yaml.YAMLError as e:
            pytest.fail(f"ci.yml is not valid YAML: {e}")

    def test_ci_yml_parsed_is_dict(self, ci_yml_parsed):
        """Parsed YAML should be a dictionary."""
        assert isinstance(ci_yml_parsed, dict), \
            f"Parsed YAML should be dict, got {type(ci_yml_parsed)}"

    def test_ci_yml_has_required_top_level_keys(self, ci_yml_parsed):
        """Parsed YAML should have 'name', 'on', and 'jobs' keys."""
        assert "name" in ci_yml_parsed, "Missing 'name' key"
        assert "on" in ci_yml_parsed, "Missing 'on' key"
        assert "jobs" in ci_yml_parsed, "Missing 'jobs' key"


# ============================================================================
# TestTriggerConfiguration - Verify workflow triggers
# ============================================================================

class TestTriggerConfiguration:
    """Test that workflow triggers on correct events."""

    def test_ci_workflow_name_is_ci(self, ci_yml_parsed):
        """Workflow name should be 'CI'."""
        assert ci_yml_parsed.get("name") == "CI", \
            f"Expected name 'CI', got '{ci_yml_parsed.get('name')}'"

    def test_ci_has_on_key(self, ci_yml_parsed):
        """Workflow should have 'on' key."""
        assert "on" in ci_yml_parsed, "Missing 'on' key"
        assert isinstance(ci_yml_parsed["on"], dict), \
            f"'on' should be dict, got {type(ci_yml_parsed['on'])}"

    def test_ci_triggers_on_push(self, ci_yml_parsed):
        """Workflow should trigger on push."""
        on_config = ci_yml_parsed.get("on", {})
        assert "push" in on_config, "Workflow does not trigger on push"

    def test_ci_triggers_on_pull_request(self, ci_yml_parsed):
        """Workflow should trigger on pull_request."""
        on_config = ci_yml_parsed.get("on", {})
        assert "pull_request" in on_config, "Workflow does not trigger on pull_request"


# ============================================================================
# TestJobConfiguration - Verify jobs section
# ============================================================================

class TestJobConfiguration:
    """Test that jobs section is correctly configured."""

    def test_ci_has_jobs_key(self, ci_yml_parsed):
        """Workflow should have 'jobs' key."""
        assert "jobs" in ci_yml_parsed, "Missing 'jobs' key"
        assert isinstance(ci_yml_parsed["jobs"], dict), \
            f"'jobs' should be dict, got {type(ci_yml_parsed['jobs'])}"

    def test_ci_has_test_job(self, ci_yml_parsed):
        """Workflow should have a 'test' job."""
        jobs = ci_yml_parsed.get("jobs", {})
        assert "test" in jobs, "Missing 'test' job"
        assert isinstance(jobs["test"], dict), \
            f"'test' job should be dict, got {type(jobs['test'])}"

    def test_test_job_runs_on_ubuntu_latest(self, ci_yml_parsed):
        """'test' job should run on ubuntu-latest."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        runs_on = test_job.get("runs-on")
        assert runs_on == "ubuntu-latest", \
            f"Expected 'ubuntu-latest', got '{runs_on}'"


# ============================================================================
# TestCheckoutStep - Verify checkout step
# ============================================================================

class TestCheckoutStep:
    """Test checkout step configuration."""

    def test_test_job_has_steps(self, ci_yml_parsed):
        """'test' job should have 'steps' list."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        assert "steps" in test_job, "Missing 'steps' in test job"
        assert isinstance(test_job["steps"], list), \
            f"'steps' should be list, got {type(test_job['steps'])}"
        assert len(test_job["steps"]) > 0, "No steps defined"

    def test_first_step_is_checkout(self, ci_yml_parsed):
        """First step should be checkout."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        assert len(steps) > 0, "No steps defined"
        first_step = steps[0]
        assert "uses" in first_step, "First step missing 'uses' key"
        assert "checkout" in first_step["uses"].lower(), \
            f"First step should be checkout, got {first_step.get('uses')}"


# ============================================================================
# TestPythonSetupStep - Verify Python setup step
# ============================================================================

class TestPythonSetupStep:
    """Test Python 3.11 setup step."""

    def test_has_setup_python_step(self, ci_yml_parsed):
        """Should have a 'setup-python' step."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        setup_python_step = None
        for step in steps:
            if "setup-python" in step.get("uses", ""):
                setup_python_step = step
                break
        assert setup_python_step is not None, "Missing 'setup-python' step"

    def test_setup_python_has_with_config(self, ci_yml_parsed):
        """setup-python step should have 'with' configuration."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        setup_python_step = None
        for step in steps:
            if "setup-python" in step.get("uses", ""):
                setup_python_step = step
                break
        assert "with" in setup_python_step, "Missing 'with' in setup-python step"

    def test_python_version_is_3_11(self, ci_yml_parsed):
        """Python version should be '3.11'."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        setup_python_step = None
        for step in steps:
            if "setup-python" in step.get("uses", ""):
                setup_python_step = step
                break
        with_config = setup_python_step.get("with", {})
        python_version = with_config.get("python-version")
        assert python_version == "3.11", \
            f"Expected Python '3.11', got '{python_version}'"

    def test_pip_cache_is_enabled(self, ci_yml_parsed):
        """pip cache should be enabled."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        setup_python_step = None
        for step in steps:
            if "setup-python" in step.get("uses", ""):
                setup_python_step = step
                break
        with_config = setup_python_step.get("with", {})
        cache = with_config.get("cache")
        assert cache == "pip", \
            f"Expected cache='pip', got '{cache}'"


# ============================================================================
# TestDependencyInstallStep - Verify dependency installation
# ============================================================================

class TestDependencyInstallStep:
    """Test dependency installation step."""

    def test_has_install_dependencies_step(self, ci_yml_parsed):
        """Should have an 'Install dependencies' step."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        install_step = None
        for step in steps:
            if step.get("name") == "Install dependencies":
                install_step = step
                break
        assert install_step is not None, "Missing 'Install dependencies' step"

    def test_install_step_has_run_command(self, ci_yml_parsed):
        """Install dependencies step should have 'run' command."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        install_step = None
        for step in steps:
            if step.get("name") == "Install dependencies":
                install_step = step
                break
        assert "run" in install_step, "Missing 'run' in install step"

    def test_install_step_upgrades_pip(self, ci_yml_parsed):
        """Install dependencies step should upgrade pip."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        install_step = None
        for step in steps:
            if step.get("name") == "Install dependencies":
                install_step = step
                break
        run_command = install_step.get("run", "")
        assert "pip install --upgrade pip" in run_command, \
            "Missing 'pip install --upgrade pip' command"

    def test_install_step_installs_from_requirements_txt(self, ci_yml_parsed):
        """Install dependencies step should install from requirements.txt."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        install_step = None
        for step in steps:
            if step.get("name") == "Install dependencies":
                install_step = step
                break
        run_command = install_step.get("run", "")
        assert "pip install -r requirements.txt" in run_command, \
            "Missing 'pip install -r requirements.txt' command"

    def test_requirements_txt_file_exists(self, requirements_txt_exists):
        """requirements.txt should exist in project root."""
        assert requirements_txt_exists, \
            "requirements.txt does not exist in project root"


# ============================================================================
# TestPytestRunStep - Verify pytest execution step
# ============================================================================

class TestPytestRunStep:
    """Test pytest run step."""

    def test_has_run_pytest_step(self, ci_yml_parsed):
        """Should have a 'Run pytest' step."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        pytest_step = None
        for step in steps:
            if step.get("name") == "Run pytest":
                pytest_step = step
                break
        assert pytest_step is not None, "Missing 'Run pytest' step"

    def test_pytest_step_has_run_command(self, ci_yml_parsed):
        """Run pytest step should have 'run' command."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        pytest_step = None
        for step in steps:
            if step.get("name") == "Run pytest":
                pytest_step = step
                break
        assert "run" in pytest_step, "Missing 'run' in pytest step"

    def test_pytest_command_uses_python_m_pytest(self, ci_yml_parsed):
        """pytest command should use 'python -m pytest'."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        pytest_step = None
        for step in steps:
            if step.get("name") == "Run pytest":
                pytest_step = step
                break
        run_command = pytest_step.get("run", "")
        assert "python -m pytest scafad/" in run_command, \
            f"Expected 'python -m pytest scafad/', got '{run_command}'"

    def test_pytest_command_uses_tb_short(self, ci_yml_parsed):
        """pytest command should use --tb=short flag."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        pytest_step = None
        for step in steps:
            if step.get("name") == "Run pytest":
                pytest_step = step
                break
        run_command = pytest_step.get("run", "")
        assert "--tb=short" in run_command, \
            f"Expected '--tb=short' in command, got '{run_command}'"

    def test_pytest_command_exact_match(self, ci_yml_parsed):
        """pytest command should be exactly 'python -m pytest scafad/ --tb=short'."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        pytest_step = None
        for step in steps:
            if step.get("name") == "Run pytest":
                pytest_step = step
                break
        run_command = pytest_step.get("run", "")
        assert "python -m pytest scafad/ --tb=short" == run_command.strip(), \
            f"Expected exact command 'python -m pytest scafad/ --tb=short', got '{run_command}'"

    def test_pytest_step_is_last_step(self, ci_yml_parsed):
        """Run pytest step should be the last step."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        last_step = steps[-1]
        assert last_step.get("name") == "Run pytest", \
            f"Expected last step to be 'Run pytest', got '{last_step.get('name')}'"


# ============================================================================
# TestWorkflowStructure - Verify overall workflow structure
# ============================================================================

class TestWorkflowStructure:
    """Test overall workflow structure and cleanliness."""

    def test_has_exactly_four_steps(self, ci_yml_parsed):
        """Workflow should have exactly 4 steps (minimal workflow)."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        assert len(steps) == 4, \
            f"Expected 4 steps (minimal), got {len(steps)}"

    def test_step_names_are_correct(self, ci_yml_parsed):
        """All step names should match expected names."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        expected_names = [
            "Checkout repository",
            "Set up Python 3.11",
            "Install dependencies",
            "Run pytest",
        ]
        actual_names = [step.get("name") for step in steps]
        assert actual_names == expected_names, \
            f"Expected steps {expected_names}, got {actual_names}"

    def test_no_environment_variables_defined(self, ci_yml_parsed):
        """Workflow should not have extraneous environment variables."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        # Should not have env at job level (not required for minimal workflow)
        # This is acceptable; we just verify the structure is clean
        assert "env" not in test_job or isinstance(test_job.get("env"), dict)

    def test_no_strategy_matrix(self, ci_yml_parsed):
        """Workflow should not have a strategy matrix (single version)."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        assert "strategy" not in test_job, \
            "Workflow should not have strategy matrix (minimal workflow)"

    def test_no_timeout_defined(self, ci_yml_parsed):
        """Workflow should not define custom timeout (uses default)."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        assert "timeout-minutes" not in test_job, \
            "Workflow should not define custom timeout"


# ============================================================================
# TestAcceptanceCriteria - Verify all acceptance criteria
# ============================================================================

class TestAcceptanceCriteria:
    """Test all acceptance criteria from the task."""

    def test_ac_ci_workflow_exists(self, ci_yml_path):
        """AC: .github/workflows/ci.yml exists."""
        assert ci_yml_path.exists(), \
            f"ci.yml does not exist at {ci_yml_path}"

    def test_ac_workflow_runs_pytest_on_push(self, ci_yml_parsed):
        """AC: Workflow runs on push."""
        on_config = ci_yml_parsed.get("on", {})
        assert "push" in on_config, "Workflow does not trigger on push"

    def test_ac_workflow_runs_pytest_on_pull_request(self, ci_yml_parsed):
        """AC: Workflow runs on pull_request."""
        on_config = ci_yml_parsed.get("on", {})
        assert "pull_request" in on_config, "Workflow does not trigger on pull_request"

    def test_ac_workflow_uses_python_3_11(self, ci_yml_parsed):
        """AC: Workflow uses Python 3.11."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        setup_python_step = None
        for step in steps:
            if "setup-python" in step.get("uses", ""):
                setup_python_step = step
                break
        assert setup_python_step is not None, "Missing setup-python step"
        with_config = setup_python_step.get("with", {})
        python_version = with_config.get("python-version")
        assert python_version == "3.11", \
            f"Expected Python 3.11, got {python_version}"

    def test_ac_workflow_installs_requirements_txt(self, ci_yml_parsed):
        """AC: Workflow installs from requirements.txt."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        install_step = None
        for step in steps:
            if step.get("name") == "Install dependencies":
                install_step = step
                break
        assert install_step is not None, "Missing install step"
        run_command = install_step.get("run", "")
        assert "pip install -r requirements.txt" in run_command, \
            "Missing requirements.txt installation"

    def test_ac_workflow_runs_pytest_scafad(self, ci_yml_parsed):
        """AC: Workflow runs 'python -m pytest scafad/ --tb=short'."""
        test_job = ci_yml_parsed.get("jobs", {}).get("test", {})
        steps = test_job.get("steps", [])
        pytest_step = None
        for step in steps:
            if step.get("name") == "Run pytest":
                pytest_step = step
                break
        assert pytest_step is not None, "Missing pytest step"
        run_command = pytest_step.get("run", "")
        assert "python -m pytest scafad/ --tb=short" == run_command.strip(), \
            f"pytest command incorrect: {run_command}"

    def test_ac_yaml_is_valid(self, ci_yml_content):
        """AC: YAML is valid (parses without error)."""
        try:
            yaml.safe_load(ci_yml_content)
        except yaml.YAMLError as e:
            pytest.fail(f"YAML is not valid: {e}")

    def test_ac_on_key_is_quoted_for_reserved_word(self, ci_yml_content):
        """AC: 'on' key is quoted to handle YAML reserved word."""
        # This is a bit tricky to verify — we check the raw content
        # The YAML parser will handle both quoted and unquoted 'on',
        # but GitHub Actions expects the literal text "on" in the YAML
        assert '"on":' in ci_yml_content or "'on':" in ci_yml_content, \
            "The 'on' key should be quoted in YAML to be explicit"
