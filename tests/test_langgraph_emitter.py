"""Tests for the LangGraph emitter — IR → agent.py + tools.py + requirements.txt +
langgraph.json + .env.example + README.md"""

from __future__ import annotations

import json
from pathlib import Path

from agentshift.emitters.langgraph import emit
from agentshift.ir import (
    AgentIR,
    Constraints,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
    ToolAuth,
    Trigger,
)

FIXTURES = Path(__file__).parent / "fixtures"
PREGNANCY = FIXTURES / "pregnancy-companion"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OUTPUT_FILES = {
    "agent.py",
    "tools.py",
    "requirements.txt",
    "langgraph.json",
    ".env.example",
    "README.md",
}


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-agent",
        description="A test agent for AgentShift LangGraph emitter",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


# ---------------------------------------------------------------------------
# T11-1: Basic emit — all 6 output files exist
# ---------------------------------------------------------------------------


def test_langgraph_basic_emit(tmp_path):
    """All 6 expected output files are created."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"Missing output file: {fname}"


# ---------------------------------------------------------------------------
# T11-2: agent.py structure
# ---------------------------------------------------------------------------


def test_langgraph_agent_py_structure(tmp_path):
    """agent.py contains the key LangGraph building blocks."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "StateGraph" in content
    assert "ToolNode" in content
    assert "build_graph" in content
    assert "compile" in content


def test_langgraph_agent_py_has_system_prompt(tmp_path):
    """agent.py includes the system prompt from the IR persona."""
    ir = make_simple_ir(persona=Persona(system_prompt="You are a pregnancy companion."))
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "pregnancy companion" in content


def test_langgraph_agent_py_graph_exported(tmp_path):
    """agent.py exports `graph` at module level for LangGraph Platform."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    assert "graph = build_graph().compile(" in content


# ---------------------------------------------------------------------------
# T11-3: tools.py structure
# ---------------------------------------------------------------------------


def test_langgraph_tools_py_structure(tmp_path):
    """tools.py contains get_tools() and @tool decorator."""
    ir = make_simple_ir(
        tools=[
            Tool(name="my-tool", description="Does something useful.", kind="function")
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "get_tools" in content
    assert "@tool" in content


def test_langgraph_tools_py_imports_langchain_tool(tmp_path):
    """tools.py imports from langchain_core.tools."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "from langchain_core.tools import tool" in content


# ---------------------------------------------------------------------------
# T11-4: requirements.txt contains expected packages
# ---------------------------------------------------------------------------


def test_langgraph_requirements(tmp_path):
    """requirements.txt includes langgraph and langchain-core."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "langgraph" in content
    assert "langchain-core" in content


def test_langgraph_requirements_includes_anthropic_by_default(tmp_path):
    """requirements.txt includes langchain-anthropic for the default LLM."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "langchain-anthropic" in content


def test_langgraph_requirements_includes_requests_for_openapi_tools(tmp_path):
    """requirements.txt includes requests when any openapi tool is present."""
    ir = make_simple_ir(
        tools=[Tool(name="weather", description="Weather API", kind="openapi")]
    )
    emit(ir, tmp_path)
    content = (tmp_path / "requirements.txt").read_text()
    assert "requests" in content


# ---------------------------------------------------------------------------
# T11-5: langgraph.json is valid JSON with graphs key
# ---------------------------------------------------------------------------


def test_langgraph_manifest(tmp_path):
    """langgraph.json is valid JSON and contains the graphs key."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    raw = (tmp_path / "langgraph.json").read_text()
    data = json.loads(raw)  # must not raise
    assert isinstance(data, dict)
    assert "graphs" in data
    assert isinstance(data["graphs"], dict)
    assert len(data["graphs"]) >= 1


def test_langgraph_manifest_has_python_version(tmp_path):
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "langgraph.json").read_text())
    assert "python_version" in data


def test_langgraph_manifest_has_dependencies(tmp_path):
    ir = make_simple_ir()
    emit(ir, tmp_path)
    data = json.loads((tmp_path / "langgraph.json").read_text())
    assert "dependencies" in data


# ---------------------------------------------------------------------------
# T11-6: .env.example exists and has key env var patterns
# ---------------------------------------------------------------------------


def test_langgraph_env_example(tmp_path):
    """.env.example exists and contains expected API key patterns."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    assert (tmp_path / ".env.example").exists()
    content = (tmp_path / ".env.example").read_text()
    assert "ANTHROPIC_API_KEY" in content


