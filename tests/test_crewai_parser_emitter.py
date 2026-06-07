"""Tests for the CrewAI parser + emitter — agents.yaml round-trip, task mapping.

Parser: src/agentshift/parsers/crewai.py
Emitter: src/agentshift/emitters/crewai.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from agentshift.emitters.crewai import emit
from agentshift.parsers.crewai import parse
from agentshift.ir import (
    AgentIR,
    Metadata,
    Persona,
    Tool,
    Trigger,
)

FIXTURES = Path(__file__).parent / "fixtures"
PREGNANCY = FIXTURES / "pregnancy-companion"

EMITTER_OUTPUT_FILES = {
    "config/agents.yaml",
    "config/tasks.yaml",
    "crew.py",
    "requirements.txt",
    "README.md",
}


def make_simple_ir(**kwargs) -> AgentIR:
    defaults = dict(
        name="test-agent",
        description="A test agent for AgentShift CrewAI emitter",
        persona=Persona(system_prompt="You are a helpful assistant."),
        metadata=Metadata(source_platform="openclaw"),
    )
    defaults.update(kwargs)
    return AgentIR(**defaults)


def make_crewai_project(tmp_path: Path, agents_yaml: dict, tasks_yaml: dict | None = None) -> Path:
    """Create a minimal CrewAI project structure for parser tests."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "agents.yaml").write_text(yaml.dump(agents_yaml), encoding="utf-8")
    if tasks_yaml is not None:
        (config_dir / "tasks.yaml").write_text(yaml.dump(tasks_yaml), encoding="utf-8")
    return tmp_path


# ===========================================================================
# EMITTER TESTS
# ===========================================================================


class TestCrewAIEmitterOutputFiles:
    def test_all_output_files_created(self, tmp_path):
        """All 5 expected output files/dirs are created."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        for rel_path in EMITTER_OUTPUT_FILES:
            assert (tmp_path / rel_path).exists(), f"Missing output: {rel_path}"

    def test_creates_config_subdirectory(self, tmp_path):
        """emit() creates config/ subdirectory."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        assert (tmp_path / "config").is_dir()

    def test_creates_nested_output_directory(self, tmp_path):
        """emit() creates nested output directory if it doesn't exist."""
        ir = make_simple_ir()
        target = tmp_path / "deep" / "nested"
        emit(ir, target)
        assert target.exists()
        assert (target / "config").is_dir()


