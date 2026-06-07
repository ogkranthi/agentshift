"""Tests for the AutoGen emitter — IR → agent_config.json + tools.py + run.py +
requirements.txt + README.md"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentshift.emitters.autogen import emit
from agentshift.ir import (
    AgentIR,
    Constraints,
    Metadata,
    Persona,
    Tool,
    Trigger,
)

FIXTURES = Path(__file__).parent / "fixtures"
PREGNANCY = FIXTURES / "pregnancy-companion"

OUTPUT_FILES = {
    "agent_config.json",
    "tools.py",
    "run.py",
    "requirements.txt",
    "README.md",
}


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-agent",
        description="A test agent for AgentShift AutoGen emitter",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


# ---------------------------------------------------------------------------
# T22-1: Basic emit — all 5 output files exist
# ---------------------------------------------------------------------------


def test_autogen_basic_emit(tmp_path):
    """All 5 expected output files are created."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"Missing output file: {fname}"


# ---------------------------------------------------------------------------
# T22-2: agent_config.json — JSON schema validation
# ---------------------------------------------------------------------------


def test_agent_config_json_is_valid_json(tmp_path):
    """agent_config.json is valid JSON."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent_config.json").read_text()
    data = json.loads(content)  # must not raise
    assert isinstance(data, dict)


def test_agent_config_json_has_provider(tmp_path):
    """agent_config.json has 'provider' key at top level."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    assert "provider" in data
    assert "RoundRobinGroupChat" in data["provider"]


def test_agent_config_json_component_type_is_team(tmp_path):
    """agent_config.json component_type is 'team'."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    assert data.get("component_type") == "team"


def test_agent_config_json_has_version(tmp_path):
    """agent_config.json has version field."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    assert "version" in data
    assert data["version"] == 1


def test_agent_config_json_has_label(tmp_path):
    """agent_config.json has label field (PascalCase team name)."""
    ir = make_simple_ir(name="my-agent")
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    assert "label" in data
    # Label should be PascalCase
    assert "MyAgent" in data["label"]


def test_agent_config_json_has_config(tmp_path):
    """agent_config.json has 'config' key."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    assert "config" in data
    assert isinstance(data["config"], dict)


def test_agent_config_json_has_participants(tmp_path):
    """agent_config.json config has participants list."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participants = data["config"]["participants"]
    assert isinstance(participants, list)
    assert len(participants) >= 1


def test_agent_config_json_participant_is_assistant_agent(tmp_path):
    """The participant is an AssistantAgent."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    assert "AssistantAgent" in participant["provider"]


def test_agent_config_json_participant_has_name(tmp_path):
    """Participant config has a name field (snake_case agent name)."""
    ir = make_simple_ir(name="my-agent")
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    assert participant["config"]["name"] == "my_agent"


def test_agent_config_json_has_system_message(tmp_path):
    """Participant config includes system_message."""
    ir = make_simple_ir(persona=Persona(system_prompt="You are a pregnancy companion."))
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    system_msg = participant["config"]["system_message"]
    assert "pregnancy companion" in system_msg


def test_agent_config_json_system_message_has_terminate(tmp_path):
    """System message includes TERMINATE instruction for AutoGen convention."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    system_msg = participant["config"]["system_message"]
    assert "TERMINATE" in system_msg


def test_agent_config_json_has_model_client(tmp_path):
    """Participant config includes model_client."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    assert "model_client" in participant["config"]


def test_agent_config_json_default_model_is_gpt4o(tmp_path):
    """Default model in agent_config.json is gpt-4o."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    model = participant["config"]["model_client"]["config"]["model"]
    assert model == "gpt-4o"


def test_agent_config_json_custom_model(tmp_path):
    """Custom model from platform_extensions is used."""
    ir = make_simple_ir(
        metadata=Metadata(
            source_platform="openclaw",
            platform_extensions={"autogen": {"model": "gpt-4-turbo"}},
        )
    )
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    model = participant["config"]["model_client"]["config"]["model"]
    assert model == "gpt-4-turbo"


