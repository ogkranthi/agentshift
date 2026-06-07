"""Tests for the OpenAI Agents SDK emitter — IR → agent.py + tools.py + runner.py +
requirements.txt + README.md"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from agentshift.emitters.openai_agents import emit
from agentshift.ir import (
    AgentIR,
    Constraints,
    Metadata,
    Persona,
    Tool,
    ToolAuth,
    Trigger,
)

FIXTURES = Path(__file__).parent / "fixtures"
PREGNANCY = FIXTURES / "pregnancy-companion"

OUTPUT_FILES = {
    "agent.py",
    "tools.py",
    "runner.py",
    "requirements.txt",
    "README.md",
}


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-agent",
        description="A test agent for AgentShift OpenAI Agents emitter",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


# ---------------------------------------------------------------------------
# T20-1: Basic emit — all 5 output files exist
# ---------------------------------------------------------------------------


def test_openai_agents_basic_emit(tmp_path):
    """All 5 expected output files are created."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"Missing output file: {fname}"


# ---------------------------------------------------------------------------
# T20-2: agent.py structure
# ---------------------------------------------------------------------------


def test_agent_py_imports_agent(tmp_path):
    """agent.py imports Agent from agents module."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "from agents import Agent" in content


def test_agent_py_has_agent_instantiation(tmp_path):
    """agent.py contains an Agent(...) instantiation."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "Agent(" in content


def test_agent_py_has_name(tmp_path):
    """agent.py includes the agent name."""
    ir = make_simple_ir(name="my-cool-agent")
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "my-cool-agent" in content


def test_agent_py_has_system_prompt(tmp_path):
    """agent.py includes the system prompt from the IR persona."""
    ir = make_simple_ir(persona=Persona(system_prompt="You are a pregnancy companion."))
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "pregnancy companion" in content


def test_agent_py_has_model(tmp_path):
    """agent.py includes a model specification."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "model=" in content


def test_agent_py_default_model_is_gpt4o(tmp_path):
    """agent.py defaults to gpt-4o model."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "gpt-4o" in content


def test_agent_py_custom_model_from_extensions(tmp_path):
    """agent.py uses model from platform_extensions when set."""
    ir = make_simple_ir(
        metadata=Metadata(
            source_platform="openclaw",
            platform_extensions={"openai-agents": {"model": "gpt-4-turbo"}},
        )
    )
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "gpt-4-turbo" in content


def test_agent_py_has_instructions_key(tmp_path):
    """agent.py includes instructions= keyword."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "instructions=" in content


# ---------------------------------------------------------------------------
# T20-3: tools.py — function tool stubs
# ---------------------------------------------------------------------------


def test_tools_py_imports_function_tool(tmp_path):
    """tools.py imports function_tool from agents."""
    ir = make_simple_ir(
        tools=[Tool(name="search", description="Search the web", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "from agents import function_tool" in content


def test_tools_py_has_decorator(tmp_path):
    """tools.py uses @function_tool decorator for function tools."""
    ir = make_simple_ir(
        tools=[Tool(name="my-tool", description="Does something", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "@function_tool" in content


def test_tools_py_snake_case_function_names(tmp_path):
    """tools.py uses snake_case for function names derived from tool names."""
    ir = make_simple_ir(
        tools=[
            Tool(name="search-web", description="Search the web", kind="function"),
            Tool(name="get-weather", description="Get weather data", kind="function"),
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "search_web" in content
    assert "get_weather" in content


def test_tools_py_has_todo_comment(tmp_path):
    """tools.py includes TODO comment for stub functions."""
    ir = make_simple_ir(
        tools=[Tool(name="my-func", description="A function", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "TODO" in content


def test_tools_py_has_not_implemented_error(tmp_path):
    """tools.py raises NotImplementedError for stub functions."""
    ir = make_simple_ir(
        tools=[Tool(name="my-func", description="A function", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "NotImplementedError" in content


def test_tools_py_shell_tool_uses_subprocess(tmp_path):
    """Shell tools use subprocess.run pattern."""
    ir = make_simple_ir(
        tools=[Tool(name="git", description="Run git commands", kind="shell")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "subprocess" in content
    assert "subprocess.run" in content


def test_tools_py_builtin_tools_excluded(tmp_path):
    """Builtin tools (e.g. 'builtin') are NOT emitted as function stubs."""
    ir = make_simple_ir(
        tools=[
            Tool(name="builtin-tool", description="A builtin", kind="builtin"),
            Tool(name="custom-tool", description="A custom tool", kind="function"),
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    # custom tool should appear, builtin should NOT
    assert "custom_tool" in content
    assert "builtin_tool" not in content


def test_tools_py_typed_parameters(tmp_path):
    """tools.py generates typed parameters from JSON schema."""
    ir = make_simple_ir(
        tools=[
            Tool(
                name="create-task",
                description="Create a task",
                kind="function",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "count": {"type": "integer"},
                        "is_done": {"type": "boolean"},
                    },
                    "required": ["title"],
                },
            )
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "title: str" in content
    assert "count: int" in content
    assert "is_done: bool" in content


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
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            )
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "limit: int | None = None" in content


def test_tools_py_mcp_tool_generates_server_config(tmp_path):
    """MCP tools produce MCPServerStdio config in tools.py."""
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
    content = (tmp_path / "tools.py").read_text()
    assert "MCPServerStdio" in content
    assert "slack-mcp" in content


def test_tools_py_no_tools_still_emits(tmp_path):
    """IR with no tools still produces tools.py without error."""
    ir = make_simple_ir(tools=[])
    emit(ir, tmp_path)  # must not raise
    assert (tmp_path / "tools.py").exists()


# ---------------------------------------------------------------------------
# T20-4: runner.py structure
# ---------------------------------------------------------------------------


def test_runner_py_imports_asyncio(tmp_path):
    """runner.py imports asyncio."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "runner.py").read_text()
    assert "import asyncio" in content


def test_runner_py_imports_runner(tmp_path):
    """runner.py imports Runner from agents."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "runner.py").read_text()
    assert "from agents import Runner" in content


def test_runner_py_has_main_coroutine(tmp_path):
    """runner.py defines an async main() function."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "runner.py").read_text()
    assert "async def main" in content


def test_runner_py_has_asyncio_run(tmp_path):
    """runner.py calls asyncio.run(main())."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "runner.py").read_text()
    assert "asyncio.run(main())" in content


# ---------------------------------------------------------------------------
# T20-5: requirements.txt
# ---------------------------------------------------------------------------


def test_requirements_includes_openai_agents(tmp_path):
    """requirements.txt includes openai-agents dependency."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "openai-agents" in content


def test_requirements_includes_mcp_for_mcp_tools(tmp_path):
    """requirements.txt includes mcp package when MCP tools are present."""
    ir = make_simple_ir(
        tools=[Tool(name="my-mcp", description="MCP tool", kind="mcp")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "mcp" in content


def test_requirements_no_mcp_without_mcp_tools(tmp_path):
    """requirements.txt does NOT include mcp package when no MCP tools exist."""
    ir = make_simple_ir(
        tools=[Tool(name="my-func", description="A function", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    # mcp should not appear as a separate dependency
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.startswith("#")]
    mcp_lines = [l for l in lines if l.startswith("mcp")]
    assert len(mcp_lines) == 0


# ---------------------------------------------------------------------------
# T20-6: README.md
# ---------------------------------------------------------------------------


def test_readme_mentions_agent_name(tmp_path):
    """README.md mentions the agent name."""
    ir = make_simple_ir(name="my-test-agent")
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "my-test-agent" in content


def test_readme_mentions_agentshift(tmp_path):
    """README.md mentions AgentShift."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "AgentShift" in content or "agentshift" in content.lower()


def test_readme_has_setup_section(tmp_path):
    """README.md has a Setup section."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "Setup" in content


def test_readme_has_openai_key_instructions(tmp_path):
    """README.md mentions OPENAI_API_KEY."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "OPENAI_API_KEY" in content


def test_readme_tools_section_lists_tools(tmp_path):
    """README.md lists tools when IR has emittable tools."""
    ir = make_simple_ir(
        tools=[Tool(name="my-func", description="A helpful function", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "my-func" in content


def test_readme_trigger_section_for_non_manual_triggers(tmp_path):
    """README.md notes non-manual triggers."""
    ir = make_simple_ir(
        triggers=[Trigger(id="daily", kind="cron", cron_expr="0 9 * * *")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "cron" in content.lower() or "0 9 * * *" in content


# ---------------------------------------------------------------------------
# T20-7: Guardrails are embedded in instructions
# ---------------------------------------------------------------------------


def test_guardrails_appear_in_agent_py(tmp_path):
    """Guardrails from constraints are included in agent.py system prompt."""
    ir = make_simple_ir(
        constraints=Constraints(guardrails=["Do not reveal internal details"])
    )
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "Do not reveal internal details" in content


def test_topic_restrictions_appear_in_agent_py(tmp_path):
    """Topic restrictions appear in agent.py system prompt."""
    ir = make_simple_ir(
        constraints=Constraints(topic_restrictions=["politics"])
    )
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "politics" in content


# ---------------------------------------------------------------------------
# T20-8: agent.py imports tools when tools exist
# ---------------------------------------------------------------------------


def test_agent_py_imports_tools(tmp_path):
    """agent.py imports tool functions from tools.py when tools exist."""
    ir = make_simple_ir(
        tools=[Tool(name="my-func", description="A function", kind="function")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "from .tools import" in content
    assert "my_func" in content


def test_agent_py_no_tools_no_tools_import(tmp_path):
    """agent.py does NOT import from tools when no tools exist."""
    ir = make_simple_ir(tools=[])
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    # Should not have tools import when there are none
    assert "from .tools import" not in content


# ---------------------------------------------------------------------------
# T20-9: Directory creation
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
# T20-10: No Python repr / memory addresses in output
# ---------------------------------------------------------------------------


def test_no_python_repr_in_output(tmp_path):
    """No Python object repr or memory addresses appear in output files."""
    ir = make_simple_ir(
        tools=[Tool(name="gh", description="GitHub CLI", kind="shell")]
    )
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        content = (tmp_path / fname).read_text()
        assert "<agentshift." not in content, f"Python repr in {fname}"
        assert "object at 0x" not in content, f"Memory address in {fname}"


# ---------------------------------------------------------------------------
# T20-11: Long instructions handled without crash
# ---------------------------------------------------------------------------


def test_long_instructions_no_crash(tmp_path):
    """Very long system prompts are written without crashing."""
    long_prompt = "This is a very long instruction. " * 1000
    ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
    emit(ir, tmp_path)  # must not raise
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists()


# ---------------------------------------------------------------------------
# T20-12: openai_agents emitter module is importable
# ---------------------------------------------------------------------------


def test_openai_agents_emitter_importable():
    """The OpenAI Agents emitter module is importable."""
    from agentshift.emitters import openai_agents  # noqa: F401
    assert hasattr(openai_agents, "emit")


# ---------------------------------------------------------------------------
# T20-13: Fixture conversion — pregnancy-companion fixture
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not PREGNANCY.exists(), reason="pregnancy-companion fixture not found")
def test_pregnancy_companion_conversion(tmp_path):
    """Pregnancy-companion fixture converts to OpenAI Agents SDK without error."""
    from agentshift.parsers.openclaw import parse_skill_dir

    ir = parse_skill_dir(PREGNANCY)
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"Missing: {fname}"


# ---------------------------------------------------------------------------
# T20-14: CLI convert command end-to-end
# ---------------------------------------------------------------------------

_VENV_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "agentshift"
_AGENTSHIFT = (
    [str(_VENV_BIN)] if _VENV_BIN.exists() else [sys.executable, "-m", "agentshift"]
)


@pytest.mark.skipif(not PREGNANCY.exists(), reason="pregnancy-companion fixture not found")
@pytest.mark.skipif(
    "openai-agents" not in __import__("agentshift.cli", fromlist=["_EMITTERS"])._EMITTERS,
    reason="openai-agents not yet registered in CLI _EMITTERS",
)
def test_cli_convert_to_openai_agents(tmp_path):
    """CLI `agentshift convert --to openai-agents <fixture>` succeeds."""
    result = subprocess.run(
        [
            *_AGENTSHIFT,
            "convert",
            str(PREGNANCY),
            "--from",
            "openclaw",
            "--to",
            "openai-agents",
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
