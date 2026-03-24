"""Tests for agentshift.validators — per-platform schema validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from agentshift.validators import run_validation

FIXTURES = Path(__file__).parent / "fixtures"
_VENV_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "agentshift"
AGENTSHIFT = [str(_VENV_BIN)] if _VENV_BIN.exists() else [sys.executable, "-m", "agentshift"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_validate(
    output_dir: Path, target: str, extra: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    cmd = [*AGENTSHIFT, "validate", str(output_dir), "--target", target, *(extra or [])]
    return subprocess.run(cmd, capture_output=True, text=True)


def make_claude_code_dir(
    tmp_path: Path, *, claude_md: str = "# Agent\nDo stuff.", settings: dict | None = None
) -> Path:
    (tmp_path / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
    if settings is None:
        settings = {"permissions": {"allow": ["Bash(git:*)"], "deny": []}}
    (tmp_path / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return tmp_path


def make_copilot_dir(
    tmp_path: Path, *, frontmatter: dict | None = None, name: str = "myagent"
) -> Path:
    if frontmatter is None:
        frontmatter = {
            "name": "My Agent",
            "description": "Does things",
            "model": ["gpt-4o"],
            "tools": ["web"],
        }
    fm = yaml.dump(frontmatter, default_flow_style=False)
    content = f"---\n{fm}---\n\n# Instructions\nBe helpful."
    (tmp_path / f"{name}.agent.md").write_text(content, encoding="utf-8")
    return tmp_path


def make_bedrock_dir(
    tmp_path: Path, instruction: str = "Be helpful.", extra_cf: dict | None = None
) -> Path:
    (tmp_path / "instruction.txt").write_text(instruction, encoding="utf-8")
    openapi = {"openapi": "3.0.0", "info": {"title": "Agent", "version": "1.0"}, "paths": {}}
    (tmp_path / "openapi.json").write_text(json.dumps(openapi), encoding="utf-8")
    cf = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Resources": {
            "MyAgent": {
                "Type": "AWS::Bedrock::Agent",
                "Properties": {"AgentName": "TestAgent"},
            }
        },
    }
    if extra_cf:
        cf.update(extra_cf)
    (tmp_path / "cloudformation.yaml").write_text(yaml.dump(cf), encoding="utf-8")
    return tmp_path


def make_m365_dir(tmp_path: Path, *, instructions: str = "Be helpful.") -> Path:
    da = {
        "$schema": "https://developer.microsoft.com/json-schemas/copilot/declarative-agent/v1.0/schema.json",
        "version": "v1.0",
        "name": "My Agent",
        "description": "Does things",
        "instructions": instructions,
    }
    (tmp_path / "declarative-agent.json").write_text(json.dumps(da), encoding="utf-8")
    manifest = {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/vDevPreview/MicrosoftTeams.schema.json",
        "manifestVersion": "devPreview",
        "copilotAgents": {"declarativeAgents": [{"id": "da1", "file": "declarative-agent.json"}]},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def make_vertex_dir(tmp_path: Path, *, goal: str = "Be helpful.") -> Path:
    agent = {
        "displayName": "My Agent",
        "goal": goal,
        "instructions": [{"text": "Be polite."}],
    }
    (tmp_path / "agent.json").write_text(json.dumps(agent), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# claude-code validator
# ---------------------------------------------------------------------------


class TestClaudeCodeValidator:
    def test_valid_dir_passes(self, tmp_path):
        make_claude_code_dir(tmp_path)
        report = run_validation(tmp_path, "claude-code")
        assert report.ok

    def test_missing_claude_md_fails(self, tmp_path):
        settings = {"permissions": {"allow": []}}
        (tmp_path / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        report = run_validation(tmp_path, "claude-code")
        assert not report.ok
        assert any("CLAUDE.md" in e.name for e in report.errors)

    def test_empty_claude_md_fails(self, tmp_path):
        make_claude_code_dir(tmp_path, claude_md="   ")
        report = run_validation(tmp_path, "claude-code")
        assert not report.ok

    def test_missing_settings_json_fails(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Agent", encoding="utf-8")
        report = run_validation(tmp_path, "claude-code")
        assert not report.ok
        assert any("settings.json" in e.name for e in report.errors)

    def test_invalid_json_settings_fails(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Agent", encoding="utf-8")
        (tmp_path / "settings.json").write_text("{not valid json", encoding="utf-8")
        report = run_validation(tmp_path, "claude-code")
        assert not report.ok

    def test_settings_without_permissions_fails(self, tmp_path):
        make_claude_code_dir(tmp_path, settings={"other": "stuff"})
        report = run_validation(tmp_path, "claude-code")
        assert not report.ok
        assert any("permissions" in e.name for e in report.errors)

    def test_allow_not_list_fails(self, tmp_path):
        make_claude_code_dir(tmp_path, settings={"permissions": {"allow": "Bash(*)", "deny": []}})
        report = run_validation(tmp_path, "claude-code")
        assert not report.ok

    def test_bash_star_is_warning_not_error(self, tmp_path):
        make_claude_code_dir(tmp_path, settings={"permissions": {"allow": ["Bash(*)"], "deny": []}})
        report = run_validation(tmp_path, "claude-code")
        # should still pass (no hard errors) but emit a warning
        assert report.ok
        assert any("Bash(*)" in w.name for w in report.warnings)


# ---------------------------------------------------------------------------
# copilot validator
# ---------------------------------------------------------------------------


class TestCopilotValidator:
    def test_valid_dir_passes(self, tmp_path):
        make_copilot_dir(tmp_path)
        report = run_validation(tmp_path, "copilot")
        assert report.ok

    def test_missing_agent_md_fails(self, tmp_path):
        report = run_validation(tmp_path, "copilot")
        assert not report.ok
        assert any("agent.md" in e.name for e in report.errors)

    def test_missing_name_fails(self, tmp_path):
        fm = {"description": "Does stuff", "model": ["gpt-4o"], "tools": []}
        make_copilot_dir(tmp_path, frontmatter=fm)
        report = run_validation(tmp_path, "copilot")
        assert not report.ok

    def test_empty_model_list_fails(self, tmp_path):
        fm = {"name": "Agent", "description": "Does stuff", "model": [], "tools": []}
        make_copilot_dir(tmp_path, frontmatter=fm)
        report = run_validation(tmp_path, "copilot")
        assert not report.ok

    def test_empty_description_fails(self, tmp_path):
        fm = {"name": "Agent", "description": "  ", "model": ["gpt-4o"], "tools": []}
        make_copilot_dir(tmp_path, frontmatter=fm)
        report = run_validation(tmp_path, "copilot")
        assert not report.ok

    def test_model_not_list_fails(self, tmp_path):
        fm = {"name": "Agent", "description": "Does stuff", "model": "gpt-4o", "tools": []}
        make_copilot_dir(tmp_path, frontmatter=fm)
        report = run_validation(tmp_path, "copilot")
        assert not report.ok


# ---------------------------------------------------------------------------
# bedrock validator
# ---------------------------------------------------------------------------


class TestBedrockValidator:
    def test_valid_dir_passes(self, tmp_path):
        make_bedrock_dir(tmp_path)
        report = run_validation(tmp_path, "bedrock")
        assert report.ok

    def test_missing_instruction_txt_fails(self, tmp_path):
        make_bedrock_dir(tmp_path)
        (tmp_path / "instruction.txt").unlink()
        report = run_validation(tmp_path, "bedrock")
        assert not report.ok

    def test_instruction_too_long_fails(self, tmp_path):
        make_bedrock_dir(tmp_path, instruction="x" * 4001)
        report = run_validation(tmp_path, "bedrock")
        assert not report.ok
        assert any("4000" in e.message for e in report.errors)

    def test_instruction_exactly_4000_passes(self, tmp_path):
        make_bedrock_dir(tmp_path, instruction="x" * 4000)
        report = run_validation(tmp_path, "bedrock")
        # instruction check should pass
        instr_check = next((c for c in report.checks if "length" in c.name), None)
        assert instr_check is not None and instr_check.passed

    def test_missing_openapi_json_fails(self, tmp_path):
        make_bedrock_dir(tmp_path)
        (tmp_path / "openapi.json").unlink()
        report = run_validation(tmp_path, "bedrock")
        assert not report.ok

    def test_openapi_missing_keys_fails(self, tmp_path):
        make_bedrock_dir(tmp_path)
        (tmp_path / "openapi.json").write_text(json.dumps({"openapi": "3.0.0"}), encoding="utf-8")
        report = run_validation(tmp_path, "bedrock")
        assert not report.ok

    def test_missing_cloudformation_fails(self, tmp_path):
        make_bedrock_dir(tmp_path)
        (tmp_path / "cloudformation.yaml").unlink()
        report = run_validation(tmp_path, "bedrock")
        assert not report.ok

    def test_no_bedrock_agent_resource_fails(self, tmp_path):
        make_bedrock_dir(tmp_path)
        cf = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}},
        }
        (tmp_path / "cloudformation.yaml").write_text(yaml.dump(cf), encoding="utf-8")
        report = run_validation(tmp_path, "bedrock")
        assert not report.ok


# ---------------------------------------------------------------------------
# m365 validator
# ---------------------------------------------------------------------------


class TestM365Validator:
    def test_valid_dir_passes(self, tmp_path):
        make_m365_dir(tmp_path)
        report = run_validation(tmp_path, "m365")
        assert report.ok

    def test_missing_declarative_agent_json_fails(self, tmp_path):
        make_m365_dir(tmp_path)
        (tmp_path / "declarative-agent.json").unlink()
        report = run_validation(tmp_path, "m365")
        assert not report.ok

    def test_instructions_too_long_fails(self, tmp_path):
        make_m365_dir(tmp_path, instructions="x" * 8001)
        report = run_validation(tmp_path, "m365")
        assert not report.ok

    def test_missing_manifest_json_fails(self, tmp_path):
        make_m365_dir(tmp_path)
        (tmp_path / "manifest.json").unlink()
        report = run_validation(tmp_path, "m365")
        assert not report.ok

    def test_manifest_missing_copilot_agents_fails(self, tmp_path):
        make_m365_dir(tmp_path)
        (tmp_path / "manifest.json").write_text(
            json.dumps({"manifestVersion": "1.0"}), encoding="utf-8"
        )
        report = run_validation(tmp_path, "m365")
        assert not report.ok


# ---------------------------------------------------------------------------
# vertex validator
# ---------------------------------------------------------------------------


class TestVertexValidator:
    def test_valid_dir_passes(self, tmp_path):
        make_vertex_dir(tmp_path)
        report = run_validation(tmp_path, "vertex")
        assert report.ok

    def test_missing_agent_json_fails(self, tmp_path):
        report = run_validation(tmp_path, "vertex")
        assert not report.ok

    def test_missing_display_name_fails(self, tmp_path):
        agent = {"goal": "Be helpful.", "instructions": []}
        (tmp_path / "agent.json").write_text(json.dumps(agent), encoding="utf-8")
        report = run_validation(tmp_path, "vertex")
        assert not report.ok

    def test_goal_too_long_fails(self, tmp_path):
        make_vertex_dir(tmp_path, goal="x" * 8001)
        report = run_validation(tmp_path, "vertex")
        assert not report.ok

    def test_goal_exactly_8000_passes(self, tmp_path):
        make_vertex_dir(tmp_path, goal="x" * 8000)
        report = run_validation(tmp_path, "vertex")
        goal_check = next((c for c in report.checks if "goal length" in c.name), None)
        assert goal_check is not None and goal_check.passed


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestValidateCLI:
    def test_valid_claude_code_exit_zero(self, tmp_path):
        make_claude_code_dir(tmp_path)
        result = run_validate(tmp_path, "claude-code")
        assert result.returncode == 0, result.stderr

    def test_invalid_claude_code_exit_nonzero(self, tmp_path):
        result = run_validate(tmp_path, "claude-code")
        assert result.returncode != 0

    def test_json_flag_emits_valid_json(self, tmp_path):
        make_claude_code_dir(tmp_path)
        result = run_validate(tmp_path, "claude-code", extra=["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert "checks" in data

    def test_json_flag_failure_has_error_count(self, tmp_path):
        result = run_validate(tmp_path, "claude-code", extra=["--json"])
        assert result.returncode != 0
        data = json.loads(result.stdout)
        assert data["ok"] is False
        assert data["error_count"] > 0

    def test_unknown_platform_exit_nonzero(self, tmp_path):
        make_claude_code_dir(tmp_path)
        result = run_validate(tmp_path, "unknown-platform")
        assert result.returncode != 0

    def test_stdout_contains_checkmarks_on_pass(self, tmp_path):
        make_claude_code_dir(tmp_path)
        result = run_validate(tmp_path, "claude-code")
        assert "passed" in result.stdout.lower() or "✅" in result.stdout