def test_agent_config_json_has_termination_condition(tmp_path):
    """agent_config.json has termination_condition in config."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    assert "termination_condition" in data["config"]


def test_agent_config_json_termination_uses_text_mention(tmp_path):
    """Termination condition is TextMentionTermination."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    term = data["config"]["termination_condition"]
    assert "TextMentionTermination" in term["provider"]
    assert term["config"]["text"] == "TERMINATE"


def test_agent_config_json_has_model_context(tmp_path):
    """Participant config includes model_context."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    assert "model_context" in participant["config"]


def test_agent_config_json_tools_list_empty_by_default(tmp_path):
    """Participant config has empty tools list when no tools defined."""
    ir = make_simple_ir(tools=[])
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    assert participant["config"]["tools"] == []


def test_agent_config_json_function_tools_appear(tmp_path):
    """Function tools appear in participant config tools list."""
    ir = make_simple_ir(
        tools=[Tool(name="my-func", description="A function tool", kind="function")]
    )
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    tools = participant["config"]["tools"]
    assert len(tools) >= 1
    assert any("FunctionTool" in t["provider"] for t in tools)


def test_agent_config_json_mcp_tools_use_mcp_adapter(tmp_path):
    """MCP tools use StdioMCPToolAdapter provider."""
    ir = make_simple_ir(
        tools=[
            Tool(
                name="slack-mcp",
                description="Slack via MCP",
                kind="mcp",
                endpoint="@modelcontextprotocol/slack",
            )
        ]
    )
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    tools = participant["config"]["tools"]
    assert len(tools) >= 1
    assert any("MCP" in t["provider"] for t in tools)


def test_agent_config_json_builtin_tools_excluded(tmp_path):
    """Builtin tools are excluded from agent_config.json tools list."""
    ir = make_simple_ir(
        tools=[
            Tool(name="builtin-tool", description="A builtin", kind="builtin"),
            Tool(name="custom", description="Custom tool", kind="function"),
        ]
    )
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    tools = participant["config"]["tools"]
    # Only 1 tool (custom), not the builtin
    assert len(tools) == 1


def test_agent_config_json_guardrails_in_system_message(tmp_path):
    """Guardrails from constraints are included in system_message."""
    ir = make_simple_ir(
        constraints=Constraints(guardrails=["Never reveal passwords"])
    )
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    system_msg = participant["config"]["system_message"]
    assert "Never reveal passwords" in system_msg


def test_agent_config_json_topic_restrictions_in_system_message(tmp_path):
    """Topic restrictions appear in system_message."""
    ir = make_simple_ir(
        constraints=Constraints(topic_restrictions=["illegal activities"])
    )
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    system_msg = participant["config"]["system_message"]
    assert "illegal activities" in system_msg


def test_agent_config_json_component_version(tmp_path):
    """agent_config.json has component_version field."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    assert "component_version" in data


