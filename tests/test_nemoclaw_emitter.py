"""Tests for the NVIDIA NemoClaw emitter — IR → workspace files + sandbox config."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
import yaml

from agentshift.emitters.nemoclaw import emit
from agentshift.ir import (
    AgentIR,
    Governance,
    Guardrail,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
)

FIXTURES = Path(__file__).parent / "fixtures"


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-skill",
        description="A test skill for AgentShift NemoClaw",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


# ---------------------------------------------------------------------------
# Basic file creation
# ---------------------------------------------------------------------------


class TestNemoClawEmitterBasic:
    def test_creates_workspace_skill_md(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "workspace" / "SKILL.md").exists()

    def test_creates_workspace_soul_md(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "workspace" / "SOUL.md").exists()

    def test_creates_workspace_identity_md(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "workspace" / "IDENTITY.md").exists()

    def test_creates_nemoclaw_config_yaml(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "nemoclaw-config.yaml").exists()

    def test_creates_network_policy_yaml(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "network-policy.yaml").exists()

    def test_creates_deploy_sh(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "deploy.sh").exists()

    def test_creates_readme_md(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "README.md").exists()

    def test_creates_output_directory_if_missing(self, tmp_path):
        ir = make_simple_ir()
        target = tmp_path / "deep" / "nested" / "dir"
        assert not target.exists()
        emit(ir, target)
        assert target.exists()


# ---------------------------------------------------------------------------
# SKILL.md content
# ---------------------------------------------------------------------------


class TestNemoClawSkillMd:
    def test_skill_md_contains_agent_name(self, tmp_path):
        ir = make_simple_ir(name="my-agent")
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SKILL.md").read_text()
        assert "my-agent" in content

    def test_skill_md_contains_description(self, tmp_path):
        ir = make_simple_ir(description="A great agent")
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SKILL.md").read_text()
        assert "A great agent" in content

    def test_skill_md_contains_system_prompt(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="You are a code reviewer."))
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SKILL.md").read_text()
        assert "You are a code reviewer." in content

    def test_skill_md_contains_tools(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SKILL.md").read_text()
        assert "gh" in content

    def test_skill_md_contains_knowledge(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[KnowledgeSource(name="docs", kind="file", path="/tmp/docs.md")]
        )
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SKILL.md").read_text()
        assert "docs" in content

    def test_skill_md_contains_guardrails(self, tmp_path):
        ir = make_simple_ir(
            governance=Governance(guardrails=[Guardrail(id="g1", text="Never share private keys")])
        )
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SKILL.md").read_text()
        assert "Never share private keys" in content


# ---------------------------------------------------------------------------
# nemoclaw-config.yaml
# ---------------------------------------------------------------------------


class TestNemoClawConfig:
    def test_config_is_valid_yaml(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        raw = (tmp_path / "nemoclaw-config.yaml").read_text()
        data = yaml.safe_load(raw)
        assert isinstance(data, dict)

    def test_config_sandbox_name_matches_ir(self, tmp_path):
        ir = make_simple_ir(name="my-sandbox")
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "nemoclaw-config.yaml").read_text())
        assert data["sandbox"]["name"] == "my-sandbox"

    def test_config_has_inference_provider(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "nemoclaw-config.yaml").read_text())
        assert data["inference"]["provider"] == "nvidia"

    def test_config_workspace_lists_files(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "nemoclaw-config.yaml").read_text())
        files = data["workspace"]["files"]
        assert "workspace/SKILL.md" in files
        assert "workspace/SOUL.md" in files
        assert "workspace/IDENTITY.md" in files

    def test_config_security_posture(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "nemoclaw-config.yaml").read_text())
        assert data["security"]["posture"] == "balanced"

    def test_config_description_truncated_at_100(self, tmp_path):
        long_desc = "x" * 200
        ir = make_simple_ir(description=long_desc)
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "nemoclaw-config.yaml").read_text())
        assert len(data["sandbox"]["description"]) <= 100


# ---------------------------------------------------------------------------
# network-policy.yaml
# ---------------------------------------------------------------------------


class TestNemoClawNetworkPolicy:
    def test_network_policy_is_valid_yaml(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        raw = (tmp_path / "network-policy.yaml").read_text()
        data = yaml.safe_load(raw)
        assert isinstance(data, dict)
        assert "policies" in data

    def test_default_policies_present(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "network-policy.yaml").read_text())
        names = [p["name"] for p in data["policies"]]
        assert "claude_code" in names
        assert "nvidia" in names

    def test_gh_tool_adds_github_policy(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "network-policy.yaml").read_text())
        names = [p["name"] for p in data["policies"]]
        assert "github" in names

    def test_git_tool_adds_github_policy(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="git", description="Git CLI", kind="shell")])
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "network-policy.yaml").read_text())
        names = [p["name"] for p in data["policies"]]
        assert "github" in names

    def test_curl_tool_adds_todo_comment(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="curl", description="HTTP client", kind="shell")])
        emit(ir, tmp_path)
        content = (tmp_path / "network-policy.yaml").read_text()
        assert "TODO" in content
        assert "curl" in content

    def test_npm_tool_adds_npm_registry_policy(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="npm", description="Node pkg mgr", kind="shell")])
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "network-policy.yaml").read_text())
        names = [p["name"] for p in data["policies"]]
        assert "npm_registry" in names

    def test_mcp_tool_adds_todo_comment(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="slack", description="Slack MCP", kind="mcp")])
        emit(ir, tmp_path)
        content = (tmp_path / "network-policy.yaml").read_text()
        assert "TODO" in content
        assert "mcp_slack" in content


# ---------------------------------------------------------------------------
# deploy.sh
# ---------------------------------------------------------------------------


class TestNemoClawDeploySh:
    def test_deploy_sh_is_executable(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        st = os.stat(tmp_path / "deploy.sh")
        assert st.st_mode & stat.S_IXUSR

    def test_deploy_sh_contains_agent_name(self, tmp_path):
        ir = make_simple_ir(name="my-deploy-agent")
        emit(ir, tmp_path)
        content = (tmp_path / "deploy.sh").read_text()
        assert "my-deploy-agent" in content

    def test_deploy_sh_has_shebang(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "deploy.sh").read_text()
        assert content.startswith("#!/usr/bin/env bash")

    def test_deploy_sh_uploads_workspace_files(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "deploy.sh").read_text()
        assert "SKILL.md" in content
        assert "SOUL.md" in content
        assert "IDENTITY.md" in content


# ---------------------------------------------------------------------------
# SOUL.md
# ---------------------------------------------------------------------------


class TestNemoClawSoulMd:
    def test_soul_md_has_core_identity(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SOUL.md").read_text()
        assert "Core Identity" in content

    def test_soul_md_has_boundaries(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SOUL.md").read_text()
        assert "Boundaries" in content

    def test_soul_md_guardrails_in_boundaries(self, tmp_path):
        ir = make_simple_ir(
            governance=Governance(
                guardrails=[Guardrail(id="g1", text="Do not execute destructive commands")]
            )
        )
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SOUL.md").read_text()
        assert "Do not execute destructive commands" in content

    def test_soul_md_default_personality(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="Hello"))
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SOUL.md").read_text()
        assert "Be helpful, accurate, and concise." in content

    def test_soul_md_custom_personality(self, tmp_path):
        ir = make_simple_ir(
            persona=Persona(
                system_prompt="Hello",
                personality_notes="Friendly and enthusiastic",
            )
        )
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SOUL.md").read_text()
        assert "Friendly and enthusiastic" in content


# ---------------------------------------------------------------------------
# IDENTITY.md
# ---------------------------------------------------------------------------


class TestNemoClawIdentityMd:
    def test_identity_md_contains_name(self, tmp_path):
        ir = make_simple_ir(name="id-agent")
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "IDENTITY.md").read_text()
        assert "id-agent" in content

    def test_identity_md_contains_emoji(self, tmp_path):
        ir = make_simple_ir(metadata=Metadata(source_platform="openclaw", emoji="\U0001f525"))
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "IDENTITY.md").read_text()
        assert "\U0001f525" in content

    def test_identity_md_default_emoji(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "IDENTITY.md").read_text()
        assert "\U0001f916" in content

    def test_identity_md_vibe_from_personality(self, tmp_path):
        ir = make_simple_ir(
            persona=Persona(
                system_prompt="Hi",
                personality_notes="Calm and collected\nAlways thorough",
            )
        )
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "IDENTITY.md").read_text()
        assert "Calm and collected" in content


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


class TestNemoClawReadme:
    def test_readme_mentions_agent_name(self, tmp_path):
        ir = make_simple_ir(name="readme-agent")
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "readme-agent" in readme

    def test_readme_mentions_nemoclaw(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "NemoClaw" in readme

    def test_readme_mentions_agentshift(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "AgentShift" in readme


# ---------------------------------------------------------------------------
# No raw Python reprs
# ---------------------------------------------------------------------------


class TestNoRawPythonReprs:
    def test_no_python_repr_in_any_output(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        for f in [
            "workspace/SKILL.md",
            "workspace/SOUL.md",
            "workspace/IDENTITY.md",
            "nemoclaw-config.yaml",
            "network-policy.yaml",
            "deploy.sh",
            "README.md",
        ]:
            content = (tmp_path / f).read_text()
            assert "<agentshift." not in content
            assert "object at 0x" not in content


# ---------------------------------------------------------------------------
# Real skills (skipped if not installed)
# ---------------------------------------------------------------------------


class TestNemoClawRealSkills:
    _GITHUB_SKILL = (
        Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
    )
    _SLACK_SKILL = (
        Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/slack"
    )
    _WEATHER_SKILL = (
        Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/weather"
    )

    def test_github_skill_creates_all_files(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(self._GITHUB_SKILL)
        emit(ir, tmp_path)
        assert (tmp_path / "workspace" / "SKILL.md").exists()
        assert (tmp_path / "nemoclaw-config.yaml").exists()
        assert (tmp_path / "network-policy.yaml").exists()
        assert (tmp_path / "deploy.sh").exists()

    def test_slack_skill_creates_all_files(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._SLACK_SKILL.exists():
            pytest.skip("slack skill not installed")
        ir = parse_skill_dir(self._SLACK_SKILL)
        emit(ir, tmp_path)
        assert (tmp_path / "workspace" / "SKILL.md").exists()
        assert (tmp_path / "nemoclaw-config.yaml").exists()

    def test_weather_skill_creates_all_files(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._WEATHER_SKILL.exists():
            pytest.skip("weather skill not installed")
        ir = parse_skill_dir(self._WEATHER_SKILL)
        emit(ir, tmp_path)
        assert (tmp_path / "workspace" / "SKILL.md").exists()
        assert (tmp_path / "nemoclaw-config.yaml").exists()


# ---------------------------------------------------------------------------
# Round-trip: openclaw → IR → nemoclaw
# ---------------------------------------------------------------------------


class TestNemoClawRoundTrip:
    _GITHUB_SKILL = (
        Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
    )

    def test_openclaw_to_ir_to_nemoclaw_skill_md_has_content(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not self._GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(self._GITHUB_SKILL)
        emit(ir, tmp_path)
        content = (tmp_path / "workspace" / "SKILL.md").read_text()
        assert len(content) > 100
        assert ir.name in content