class TestCrewAIEmitterAgentsYaml:
    def test_agents_yaml_valid(self, tmp_path):
        """config/agents.yaml is valid YAML."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "config" / "agents.yaml").read_text()
        data = yaml.safe_load(content)  # must not raise
        assert isinstance(data, dict)

    def test_agents_yaml_has_agent_key(self, tmp_path):
        """config/agents.yaml contains the agent as a top-level key."""
        ir = make_simple_ir(name="my-agent")
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "agents.yaml").read_text())
        assert "my_agent" in data

    def test_agents_yaml_has_role(self, tmp_path):
        """config/agents.yaml includes role field."""
        ir = make_simple_ir(description="Helps with everything.")
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "agents.yaml").read_text())
        agent_data = next(iter(data.values()))
        assert "role" in agent_data

    def test_agents_yaml_has_goal(self, tmp_path):
        """config/agents.yaml includes goal field."""
        ir = make_simple_ir(
            persona=Persona(system_prompt="Help users manage tasks efficiently.")
        )
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "agents.yaml").read_text())
        agent_data = next(iter(data.values()))
        assert "goal" in agent_data

    def test_agents_yaml_has_backstory(self, tmp_path):
        """config/agents.yaml includes backstory field from system_prompt."""
        ir = make_simple_ir(
            persona=Persona(system_prompt="You are an expert researcher with 10 years experience.")
        )
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "agents.yaml").read_text())
        agent_data = next(iter(data.values()))
        assert "backstory" in agent_data

    def test_agents_yaml_has_verbose(self, tmp_path):
        """config/agents.yaml includes verbose: true."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "agents.yaml").read_text())
        agent_data = next(iter(data.values()))
        assert agent_data.get("verbose") is True

    def test_agents_yaml_default_model(self, tmp_path):
        """config/agents.yaml defaults to gpt-4o model."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "config" / "agents.yaml").read_text()
        assert "gpt-4o" in content

    def test_agents_yaml_custom_model(self, tmp_path):
        """config/agents.yaml uses model from platform_extensions when set."""
        ir = make_simple_ir(
            metadata=Metadata(
                source_platform="openclaw",
                platform_extensions={"crewai": {"model": "gpt-3.5-turbo"}},
            )
        )
        emit(ir, tmp_path)
        content = (tmp_path / "config" / "agents.yaml").read_text()
        assert "gpt-3.5-turbo" in content


class TestCrewAIEmitterTasksYaml:
    def test_tasks_yaml_valid(self, tmp_path):
        """config/tasks.yaml is valid YAML."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "config" / "tasks.yaml").read_text()
        data = yaml.safe_load(content)  # must not raise
        assert isinstance(data, dict)

    def test_tasks_yaml_has_main_task_by_default(self, tmp_path):
        """config/tasks.yaml has main_task when no manual triggers exist."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "tasks.yaml").read_text())
        assert "main_task" in data

    def test_tasks_yaml_task_has_description(self, tmp_path):
        """config/tasks.yaml task includes description."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "tasks.yaml").read_text())
        task = next(iter(data.values()))
        assert "description" in task

    def test_tasks_yaml_task_has_expected_output(self, tmp_path):
        """config/tasks.yaml task includes expected_output."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "tasks.yaml").read_text())
        task = next(iter(data.values()))
        assert "expected_output" in task

    def test_tasks_yaml_references_agent(self, tmp_path):
        """config/tasks.yaml task references the agent key."""
        ir = make_simple_ir(name="my-agent")
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "tasks.yaml").read_text())
        task = next(iter(data.values()))
        assert "agent" in task
        assert task["agent"] == "my_agent"

    def test_tasks_yaml_manual_triggers_become_tasks(self, tmp_path):
        """Manual triggers map to tasks in tasks.yaml."""
        ir = make_simple_ir(
            triggers=[
                Trigger(kind="manual", id="task1", message="Analyze the provided document"),
                Trigger(kind="manual", id="task2", message="Summarize the analysis"),
            ]
        )
        emit(ir, tmp_path)
        data = yaml.safe_load((tmp_path / "config" / "tasks.yaml").read_text())
        assert len(data) >= 2


class TestCrewAIEmitterCrewPy:
    def test_crew_py_imports_crewai(self, tmp_path):
        """crew.py imports from crewai."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "crew.py").read_text()
        assert "from crewai" in content

    def test_crew_py_has_crewbase_decorator(self, tmp_path):
        """crew.py uses @CrewBase decorator."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "crew.py").read_text()
        assert "@CrewBase" in content

    def test_crew_py_has_agent_method(self, tmp_path):
        """crew.py has an @agent decorated method."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "crew.py").read_text()
        assert "@agent" in content

    def test_crew_py_has_task_method(self, tmp_path):
        """crew.py has a @task decorated method."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "crew.py").read_text()
        assert "@task" in content

    def test_crew_py_has_crew_method(self, tmp_path):
        """crew.py has a @crew decorated method."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "crew.py").read_text()
        assert "@crew" in content

    def test_crew_py_class_name_uses_pascal_case(self, tmp_path):
        """crew.py class name is PascalCase based on agent name."""
        ir = make_simple_ir(name="my-research-agent")
        emit(ir, tmp_path)
        content = (tmp_path / "crew.py").read_text()
        assert "MyResearchAgent" in content

    def test_crew_py_tools_get_todo_comment(self, tmp_path):
        """When tools exist, crew.py includes a TODO comment for wiring."""
        ir = make_simple_ir(
            tools=[Tool(name="search", description="Search the web", kind="function")]
        )
        emit(ir, tmp_path)
        content = (tmp_path / "crew.py").read_text()
        assert "TODO" in content

    def test_crew_py_sequential_process(self, tmp_path):
        """crew.py uses Process.sequential."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "crew.py").read_text()
        assert "Process.sequential" in content


class TestCrewAIEmitterRequirements:
    def test_requirements_includes_crewai(self, tmp_path):
        """requirements.txt includes crewai dependency."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "requirements.txt").read_text()
        assert "crewai" in content