def test_agent_config_json_pretty_printed(tmp_path):
    """agent_config.json is pretty-printed (indented)."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent_config.json").read_text()
    # Pretty-printed JSON has newlines
    assert "\n" in content


# ---------------------------------------------------------------------------
# T22-3: tools.py structure
# ---------------------------------------------------------------------------


def test_tools_py_has_stubs_for_function_tools(tmp_path):
    """tools.py has function stubs for function-kind tools."""
    ir = make_simple_ir(
        tools=[Tool(name="my-tool", description="Does something", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "def my_tool" in content


def test_tools_py_snake_case_names(tmp_path):
    """tools.py uses snake_case for function names."""
    ir = make_simple_ir(
        tools=[Tool(name="get-weather-data", description="Get weather", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "def get_weather_data" in content


def test_tools_py_has_todo_comment(tmp_path):
    """tools.py includes TODO comment for stubs."""
    ir = make_simple_ir(
        tools=[Tool(name="my-func", description="A function", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "TODO" in content


def test_tools_py_has_not_implemented_error(tmp_path):
    """tools.py raises NotImplementedError for stubs."""
    ir = make_simple_ir(
        tools=[Tool(name="my-func", description="A function", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "NotImplementedError" in content


def test_tools_py_no_tools_comment(tmp_path):
    """tools.py has a comment when no tools are defined."""
    ir = make_simple_ir(tools=[])
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "No tools" in content or "no tools" in content.lower()


def test_tools_py_mcp_tools_excluded_from_stubs(tmp_path):
    """MCP tools don't generate Python function stubs in tools.py."""
    ir = make_simple_ir(
        tools=[
            Tool(name="mcp-tool", description="MCP tool", kind="mcp"),
            Tool(name="func-tool", description="Function tool", kind="function"),
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "def func_tool" in content
    assert "def mcp_tool" not in content


def test_tools_py_typed_parameters(tmp_path):
    """tools.py generates typed parameters from JSON schema."""
    ir = make_simple_ir(
        tools=[
            Tool(
                name="create-item",
                description="Create an item",
                kind="function",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "qty": {"type": "integer"},
                        "price": {"type": "number"},
                    },
                    "required": ["name"],
                },
            )
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "name: str" in content
    assert "qty: int" in content
    assert "price: float" in content


def test_tools_py_optional_params_have_none_default(tmp_path):
    """Optional (non-required) parameters get `| None = None` default."""
    ir = make_simple_ir(
        tools=[
            Tool(
                name="search",
                description="Search",
                kind="function",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "page": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            )
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "page: int | None = None" in content


def test_tools_py_no_params_defaults_to_input_str(tmp_path):
    """Function tools with no parameters get `input: str` as default signature."""
    ir = make_simple_ir(
        tools=[Tool(name="my-tool", description="No params tool", kind="function", parameters=None)]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "input: str" in content


# ---------------------------------------------------------------------------
# T22-4: run.py structure
# ---------------------------------------------------------------------------


def test_run_py_imports_asyncio(tmp_path):
    """run.py imports asyncio."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "run.py").read_text()
    assert "import asyncio" in content


def test_run_py_imports_autogen(tmp_path):
    """run.py imports from autogen_agentchat."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "run.py").read_text()
    assert "autogen_agentchat" in content


def test_run_py_loads_agent_config(tmp_path):
    """run.py loads agent_config.json."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "run.py").read_text()
    assert "agent_config.json" in content


def test_run_py_has_async_main(tmp_path):
    """run.py defines async main() function."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "run.py").read_text()
    assert "async def main" in content


def test_run_py_has_asyncio_run(tmp_path):
    """run.py calls asyncio.run(main())."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "run.py").read_text()
    assert "asyncio.run(main())" in content


# ---------------------------------------------------------------------------
# T22-5: requirements.txt
# ---------------------------------------------------------------------------


def test_requirements_includes_autogen_agentchat(tmp_path):
    """requirements.txt includes autogen-agentchat."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "autogen-agentchat" in content


def test_requirements_includes_autogen_ext(tmp_path):
    """requirements.txt includes autogen-ext."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "autogen-ext" in content


def test_requirements_includes_mcp_for_mcp_tools(tmp_path):
    """requirements.txt includes autogen-ext[mcp] when MCP tools are present."""
    ir = make_simple_ir(
        tools=[Tool(name="my-mcp", description="MCP tool", kind="mcp")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "mcp" in content


# ---------------------------------------------------------------------------
# T22-6: README.md
# ---------------------------------------------------------------------------


def test_readme_mentions_agent_name(tmp_path):
    """README.md mentions the agent name."""
    ir = make_simple_ir(name="my-autogen-agent")
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "my-autogen-agent" in content


def test_readme_mentions_agentshift(tmp_path):
    """README.md mentions AgentShift."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "AgentShift" in content or "agentshift" in content.lower()


def test_readme_mentions_autogen(tmp_path):
    """README.md mentions AutoGen."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "AutoGen" in content or "autogen" in content.lower()


def test_readme_has_setup_section(tmp_path):
    """README.md has a Setup section."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "Setup" in content


def test_readme_has_openai_key(tmp_path):
    """README.md mentions OPENAI_API_KEY."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "OPENAI_API_KEY" in content


# ---------------------------------------------------------------------------
# T22-7: Output directory creation
# ---------------------------------------------------------------------------


def test_creates_nested_output_directory(tmp_path):
    """emit() creates nested output directory if it doesn't exist."""
    ir = make_simple_ir()
    target = tmp_path / "deep" / "nested" / "dir"
    assert not target.exists()
    emit(ir, target)
    assert target.exists()
    for fname in OUTPUT_FILES:
        assert (target / fname).exists()


# ---------------------------------------------------------------------------
# T22-8: No Python repr / memory addresses in output
# ---------------------------------------------------------------------------


def test_no_python_repr_in_output(tmp_path):
    """No Python object repr or memory addresses appear in output files."""
    ir = make_simple_ir(
        tools=[Tool(name="search", description="Search the web", kind="function")]
    )
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        content = (tmp_path / fname).read_text()
        assert "<agentshift." not in content, f"Python repr in {fname}"
        assert "object at 0x" not in content, f"Memory address in {fname}"


# ---------------------------------------------------------------------------
# T22-9: Long instructions handled without crash
# ---------------------------------------------------------------------------


def test_long_instructions_no_crash(tmp_path):
    """Very long system prompts are handled without crashing."""
    long_prompt = "This is a very long instruction. " * 1000
    ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists()


# ---------------------------------------------------------------------------
# T22-10: autogen registered in CLI _EMITTERS
# ---------------------------------------------------------------------------


def test_autogen_emitter_importable():
    """The AutoGen emitter module is importable and has emit function."""
    from agentshift.emitters import autogen  # noqa: F401
    assert hasattr(autogen, "emit")


# ---------------------------------------------------------------------------
# T22-11: Fixture conversion — pregnancy-companion
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not PREGNANCY.exists(), reason="pregnancy-companion fixture not found")
def test_pregnancy_companion_conversion(tmp_path):
    """Pregnancy-companion fixture converts to AutoGen without error."""
    from agentshift.parsers.openclaw import parse_skill_dir

    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"Missing: {fname}"


@pytest.mark.skipif(not PREGNANCY.exists(), reason="pregnancy-companion fixture not found")
def test_pregnancy_companion_config_json_valid(tmp_path):
    """Pregnancy-companion agent_config.json is valid and well-structured."""
    from agentshift.parsers.openclaw import parse_skill_dir

    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)

    content = (tmp_path / "agent_config.json").read_text()
    data = json.loads(content)

    assert "provider" in data
    assert "config" in data
    assert "participants" in data["config"]
    assert len(data["config"]["participants"]) >= 1


# ---------------------------------------------------------------------------
# T22-12: CLI convert command end-to-end
# ---------------------------------------------------------------------------

_VENV_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "agentshift"
_AGENTSHIFT = (
    [str(_VENV_BIN)] if _VENV_BIN.exists() else [sys.executable, "-m", "agentshift"]
)


@pytest.mark.skipif(not PREGNANCY.exists(), reason="pregnancy-companion fixture not found")
@pytest.mark.skipif(
    "autogen" not in __import__("agentshift.cli", fromlist=["_EMITTERS"])._EMITTERS,
    reason="autogen not yet registered in CLI _EMITTERS",
)
def test_cli_convert_to_autogen(tmp_path):
    """CLI `agentshift convert --to autogen <fixture>` succeeds."""
    result = subprocess.run(
        [
            *_AGENTSHIFT,
            "convert",
            str(PREGNANCY),
            "--from",
            "openclaw",
            "--to",
            "autogen",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"CLI did not create: {fname}"


# ---------------------------------------------------------------------------
# T22-13: Multiple tools in agent_config.json
# ---------------------------------------------------------------------------


def test_multiple_tools_all_appear_in_config(tmp_path):
    """All emittable tools appear in agent_config.json."""
    ir = make_simple_ir(
        tools=[
            Tool(name="search-web", description="Search the web", kind="function"),
            Tool(name="send-email", description="Send an email", kind="function"),
            Tool(name="get-cal", description="Get calendar", kind="openapi"),
        ]
    )
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    tools = participant["config"]["tools"]
    tool_labels = [t.get("label", "") for t in tools]
    assert "search_web" in tool_labels
    assert "send_email" in tool_labels
    assert "get_cal" in tool_labels


def test_tool_description_in_config(tmp_path):
    """Tool description appears in agent_config.json tool component."""
    ir = make_simple_ir(
        tools=[Tool(name="my-tool", description="Does something very specific", kind="function")]
    )
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "agent_config.json").read_text())
    participant = data["config"]["participants"][0]
    tools = participant["config"]["tools"]
    assert any("very specific" in t.get("description", "") for t in tools)
