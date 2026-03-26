"""Tests for the M365 Declarative Agent emitter — IR → declarative-agent.json + manifest.json"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agentshift.emitters.m365 import emit
from agentshift.ir import (
    AgentIR,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
)

FIXTURES = Path(__file__).parent / "fixtures"

_GITHUB_SKILL = Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/github"
_WEATHER_SKILL = (
    Path.home() / ".nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/weather"
)


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-agent",
        description="A test agent for AgentShift M365",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------


class TestM365FileCreation:
    def test_creates_declarative_agent_json(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        assert (tmp_path / "declarative-agent.json").exists()

    def test_creates_manifest_json(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        assert (tmp_path / "manifest.json").exists()

    def test_creates_readme_md(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        assert (tmp_path / "README.md").exists()

    def test_creates_output_directory_if_missing(self, tmp_path):
        target = tmp_path / "deep" / "nested"
        assert not target.exists()
        emit(make_simple_ir(), target)
        assert target.exists()

    def test_no_full_instructions_for_short_prompt(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        assert not (tmp_path / "instructions-full.txt").exists()

    def test_creates_full_instructions_for_long_prompt(self, tmp_path):
        long_prompt = "This is a sentence. " * 500  # ~10,000 chars
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        assert (tmp_path / "instructions-full.txt").exists()


# ---------------------------------------------------------------------------
# Valid JSON
# ---------------------------------------------------------------------------


class TestM365ValidJson:
    def test_declarative_agent_is_valid_json(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        raw = (tmp_path / "declarative-agent.json").read_text()
        doc = json.loads(raw)  # must not raise
        assert isinstance(doc, dict)

    def test_manifest_is_valid_json(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        raw = (tmp_path / "manifest.json").read_text()
        doc = json.loads(raw)  # must not raise
        assert isinstance(doc, dict)


# ---------------------------------------------------------------------------
# declarative-agent.json fields
# ---------------------------------------------------------------------------


class TestDeclarativeAgentFields:
    def test_has_schema_field(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert "$schema" in doc
        assert "declarative-agent" in doc["$schema"]

    def test_schema_url_correct(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert doc["$schema"] == (
            "https://developer.microsoft.com/json-schemas/"
            "copilot/declarative-agent/v1.4/schema.json"
        )

    def test_has_version_v1_4(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert doc["version"] == "v1.4"

    def test_name_matches_ir(self, tmp_path):
        ir = make_simple_ir(name="my-cool-agent")
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert doc["name"] == "my-cool-agent"

    def test_description_matches_ir(self, tmp_path):
        ir = make_simple_ir(description="An agent that does cool things")
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert doc["description"] == "An agent that does cool things"

    def test_description_truncated_to_1000_chars(self, tmp_path):
        ir = make_simple_ir(description="x" * 1500)
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert len(doc["description"]) <= 1000

    def test_instructions_contains_system_prompt(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="You are a test bot."))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert "You are a test bot." in doc["instructions"]

    def test_instructions_within_8000_chars(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="Short prompt."))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert len(doc["instructions"]) <= 8000

    def test_long_instructions_truncated_to_8000(self, tmp_path):
        long_prompt = "This is a sentence. " * 500  # ~10,000 chars
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert len(doc["instructions"]) <= 8000

    def test_long_instructions_has_truncation_notice(self, tmp_path):
        long_prompt = "This is a sentence. " * 500
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert "AGENTSHIFT" in doc["instructions"]
        assert "truncated" in doc["instructions"].lower()

    def test_full_instructions_file_contains_original(self, tmp_path):
        long_prompt = "This is a sentence. " * 500
        ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
        emit(ir, tmp_path)
        full = (tmp_path / "instructions-full.txt").read_text()
        assert full.strip() == long_prompt.strip()

    def test_no_prompt_falls_back_to_description(self, tmp_path):
        ir = make_simple_ir(
            description="Description fallback text",
            persona=Persona(system_prompt=None),
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert "Description fallback text" in doc["instructions"]


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class TestM365Capabilities:
    def test_teams_mcp_tool_maps_to_teams_messages(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="teams", description="Microsoft Teams", kind="mcp")])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        assert any(c.get("name") == "TeamsMessages" for c in caps)

    def test_email_mcp_tool_maps_to_email(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="email", description="Email tool", kind="mcp")])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        assert any(c.get("name") == "Email" for c in caps)

    def test_graph_mcp_tool_maps_to_graph_connectors(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="graph", description="MS Graph", kind="mcp")])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        assert any(c.get("name") == "GraphConnectors" for c in caps)

    def test_notion_mcp_tool_maps_to_graph_connectors(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="notion", description="Notion MCP", kind="mcp")])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        assert any(c.get("name") == "GraphConnectors" for c in caps)

    def test_unknown_mcp_tool_dropped(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="custom-mcp", description="Custom MCP", kind="mcp")])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        # custom-mcp has no M365 mapping, so no capabilities generated from it
        assert not any(c.get("name") == "custom-mcp" for c in caps)

    def test_url_knowledge_maps_to_websearch(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[
                KnowledgeSource(
                    name="docs",
                    kind="url",
                    path="https://example.com/docs",
                )
            ]
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        ws = next((c for c in caps if c.get("name") == "WebSearch"), None)
        assert ws is not None
        assert any(s["url"] == "https://example.com/docs" for s in ws.get("sites", []))

    def test_shell_tool_with_curl_maps_to_websearch(self, tmp_path):
        ir = make_simple_ir(
            tools=[Tool(name="curl", description="HTTP requests via curl", kind="shell")]
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        assert any(c.get("name") == "WebSearch" for c in caps)

    def test_shell_tool_without_web_dropped(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="jq", description="JSON processor", kind="shell")])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        # jq has no web access, so no capability mapped
        assert not any(c.get("name") == "jq" for c in caps)

    def test_no_tools_no_capabilities_key(self, tmp_path):
        ir = make_simple_ir(tools=[], knowledge=[])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        # capabilities key should be absent when empty
        assert "capabilities" not in doc or doc["capabilities"] == []

    def test_no_duplicate_websearch_capability(self, tmp_path):
        ir = make_simple_ir(
            tools=[Tool(name="curl", description="curl", kind="shell")],
            knowledge=[KnowledgeSource(name="site", kind="url", path="https://example.com")],
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        ws_caps = [c for c in caps if c.get("name") == "WebSearch"]
        assert len(ws_caps) == 1


# ---------------------------------------------------------------------------
# manifest.json fields
# ---------------------------------------------------------------------------


class TestManifestFields:
    def test_has_schema_field(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert "$schema" in doc
        assert "MicrosoftTeams.schema.json" in doc["$schema"]

    def test_schema_url_correct(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert doc["$schema"] == (
            "https://developer.microsoft.com/json-schemas/teams/v1.17/MicrosoftTeams.schema.json"
        )

    def test_manifest_version_is_1_17(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert doc["manifestVersion"] == "1.17"

    def test_has_valid_uuid(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert "id" in doc
        # Must be a valid UUID4
        _uuid = doc["id"]
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            _uuid,
        ), f"Not a valid UUID4: {_uuid}"

    def test_uuid_is_unique_per_emission(self, tmp_path):
        path_a = tmp_path / "a"
        path_b = tmp_path / "b"
        emit(make_simple_ir(), path_a)
        emit(make_simple_ir(), path_b)
        id_a = json.loads((path_a / "manifest.json").read_text())["id"]
        id_b = json.loads((path_b / "manifest.json").read_text())["id"]
        assert id_a != id_b

    def test_name_short_matches_ir(self, tmp_path):
        ir = make_simple_ir(name="My Agent")
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert doc["name"]["short"] == "My Agent"

    def test_name_full_is_description_truncated(self, tmp_path):
        ir = make_simple_ir(description="A" * 200)
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert len(doc["name"]["full"]) <= 100

    def test_description_short_truncated_to_80(self, tmp_path):
        ir = make_simple_ir(description="x" * 200)
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert len(doc["description"]["short"]) <= 80

    def test_description_full_truncated_to_4000(self, tmp_path):
        ir = make_simple_ir(description="x" * 5000)
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert len(doc["description"]["full"]) <= 4000

    def test_references_declarative_agent_json(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        agents = doc["copilotAgents"]["declarativeAgents"]
        assert any(a.get("file") == "declarative-agent.json" for a in agents)

    def test_accent_color_is_teams_purple(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert doc["accentColor"] == "#6264A7"

    def test_icons_fields_present(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert doc["icons"]["color"] == "color.png"
        assert doc["icons"]["outline"] == "outline.png"

    def test_permissions_field_present(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert "identity" in doc["permissions"]
        assert "messageTeamMembers" in doc["permissions"]

    def test_valid_domains_is_list(self, tmp_path):
        emit(make_simple_ir(), tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        assert isinstance(doc["validDomains"], list)


# ---------------------------------------------------------------------------
# No Python reprs in output
# ---------------------------------------------------------------------------


class TestNoRawPythonReprs:
    def test_no_python_repr_in_declarative_agent(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="teams", description="Teams MCP", kind="mcp")])
        emit(ir, tmp_path)
        raw = (tmp_path / "declarative-agent.json").read_text()
        assert "<agentshift." not in raw
        assert "object at 0x" not in raw

    def test_no_python_repr_in_manifest(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="teams", description="Teams MCP", kind="mcp")])
        emit(ir, tmp_path)
        raw = (tmp_path / "manifest.json").read_text()
        assert "<agentshift." not in raw
        assert "object at 0x" not in raw

    def test_no_python_repr_in_readme(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="jq", description="JSON processor", kind="shell")])
        emit(ir, tmp_path)
        raw = (tmp_path / "README.md").read_text()
        assert "<agentshift." not in raw
        assert "object at 0x" not in raw


# ---------------------------------------------------------------------------
# Conversation starters
# ---------------------------------------------------------------------------


class TestConversationStarters:
    def test_starters_extracted_from_examples_section(self, tmp_path):
        prompt = (
            "You are an agent.\n\n"
            "## Examples\n"
            "- Summarize my emails\n"
            "- Find recent Teams messages\n"
        )
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        starters = doc.get("conversation_starters", [])
        assert len(starters) >= 1
        texts = [s["text"] for s in starters]
        assert any("email" in t.lower() or "Teams" in t for t in texts)

    def test_starters_max_6(self, tmp_path):
        bullets = "\n".join(f"- Item {i}" for i in range(20))
        prompt = f"You are an agent.\n\n## Examples\n{bullets}\n"
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        starters = doc.get("conversation_starters", [])
        assert len(starters) <= 6

    def test_starters_have_title_and_text(self, tmp_path):
        prompt = "You are an agent.\n\n## Examples\n- Do something useful\n"
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        for s in doc.get("conversation_starters", []):
            assert "title" in s
            assert "text" in s

    def test_no_starters_key_when_none_found(self, tmp_path):
        ir = make_simple_ir(persona=Persona(system_prompt="You are a plain agent."))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        starters = doc.get("conversation_starters", [])
        assert isinstance(starters, list)


# ---------------------------------------------------------------------------
# Real skills (skipped if not installed)
# ---------------------------------------------------------------------------


class TestM365InstructionTruncationDetailed:
    """More precise instruction truncation edge-case tests."""

    def test_instruction_at_exactly_8000_chars_not_truncated(self, tmp_path):
        prompt = "x" * 8000
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert "AGENTSHIFT" not in doc["instructions"]
        assert not (tmp_path / "instructions-full.txt").exists()

    def test_instruction_at_8001_chars_is_truncated(self, tmp_path):
        prompt = "x" * 8001
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert "AGENTSHIFT" in doc["instructions"]

    def test_truncated_instructions_within_8000(self, tmp_path):
        prompt = "This is a sentence. " * 500  # ~10,000 chars
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert len(doc["instructions"]) <= 8000

    def test_instructions_full_txt_exact_content(self, tmp_path):
        prompt = "This is a sentence. " * 500
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        full = (tmp_path / "instructions-full.txt").read_text()
        assert full.strip() == prompt.strip()

    def test_truncation_notice_contains_m365_limit_text(self, tmp_path):
        prompt = "x" * 9000
        ir = make_simple_ir(persona=Persona(system_prompt=prompt))
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert "8,000" in doc["instructions"] or "truncated" in doc["instructions"].lower()


class TestM365McpCapabilitiesDetailed:
    """More thorough tests for MCP tool → capability mapping."""

    def test_teams_and_email_both_in_capabilities(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="teams", description="Teams", kind="mcp"),
                Tool(name="email", description="Email", kind="mcp"),
            ]
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        cap_names = {c["name"] for c in caps}
        assert "TeamsMessages" in cap_names
        assert "Email" in cap_names

    def test_graph_connectors_has_connections_field(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="graph", description="MS Graph", kind="mcp")])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        gc = next(c for c in caps if c["name"] == "GraphConnectors")
        assert "connections" in gc

    def test_graph_connectors_connection_has_todo_placeholder(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="notion", description="Notion", kind="mcp")])
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        gc = next(c for c in caps if c["name"] == "GraphConnectors")
        connections = gc.get("connections", [])
        assert any("TODO" in str(conn.get("connectionId", "")) for conn in connections)

    def test_graph_connectors_readme_has_setup_note(self, tmp_path):
        ir = make_simple_ir(tools=[Tool(name="graph", description="MS Graph", kind="mcp")])
        emit(ir, tmp_path)
        readme = (tmp_path / "README.md").read_text()
        assert "Graph Connector" in readme or "connection" in readme.lower()

    def test_all_four_mcp_tools_create_capabilities(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(name="teams", description="Teams", kind="mcp"),
                Tool(name="email", description="Email", kind="mcp"),
                Tool(name="graph", description="Graph", kind="mcp"),
                Tool(name="notion", description="Notion", kind="mcp"),
            ]
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        cap_names = {c["name"] for c in caps}
        assert "TeamsMessages" in cap_names
        assert "Email" in cap_names
        assert "GraphConnectors" in cap_names

    def test_no_duplicate_graph_connectors(self, tmp_path):
        # Both graph and notion map to GraphConnectors; should only appear once
        ir = make_simple_ir(
            tools=[
                Tool(name="graph", description="Graph", kind="mcp"),
                Tool(name="notion", description="Notion", kind="mcp"),
            ]
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        gc_caps = [c for c in caps if c["name"] == "GraphConnectors"]
        assert len(gc_caps) == 1


class TestM365WebSearchCapabilityDetailed:
    """More thorough WebSearch capability tests."""

    def test_two_url_knowledge_sources_both_in_sites(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[
                KnowledgeSource(name="docs1", kind="url", path="https://docs1.example.com"),
                KnowledgeSource(name="docs2", kind="url", path="https://docs2.example.com"),
            ]
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        ws = next(c for c in caps if c["name"] == "WebSearch")
        urls = {s["url"] for s in ws.get("sites", [])}
        assert "https://docs1.example.com" in urls
        assert "https://docs2.example.com" in urls

    def test_file_knowledge_does_not_generate_websearch(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[KnowledgeSource(name="guide", kind="file", path="/tmp/guide.md")]
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        assert not any(c["name"] == "WebSearch" for c in caps)

    def test_wget_tool_also_maps_to_websearch(self, tmp_path):
        ir = make_simple_ir(
            tools=[Tool(name="wget", description="Download with wget", kind="shell")]
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        assert any(c["name"] == "WebSearch" for c in caps)

    def test_curl_and_url_knowledge_merge_into_single_websearch(self, tmp_path):
        ir = make_simple_ir(
            tools=[Tool(name="curl", description="HTTP curl", kind="shell")],
            knowledge=[KnowledgeSource(name="site", kind="url", path="https://example.com")],
        )
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        caps = doc.get("capabilities", [])
        ws_caps = [c for c in caps if c["name"] == "WebSearch"]
        assert len(ws_caps) == 1
        # Should have the site merged in
        ws = ws_caps[0]
        assert any(s["url"] == "https://example.com" for s in ws.get("sites", []))


class TestM365RealSkills:
    def test_github_skill_converts(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not _GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(_GITHUB_SKILL)
        emit(ir, tmp_path)
        assert (tmp_path / "declarative-agent.json").exists()
        assert (tmp_path / "manifest.json").exists()

    def test_github_skill_declarative_agent_valid_json(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not _GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(_GITHUB_SKILL)
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert doc["version"] == "v1.4"
        assert doc["name"] == ir.name

    def test_github_skill_instructions_within_limit(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not _GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(_GITHUB_SKILL)
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "declarative-agent.json").read_text())
        assert len(doc["instructions"]) <= 8000

    def test_github_skill_manifest_has_valid_uuid(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not _GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(_GITHUB_SKILL)
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        _id = doc["id"]
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            _id,
        )

    def test_github_skill_manifest_references_agent(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not _GITHUB_SKILL.exists():
            pytest.skip("github skill not installed")
        ir = parse_skill_dir(_GITHUB_SKILL)
        emit(ir, tmp_path)
        doc = json.loads((tmp_path / "manifest.json").read_text())
        agents = doc["copilotAgents"]["declarativeAgents"]
        assert any(a.get("file") == "declarative-agent.json" for a in agents)

    def test_weather_skill_converts(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not _WEATHER_SKILL.exists():
            pytest.skip("weather skill not installed")
        ir = parse_skill_dir(_WEATHER_SKILL)
        emit(ir, tmp_path)
        assert (tmp_path / "declarative-agent.json").exists()
        assert (tmp_path / "manifest.json").exists()

    def test_weather_skill_no_python_reprs(self, tmp_path):
        from agentshift.parsers.openclaw import parse_skill_dir

        if not _WEATHER_SKILL.exists():
            pytest.skip("weather skill not installed")
        ir = parse_skill_dir(_WEATHER_SKILL)
        emit(ir, tmp_path)
        for fname in ["declarative-agent.json", "manifest.json", "README.md"]:
            raw = (tmp_path / fname).read_text()
            assert "<agentshift." not in raw, f"Python repr found in {fname}"
            assert "object at 0x" not in raw, f"Python repr found in {fname}"