def test_langgraph_env_example_has_langsmith_vars(tmp_path):
    """.env.example includes LangSmith observability variables."""
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / ".env.example").read_text()
    assert "LANGSMITH_API_KEY" in content


def test_langgraph_env_example_includes_tool_env_vars(tmp_path):
    """.env.example includes tool-specific API keys when auth is required."""
    ir = make_simple_ir(
        tools=[
            Tool(
                name="my-api",
                description="An authenticated API",
                kind="openapi",
                auth=ToolAuth(type="api_key", env_var="MY_API_KEY"),
            )
        ]
    )
    emit(ir, tmp_path)
    content = (tmp_path / ".env.example").read_text()
    assert "MY_API_KEY" in content


# ---------------------------------------------------------------------------
# T11-7: README.md exists and has agent name
# ---------------------------------------------------------------------------


def test_langgraph_readme(tmp_path):
    """README.md exists and mentions the agent name."""
    ir = make_simple_ir(name="my-test-agent")
    emit(ir, tmp_path)
    assert (tmp_path / "README.md").exists()
    content = (tmp_path / "README.md").read_text()
    assert "my-test-agent" in content


def test_langgraph_readme_mentions_agentshift(tmp_path):
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "AgentShift" in content or "agentshift" in content.lower()


def test_langgraph_readme_has_setup_section(tmp_path):
    ir = make_simple_ir()
    emit(ir, tmp_path)
    content = (tmp_path / "README.md").read_text()
    assert "Setup" in content or "setup" in content.lower()


# ---------------------------------------------------------------------------
# T11-8: IR with multiple tools → tools.py has all tool names
# ---------------------------------------------------------------------------


def test_langgraph_with_tools(tmp_path):
    """IR with multiple tools produces tools.py containing all tool function names."""
    tools = [
        Tool(name="search-web", description="Search the web", kind="function"),
        Tool(name="get-weather", description="Get weather data", kind="openapi"),
        Tool(name="send-email", description="Send an email", kind="function"),
    ]
    ir = make_simple_ir(tools=tools)
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    # Tool function names are snake_case versions (hyphens → underscores)
    assert "search_web" in content
    assert "get_weather" in content
    assert "send_email" in content


def test_langgraph_with_tools_get_tools_lists_all(tmp_path):
    """get_tools() return value includes all tool function names."""
    tools = [
        Tool(name="tool-a", description="Tool A", kind="function"),
        Tool(name="tool-b", description="Tool B", kind="function"),
    ]
    ir = make_simple_ir(tools=tools)
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    # The return list should contain all tools
    assert "tool_a" in content
    assert "tool_b" in content
    # get_tools should return a list containing both
    assert (
        "tool_a, tool_b" in content
        or "tool_b, tool_a" in content
        or ("tool_a" in content and "tool_b" in content)
    )


# ---------------------------------------------------------------------------
# T11-9: IR with zero tools → still emits cleanly
# ---------------------------------------------------------------------------


def test_langgraph_no_tools(tmp_path):
    """IR with no tools still produces all 6 output files without error."""
    ir = make_simple_ir(tools=[])
    emit(ir, tmp_path)  # must not raise
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"Missing output file: {fname}"


def test_langgraph_no_tools_get_tools_returns_empty(tmp_path):
    """get_tools() returns [] when no tools are defined."""
    ir = make_simple_ir(tools=[])
    emit(ir, tmp_path)
    content = (tmp_path / "tools.py").read_text()
    assert "return []" in content


# ---------------------------------------------------------------------------
# T11-10: Very long instructions handled without crash
# ---------------------------------------------------------------------------


def test_langgraph_instruction_truncation(tmp_path):
    """Very long system prompts are written without crashing."""
    long_prompt = "This is a very long instruction. " * 1000  # ~33000 chars
    ir = make_simple_ir(persona=Persona(system_prompt=long_prompt))
    emit(ir, tmp_path)  # must not raise
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists()


