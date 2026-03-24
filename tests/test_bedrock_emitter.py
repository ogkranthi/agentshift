"""Tests for the Bedrock emitter — IR → instruction.txt + openapi.json + cloudformation.yaml"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentshift.emitters.bedrock import emit
from agentshift.ir import (
    AgentIR,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
)

FIXTURES = Path(__file__).parent / "fixtures"


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-skill",
        description="A test skill for AgentShift Bedrock",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


# ---------------------------------------------------------------------------
# Basic file creation
# ---------------------------------------------------------------------------


class TestBedrockEmitterBasic:
    def test_creates_instruction_txt(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "instruction.txt").exists()

    def test_creates_openapi_json(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "openapi.json").exists()

    def test_creates_cloudformation_yaml(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "cloudformation.yaml").exists()

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
# instruction.txt rules
# ---------------------------------------------------------------------------


class TestBedrockInstructionTxt:
    def test_instruction_contains_system_prompt(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="You are a test bot."))
        emit(ir, tmp_path)
        content = (tmp_path / "instruction.txt").read_text()
        assert "You are a test bot." in content

    def test_short_instruction_not_truncated(self, tmp_path):
        prompt = "You are a helpful assistant."
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        content = (tmp_path / "instruction.txt").read_text()
        assert len(content) <= 4000
        assert "AGENTSHIFT" not in content

    def test_short_instruction_no_full_file(self, tmp_path):
        prompt = "You are a helpful assistant."
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        assert not (tmp_path / "instruction-full.txt").exists()

    def test_long_instruction_truncated(self, tmp_path):
        # Create a prompt well over 4000 chars
        long_prompt = "This is a sentence. " * 300  # ~6000 chars
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        content = (tmp_path / "instruction.txt").read_text()
        assert len(content) <= 4000

    def test_long_instruction_has_truncation_notice(self, tmp_path):
        long_prompt = "This is a sentence. " * 300
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        content = (tmp_path / "instruction.txt").read_text()
        assert "AGENTSHIFT" in content
        assert "truncated" in content.lower()

    def test_long_instruction_creates_full_file(self, tmp_path):
        long_prompt = "This is a sentence. " * 300
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        assert (tmp_path / "instruction-full.txt").exists()

    def test_long_instruction_full_file_untruncated(self, tmp_path):
        long_prompt = "This is a sentence. " * 300
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        full = (tmp_path / "instruction-full.txt").read_text()
        assert full.strip() == long_prompt.strip()

    def test_truncation_notice_contains_original_length(self, tmp_path):
        long_prompt = "This is a sentence. " * 300
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        content = (tmp_path / "instruction.txt").read_text()
        assert str(len(long_prompt.strip())) in content

    def test_no_prompt_falls_back_to_description(self, tmp_path):
        ir = make_simple_ir(
            description="A fallback description agent",
            persona=Persona(system_prompt=None),
        )
        emit(ir, tmp_path)
        content = (tmp_path / "instruction.txt").read_text()
        assert "fallback description" in content


# ---------------------------------------------------------------------------
# openapi.json rules
# ---------------------------------------------------------------------------


class TestBedrockOpenApiJson:
    def test_openapi_json_is_valid_json(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        raw = (tmp_path / "openapi.json").read_text()
        schema = json.loads(raw)  # must not raise
        assert isinstance(schema, dict)

    def test_openapi_version_field(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert schema["openapi"] == "3.0.0"

    def test_openapi_info_field(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert "info" in schema
        assert "title" in schema["info"]
        assert "version" in schema["info"]

    def test_openapi_paths_field_exists(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert "paths" in schema

    def test_shell_tool_appears_as_run_path(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert "/gh/run" in schema["paths"]

    def test_mcp_tool_appears_as_action_path(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="slack", description="Slack MCP", kind="mcp")])
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert "/slack/action" in schema["paths"]

    def test_shell_tool_path_uses_post(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert "post" in schema["paths"]["/gh/run"]

    def test_shell_tool_has_stub_marker(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert schema["paths"]["/gh/run"]["post"].get("x-agentshift-stub") is True

    def test_mcp_tool_has_stub_marker(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="slack", description="Slack MCP", kind="mcp")])
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert schema["paths"]["/slack/action"]["post"].get("x-agentshift-stub") is True

    def test_no_tools_produces_empty_paths(self, tmp_path):
        ir = make_simple_ir(tools=[])
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert schema["paths"] == {}

    def test_multiple_tools_all_appear(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="gh", description="GitHub CLI", kind="shell"),
                Tool(name="git", description="Git", kind="shell"),
                Tool(name="slack", description="Slack", kind="mcp"),
            ]
        )
        emit(ir, tmp_path)
        schema = json.loads((tmp_path / "openapi.json").read_text())
        assert "/gh/run" in schema["paths"]
        assert "/git/run" in schema["paths"]
        assert "/slack/action" in schema["paths"]


# ---------------------------------------------------------------------------
# cloudformation.yaml rules
# ---------------------------------------------------------------------------


class TestBedrockCloudFormation:
    def test_cf_has_agent_name_parameter(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "AgentName" in cf

    def test_cf_has_environment_parameter(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "Environment" in cf

    def test_cf_has_agent_role_arn_parameter(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "AgentRoleArn" in cf

    def test_cf_has_bedrock_agent_resource_type(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "AWS::Bedrock::Agent" in cf

    def test_cf_has_bedrock_agent_alias_resource_type(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "AWS::Bedrock::AgentAlias" in cf

    def test_cf_has_foundation_model(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "anthropic.claude-3-5-sonnet-20241022-v2:0" in cf

    def test_cf_has_instruction(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="You are a helpful assistant."))
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "Instruction:" in cf

    def test_cf_has_auto_prepare(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "AutoPrepare: true" in cf

    def test_cf_shell_tool_creates_action_group(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "ActionGroups" in cf
        assert "github-gh" in cf or "test-skill-gh" in cf

    def test_cf_knowledge_source_creates_kb_entry(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[KnowledgeSource(name="pregnancy-guide", kind="file", path="/tmp/guide.md")]
        )
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "KnowledgeBases" in cf

    def test_cf_knowledge_source_has_todo_comment(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[KnowledgeSource(name="pregnancy-guide", kind="file", path="/tmp/guide.md")]
        )
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "TODO" in cf
        assert "kb-PLACEHOLDER-TODO" in cf

    def test_cf_has_outputs(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "Outputs:" in cf
        assert "AgentId" in cf
        assert "AliasId" in cf

    def test_cf_mcp_tool_has_todo_comment(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="slack", description="Slack MCP", kind="mcp")])
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "TODO [agentshift]" in cf
        assert "slack" in cf

    def test_cf_long_instruction_has_warning_comment(self, tmp_path):
        long_prompt = "This is a sentence. " * 300
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "WARNING" in cf

    def test_cf_agent_alias_name_is_live(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "AgentAliasName: live" in cf

    def test_cf_has_agent_name_sub(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "!Sub" in cf


# ---------------------------------------------------------------------------
# README rules
# ---------------------------------------------------------------------------


class TestBedrockReadme:
    def test_readme_mentions_agent_name(self, tmp_path):
        ir = make_simple_ir(name="my-agent")
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "my-agent" in readme

    def test_readme_mentions_agentshift(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "AgentShift" in readme or "agentshift" in readme.lower()

    def test_readme_has_deploy_command(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "aws cloudformation deploy" in readme

    def test_readme_deploy_command_has_stack_name(self, tmp_path):
        ir = make_simple_ir(name="my-agent")
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "agentshift-my-agent" in readme

    def test_readme_mentions_prerequisites(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "Prerequisites" in readme or "IAM" in readme

    def test_readme_mentions_lambda_when_tools(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "Lambda" in readme

    def test_readme_mentions_knowledge_base_when_knowledge(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[KnowledgeSource(name="guide", kind="file", path="/tmp/guide.md")]
        )
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "Knowledge" in readme

    def test_readme_has_agentshift_link(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "agentshift.sh" in readme


# ---------------------------------------------------------------------------
# No raw Python reprs
# ---------------------------------------------------------------------------


class TestNoRawPythonReprs:
    def test_no_python_repr_in_instruction(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        content = (tmp_path / "instruction.txt").read_text()
        assert "<agentshift." not in content
        assert "object at 0x" not in content

    def test_no_python_repr_in_cloudformation(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "<agentshift." not in cf
        assert "object at 0x" not in cf

    def test_no_python_repr_in_openapi(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        openapi = (tmp_path / "openapi.json").read_text()
        assert "<agentshift." not in openapi
        assert "object at 0x" not in openapi

    def test_no_python_repr_in_readme(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="gh", description="GitHub CLI", kind="shell")])
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "<agentshift." not in readme
        assert "object at 0x" not in readme


# ---------------------------------------------------------------------------
# Real skills (skipped if not installed)
# ---------------------------------------------------------------------------


class TestBedrockRealSkills:
    def test_github_skill_converts(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
        if not skill.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)

        assert (tmp_path / "instruction.txt").exists()
        assert (tmp_path / "openapi.json").exists()
        assert (tmp_path / "cloudformation.yaml").exists()
        assert (tmp_path / "README.md").exists()

    def test_github_skill_instruction_within_limit(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
        if not skill.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)

        content = (tmp_path / "instruction.txt").read_text()
        assert len(content) <= 4000

    def test_github_skill_openapi_is_valid_json(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
        if not skill.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)

        raw = (tmp_path / "openapi.json").read_text()
        schema = json.loads(raw)
        assert schema["openapi"] == "3.0.0"

    def test_github_skill_cloudformation_has_bedrock_agent(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
        if not skill.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)

        cf = (tmp_path / "cloudformation.yaml").read_text()
        assert "AWS::Bedrock::Agent" in cf
        assert "AWS::Bedrock::AgentAlias" in cf

    def test_github_skill_shell_tools_in_openapi(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
        if not skill.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)

        schema = json.loads((tmp_path / "openapi.json").read_text())
        shell_tools = [t for t in ir.tools if t.kind == "shell"]
        for tool in shell_tools:
            assert f"/{tool.name}/run" in schema["paths"]


class TestBedrockCloudFormationYAMLValidity:
    """CloudFormation YAML must parse with CF-aware loader (handles !Ref, !GetAtt)."""

    def _cf_load(self, path):
        import yaml

        class CFLoader(yaml.SafeLoader):
            pass

        def cf_constructor(loader, tag_suffix, node):
            return f"{tag_suffix} {loader.construct_scalar(node)}"

        CFLoader.add_multi_constructor("!", cf_constructor)
        with open(path) as f:
            return yaml.load(f, Loader=CFLoader)

    def test_cloudformation_yaml_valid(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = self._cf_load(tmp_path / "cloudformation.yaml")
        assert "Resources" in data
        assert "Parameters" in data
        assert "Outputs" in data

    def test_cloudformation_has_agent_resource(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = self._cf_load(tmp_path / "cloudformation.yaml")
        resources = data["Resources"]
        agent_keys = [k for k in resources if "Agent" in k and "Alias" not in k]
        assert len(agent_keys) == 1

    def test_cloudformation_descriptions_no_yaml_colons(self, tmp_path):
        """Parameter descriptions with colons must be quoted."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        # If this parses without error, descriptions are properly quoted
        data = self._cf_load(tmp_path / "cloudformation.yaml")
        params = data["Parameters"]
        assert "AgentName" in params
        assert "Environment" in params
        assert "AgentRoleArn" in params

    def test_github_skill_cloudformation_valid(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
        if not skill.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)
        data = self._cf_load(tmp_path / "cloudformation.yaml")
        assert "GithubAgent" in data["Resources"]

    def test_pregnancy_cloudformation_valid(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        skill = Path.home() / ".openclaw/skills/pregnancy-companion"
        if not skill.exists():
            pytest.skip("pregnancy-companion not installed")
        ir = parse_skill_dir(skill)
        emit(ir, tmp_path)
        data = self._cf_load(tmp_path / "cloudformation.yaml")
        assert "Resources" in data