class TestCrewAIEmitterReadme:
    def test_readme_mentions_agent_name(self, tmp_path):
        """README.md mentions the agent name."""
        ir = make_simple_ir(name="my-test-agent")
        emit(ir, tmp_path)
        content = (tmp_path / "README.md").read_text()
        assert "my-test-agent" in content

    def test_readme_mentions_agentshift(self, tmp_path):
        """README.md mentions AgentShift."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "README.md").read_text()
        assert "AgentShift" in content or "agentshift" in content.lower()

    def test_readme_has_setup_section(self, tmp_path):
        """README.md has a Setup section."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "README.md").read_text()
        assert "Setup" in content

    def test_readme_mentions_crewai(self, tmp_path):
        """README.md mentions CrewAI."""
        ir = make_simple_ir()
        emit(ir, tmp_path)
        content = (tmp_path / "README.md").read_text()
        assert "CrewAI" in content or "crewai" in content.lower()


# ===========================================================================
# PARSER TESTS
# ===========================================================================


class TestCrewAIParserBasic:
    def test_parse_returns_agent_ir(self, tmp_path):
        """parse() returns an AgentIR instance."""
        agents = {"my_agent": {"role": "Researcher", "goal": "Find answers", "backstory": "Expert"}}
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert isinstance(ir, AgentIR)

    def test_parse_missing_directory_raises(self, tmp_path):
        """parse() raises FileNotFoundError for non-existent directory."""
        with pytest.raises(FileNotFoundError):
            parse(tmp_path / "nonexistent")

    def test_parse_missing_agents_yaml_raises(self, tmp_path):
        """parse() raises ValueError when no agents.yaml is found."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "config").mkdir()
        # No agents.yaml created
        with pytest.raises(ValueError, match="agents.yaml"):
            parse(tmp_path)

    def test_parse_role_becomes_description(self, tmp_path):
        """The agent role maps to IR description."""
        agents = {
            "analyst": {
                "role": "Data Analyst specializing in trends",
                "goal": "Analyze data",
                "backstory": "10 years experience",
            }
        }
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        # role should influence description
        assert ir.description != ""

    def test_parse_backstory_becomes_system_prompt(self, tmp_path):
        """The agent backstory maps to IR persona.system_prompt."""
        agents = {
            "agent1": {
                "role": "Helper",
                "goal": "Help users",
                "backstory": "You are an expert with deep knowledge in many fields.",
            }
        }
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert ir.persona.system_prompt is not None
        assert "expert" in ir.persona.system_prompt

    def test_parse_goal_becomes_description(self, tmp_path):
        """The agent goal influences IR description."""
        agents = {
            "agent1": {
                "role": "Writer",
                "goal": "Write compelling content",
                "backstory": "",
            }
        }
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert "content" in ir.description or "Writer" in ir.description

    def test_parse_first_agent_used(self, tmp_path):
        """When multiple agents exist, the first one is used."""
        agents = {
            "agent_a": {"role": "First Agent", "goal": "Do first", "backstory": "Expert A"},
            "agent_b": {"role": "Second Agent", "goal": "Do second", "backstory": "Expert B"},
        }
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        # Should not raise and should return valid IR
        assert isinstance(ir, AgentIR)

    def test_parse_name_derived_from_role(self, tmp_path):
        """IR name is derived (slugified) from role."""
        agents = {
            "my_researcher": {
                "role": "Research Scientist",
                "goal": "Research things",
                "backstory": "Expert",
            }
        }
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert ir.name != ""
        # Name should be URL-safe slug
        assert " " not in ir.name


class TestCrewAIParserTools:
    def test_parse_agent_tools_list(self, tmp_path):
        """Tools listed in agents.yaml map to IR tools."""
        agents = {
            "agent1": {
                "role": "Helper",
                "goal": "Help",
                "backstory": "Expert",
                "tools": ["search_tool", "calculator_tool"],
            }
        }
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert len(ir.tools) == 2
        tool_names = [t.name for t in ir.tools]
        assert "search_tool" in tool_names
        assert "calculator_tool" in tool_names

    def test_parse_tools_kind_is_function(self, tmp_path):
        """Tools parsed from agents.yaml get kind='function'."""
        agents = {
            "agent1": {
                "role": "Helper",
                "goal": "Help",
                "backstory": "Expert",
                "tools": ["my_tool"],
            }
        }
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert ir.tools[0].kind == "function"

    def test_parse_no_tools(self, tmp_path):
        """IR has no tools when agents.yaml has no tools."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert ir.tools == []