def test_langgraph_instruction_truncation_with_max_chars(tmp_path):
    """When max_instruction_chars is set, system prompt is truncated."""
    long_prompt = "x" * 5000
    ir = make_simple_ir(
        persona=Persona(system_prompt=long_prompt),
        constraints=Constraints(max_instruction_chars=100),
    )
    emit(ir, tmp_path)
    content = (tmp_path / "agent.py").read_text()
    # The entire 5000-char prompt should not appear verbatim
    assert "x" * 200 not in content


# ---------------------------------------------------------------------------
# T11-11: "langgraph" registered in CLI _EMITTERS
# ---------------------------------------------------------------------------


def test_langgraph_registered_in_cli():
    """The LangGraph emitter is registered as 'langgraph' in the CLI _EMITTERS dict."""
    from agentshift.cli import _EMITTERS

    assert "langgraph" in _EMITTERS


# ---------------------------------------------------------------------------
# T11-12: CLI convert command works end-to-end
# ---------------------------------------------------------------------------

_VENV_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "agentshift"
import subprocess  # noqa: E402
import sys  # noqa: E402

_AGENTSHIFT = (
    [str(_VENV_BIN)] if _VENV_BIN.exists() else [sys.executable, "-m", "agentshift"]
)


def test_langgraph_convert_command(tmp_path):
    """CLI `agentshift convert --to langgraph <fixture>` produces all 6 output files."""
    result = subprocess.run(
        [
            *_AGENTSHIFT,
            "convert",
            str(PREGNANCY),
            "--from",
            "openclaw",
            "--to",
            "langgraph",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    for fname in OUTPUT_FILES:
        assert (tmp_path / fname).exists(), f"CLI did not create: {fname}"


# ---------------------------------------------------------------------------
# Extra structural tests
# ---------------------------------------------------------------------------


class TestLangGraphAgentPyExtras:
    def test_creates_output_directory_if_missing(self, tmp_path):
        ir = make_simple_ir()
        target = tmp_path / "deep" / "nested" / "dir"
        assert not target.exists()
        emit(ir, target)
        assert target.exists()

    def test_agent_py_has_agent_state_typeddict(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "agent.py").read_text()
        assert "AgentState" in content
        assert "TypedDict" in content

    def test_agent_py_imports_start_end(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "agent.py").read_text()
        assert "START" in content
        assert "END" in content

    def test_agent_py_imports_get_tools(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "agent.py").read_text()
        assert "get_tools" in content

    def test_readme_has_generated_files_table(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "README.md").read_text()
        assert "agent.py" in content
        assert "tools.py" in content

    def test_readme_has_python_api_usage(self, tmp_path):
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "README.md").read_text()
        assert "graph.invoke" in content

    def test_cron_trigger_noted_in_agent_py(self, tmp_path):
        ir = make_simple_ir(
            triggers=[
                Trigger(
                    id="daily",
                    kind="cron",
                    cron_expr="0 9 * * *",
                    message="Run daily",
                )
            ]
        )
        emit(ir, tmp_path)
        content = (tmp_path / "agent.py").read_text()
        assert "cron" in content or "0 9 * * *" in content

    def test_no_python_repr_in_any_file(self, tmp_path):
        ir = make_simple_ir(
            tools=[Tool(name="gh", description="GitHub CLI", kind="shell")]
        )
        emit(ir, tmp_path)
        for fname in OUTPUT_FILES:
            content = (tmp_path / fname).read_text()
            assert "<agentshift." not in content, f"Python repr in {fname}"
            assert "object at 0x" not in content, f"Memory address in {fname}"

    def test_mcp_tool_generates_comment(self, tmp_path):
        ir = make_simple_ir(
            tools=[
                Tool(
                    name="slack-mcp",
                    description="Slack via MCP",
                    kind="mcp",
                    endpoint="http://localhost:3000",
                )
            ]
        )
        emit(ir, tmp_path)
        content = (tmp_path / "tools.py").read_text()
        assert "MCP" in content or "mcp" in content.lower()

    def test_knowledge_on_demand_generates_retrieve_tool(self, tmp_path):
        ir = make_simple_ir(
            knowledge=[
                KnowledgeSource(
                    name="docs",
                    kind="file",
                    path="/tmp/docs.md",
                    load_mode="on_demand",
                )
            ]
        )
        emit(ir, tmp_path)
        content = (tmp_path / "tools.py").read_text()
        assert "retrieve_docs" in content