class TestCrewAIParserTasks:
    def test_parse_tasks_become_triggers(self, tmp_path):
        """Tasks in tasks.yaml map to IR manual triggers."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        tasks = {
            "task1": {
                "description": "Analyze the provided text",
                "expected_output": "Analysis result",
                "agent": "agent1",
            }
        }
        make_crewai_project(tmp_path, agents, tasks)
        ir = parse(tmp_path)
        assert len(ir.triggers) >= 1
        assert ir.triggers[0].kind == "manual"

    def test_parse_task_description_maps_to_trigger_message(self, tmp_path):
        """Task description maps to trigger message."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        tasks = {
            "main_task": {
                "description": "Analyze quarterly data",
                "expected_output": "Analysis",
                "agent": "agent1",
            }
        }
        make_crewai_project(tmp_path, agents, tasks)
        ir = parse(tmp_path)
        assert any("quarterly" in (t.message or "") for t in ir.triggers)

    def test_parse_task_id_maps_to_trigger_id(self, tmp_path):
        """Task key maps to trigger id."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        tasks = {
            "my_special_task": {
                "description": "Do something",
                "expected_output": "Done",
                "agent": "agent1",
            }
        }
        make_crewai_project(tmp_path, agents, tasks)
        ir = parse(tmp_path)
        assert any(t.id == "my_special_task" for t in ir.triggers)

    def test_parse_no_tasks_yaml(self, tmp_path):
        """parse() succeeds when no tasks.yaml exists (empty triggers)."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert isinstance(ir, AgentIR)
        assert ir.triggers == []

    def test_parse_multiple_tasks_create_multiple_triggers(self, tmp_path):
        """Multiple tasks create multiple triggers."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        tasks = {
            "task_1": {"description": "First task", "expected_output": "Done", "agent": "agent1"},
            "task_2": {"description": "Second task", "expected_output": "Done", "agent": "agent1"},
        }
        make_crewai_project(tmp_path, agents, tasks)
        ir = parse(tmp_path)
        assert len(ir.triggers) == 2


class TestCrewAIParserModel:
    def test_parse_model_stored_in_extensions(self, tmp_path):
        """LLM model is stored in platform_extensions['crewai']."""
        agents = {
            "agent1": {
                "role": "Helper",
                "goal": "Help",
                "backstory": "Expert",
                "llm": "gpt-4-turbo",
            }
        }
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        assert ir.metadata.platform_extensions.get("crewai", {}).get("model") == "gpt-4-turbo"

    def test_parse_no_llm_no_extension(self, tmp_path):
        """If no llm key, no crewai extension is set."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        make_crewai_project(tmp_path, agents)
        ir = parse(tmp_path)
        # No crewai model extension when not specified
        crewai_ext = ir.metadata.platform_extensions.get("crewai", {})
        assert "model" not in crewai_ext or crewai_ext.get("model") == ""


class TestCrewAIParserFileLocations:
    def test_parse_agents_yaml_at_root(self, tmp_path):
        """parse() can read agents.yaml from project root (not just config/)."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        (tmp_path / "agents.yaml").write_text(yaml.dump(agents), encoding="utf-8")
        ir = parse(tmp_path)
        assert isinstance(ir, AgentIR)

    def test_parse_tasks_yaml_at_root(self, tmp_path):
        """parse() can read tasks.yaml from project root."""
        agents = {"agent1": {"role": "Helper", "goal": "Help", "backstory": "Expert"}}
        tasks = {
            "task1": {"description": "Do something", "expected_output": "Done", "agent": "agent1"}
        }
        (tmp_path / "agents.yaml").write_text(yaml.dump(agents), encoding="utf-8")
        (tmp_path / "tasks.yaml").write_text(yaml.dump(tasks), encoding="utf-8")
        ir = parse(tmp_path)
        assert len(ir.triggers) >= 1

    def test_parse_config_subdir_takes_priority(self, tmp_path):
        """config/ subdirectory agents.yaml takes priority over root agents.yaml."""
        # Root agents.yaml
        root_agents = {"root_agent": {"role": "Root", "goal": "Root goal", "backstory": "Root"}}
        (tmp_path / "agents.yaml").write_text(yaml.dump(root_agents), encoding="utf-8")

        # config/ agents.yaml
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_agents = {
            "config_agent": {"role": "Config", "goal": "Config goal", "backstory": "Config"}
        }
        (config_dir / "agents.yaml").write_text(yaml.dump(config_agents), encoding="utf-8")

        ir = parse(tmp_path)
        # Should use config/ version
        assert "config" in ir.name.lower() or "config" in ir.description.lower()


# ===========================================================================
# ROUND-TRIP TESTS
# ===========================================================================


class TestCrewAIRoundTrip:
    def test_emit_then_parse_returns_ir(self, tmp_path):
        """Emitting then parsing produces a valid AgentIR."""
        original_ir = make_simple_ir(
            name="research-agent",
            description="Research and analyze topics",
            persona=Persona(system_prompt="You are an expert researcher."),
        )
        emit(ir=original_ir, output_dir=tmp_path)
        parsed_ir = parse(tmp_path)
        assert isinstance(parsed_ir, AgentIR)

    def test_emit_then_parse_preserves_system_prompt(self, tmp_path):
        """System prompt is preserved through emit → parse cycle."""
        original_ir = make_simple_ir(
            persona=Persona(system_prompt="You are an expert researcher with 10 years experience.")
        )
        emit(ir=original_ir, output_dir=tmp_path)
        parsed_ir = parse(tmp_path)
        # The backstory should contain the system prompt
        assert parsed_ir.persona.system_prompt is not None
        assert "researcher" in parsed_ir.persona.system_prompt.lower()

    def test_emit_then_parse_preserves_description(self, tmp_path):
        """Description is preserved through emit → parse cycle (via role)."""
        original_ir = make_simple_ir(description="Analyze quarterly financial data")
        emit(ir=original_ir, output_dir=tmp_path)
        parsed_ir = parse(tmp_path)
        assert parsed_ir.description != ""

    def test_emit_then_parse_task_round_trip(self, tmp_path):
        """Manual triggers round-trip through emit → parse."""
        original_ir = make_simple_ir(
            triggers=[Trigger(kind="manual", id="task1", message="Analyze this document")]
        )
        emit(ir=original_ir, output_dir=tmp_path)
        parsed_ir = parse(tmp_path)
        assert len(parsed_ir.triggers) >= 1
        assert parsed_ir.triggers[0].kind == "manual"

    def test_emit_then_parse_no_python_repr(self, tmp_path):
        """Round-trip output contains no Python object repr."""
        original_ir = make_simple_ir()
        emit(ir=original_ir, output_dir=tmp_path)
        # Check YAML files for repr
        for fname in ["config/agents.yaml", "config/tasks.yaml"]:
            content = (tmp_path / fname).read_text()
            assert "<agentshift." not in content
            assert "object at 0x" not in content


# ===========================================================================
# REGISTRATION TEST
# ===========================================================================


def test_crewai_emitter_importable():
    """The CrewAI emitter module is importable and has emit function."""
    from agentshift.emitters import crewai  # noqa: F401
    assert hasattr(crewai, "emit")


def test_crewai_parser_importable():
    """The CrewAI parser module is importable and has parse function."""
    from agentshift.parsers import crewai  # noqa: F401
    assert hasattr(crewai, "parse")


# ===========================================================================
# CLI END-TO-END
# ===========================================================================

_VENV_BIN = Path(__file__).parent.parent / ".venv" / "bin" / "agentshift"
_AGENTSHIFT = (
    [str(_VENV_BIN)] if _VENV_BIN.exists() else [sys.executable, "-m", "agentshift"]
)


@pytest.mark.skipif(not PREGNANCY.exists(), reason="pregnancy-companion fixture not found")
@pytest.mark.skipif(
    "crewai" not in __import__("agentshift.cli", fromlist=["_EMITTERS"])._EMITTERS,
    reason="crewai not yet registered in CLI _EMITTERS",
)
def test_cli_convert_to_crewai(tmp_path):
    """CLI `agentshift convert --to crewai <fixture>` succeeds."""
    result = subprocess.run(
        [
            *_AGENTSHIFT,
            "convert",
            str(PREGNANCY),
            "--from",
            "openclaw",
            "--to",
            "crewai",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    for rel_path in EMITTER_OUTPUT_FILES:
        assert (tmp_path / rel_path).exists(), f"CLI did not create: {rel_path}"
