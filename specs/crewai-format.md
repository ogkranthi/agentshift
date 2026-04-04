# CrewAI — Format Spec

**Version:** crewai ≥ 1.13 (2025)
**Direction:** Bidirectional — IR → CrewAI YAML (emit) + CrewAI YAML → IR (parse)
**Status:** Spec complete — ready for D31

---

## Overview

CrewAI is a popular open-source multi-agent framework for Python. It uses a **YAML-based
configuration** (`agents.yaml` + `tasks.yaml`) to define agents and tasks, loaded by a Python
`@CrewBase` class. The framework supports sequential and hierarchical process flows.

GitHub:   https://github.com/crewAIInc/crewAI
Docs:     https://docs.crewai.com
Examples: https://github.com/crewAIInc/crewAI-examples

---

## Project Structure

```
{project_name}_crew/
├── crew.py           # @CrewBase class — loads YAML, wires tools
├── main.py           # Entry point: kickoff with inputs
├── requirements.txt  # crewai + tool deps
├── README.md         # How to run
└── config/
    ├── agents.yaml   # Agent definitions (role, goal, backstory)
    └── tasks.yaml    # Task definitions (description, expected_output, agent)
```

---

## `config/agents.yaml` Format

```yaml
# Each top-level key maps to an @agent method in crew.py
{agent_key}:
  role: >
    {role description — what function this agent serves}
  goal: >
    {goal — what the agent is trying to achieve}
  backstory: >
    {backstory — persona/background that shapes agent behavior}
  verbose: true           # Optional: enable detailed logging
  llm: gpt-4o             # Optional: model override
  allow_delegation: false # Optional: can agent delegate to others?
  max_iter: 15            # Optional: max reasoning iterations
  memory: false           # Optional: enable agent memory
```

### Full Example (Research + Reporting)

```yaml
researcher:
  role: >
    Senior Research Specialist
  goal: >
    Uncover accurate and current information about {topic}
  backstory: >
    You're a seasoned researcher with a talent for finding the most
    relevant, up-to-date information. You synthesize complex topics
    into clear, actionable insights.
  verbose: true
  llm: gpt-4o

reporting_analyst:
  role: >
    Reporting Analyst
  goal: >
    Create detailed, well-structured reports based on research findings
  backstory: >
    You're a meticulous analyst known for transforming raw research into
    polished, executive-ready reports. Clarity and accuracy are your hallmarks.
  verbose: true
```

---

## `config/tasks.yaml` Format

```yaml
# Each top-level key maps to a @task method in crew.py
{task_key}:
  description: >
    {what the agent should do — can reference {variables}}
  expected_output: >
    {what format/content should result from completing this task}
  agent: {agent_key}    # References a key in agents.yaml
  context:              # Optional: list of task keys whose output feeds this task
    - prior_task_key
  output_file: out.md   # Optional: save output to file
  markdown: true        # Optional: output as markdown
```

### Full Example

```yaml
research_task:
  description: >
    Conduct thorough research on {topic}.
    Identify the top developments, key players, and emerging trends.
    Use all available tools to gather current information.
  expected_output: >
    A comprehensive research brief with:
    - Executive summary (3-5 sentences)
    - Top 10 key findings with sources
    - Emerging trends section
  agent: researcher

reporting_task:
  description: >
    Review the research brief and expand it into a detailed report on {topic}.
    Include all key findings, analysis, and recommendations.
  expected_output: >
    A full markdown report with sections:
    # {topic} Report
    ## Executive Summary
    ## Key Findings
    ## Analysis
    ## Recommendations
  agent: reporting_analyst
  context:
    - research_task
  output_file: report.md
  markdown: true
```

---

## `crew.py` Structure

Tools are **not** expressed in YAML — they must be instantiated as Python objects in `crew.py`:

```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool  # Example built-in tool

@CrewBase
class {ClassName}Crew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def {agent_key}(self) -> Agent:
        return Agent(
            config=self.agents_config["{agent_key}"],
            tools=[SerperDevTool()],  # Tools assigned here in code
        )

    @task
    def {task_key}(self) -> Task:
        return Task(config=self.tasks_config["{task_key}"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,  # or Process.hierarchical
            verbose=True,
        )
```

---

## IR → CrewAI Mapping (Emitter)

| IR Field | CrewAI Target | Notes |
|----------|---------------|-------|
| `name` | Project directory name + `ClassName` in crew.py | snake_case + PascalCase |
| `description` | `goal` in agents.yaml | Primary purpose |
| `persona.system_prompt` | `backstory` + `role` in agents.yaml | Split heuristically (see below) |
| `persona.sections` | `backstory` field, prepended | Sections as context |
| `tools[kind=function]` | Tool stub class in `tools.py` + wired in crew.py | One `BaseTool` subclass per tool |
| `tools[kind=shell]` | Tool stub wrapping `subprocess.run()` | Shell command in tool |
| `tools[kind=mcp]` | README note + stub | No native MCP; wrap as custom tool |
| `tools[].name` | Tool class name | PascalCase |
| `tools[].description` | Tool class docstring | Passed to Agent |
| `model` | `llm:` in agents.yaml | Direct model name |
| `triggers[]` | tasks.yaml task descriptions | Map `kind=manual` to task descriptions |
| `knowledge[]` | README note + stub | Knowledge via RAG tool |
| `constraints.guardrails` | Prepended to backstory | Added as behavioral rules |
| `governance` | README note | No native guardrail system |

### IR → agents.yaml Strategy

Since IR has a single `persona.system_prompt` blob, the emitter applies this heuristic:
1. **role**: `description` (short) OR first sentence of system_prompt
2. **goal**: Second sentence or first `## Goal` section if present
3. **backstory**: Remaining system_prompt content / persona sections

For multi-section IR (`persona.sections`), map sections to role/goal/backstory intelligently.

### Simple Skill Mapping

For simple single-skill IR (the common case):
- One agent in agents.yaml (the skill itself)
- One task in tasks.yaml (the primary action)
- All tools assigned to that single agent

---

## CrewAI → IR Mapping (Parser)

The parser reads `agents.yaml` and `tasks.yaml` from a CrewAI project:

| CrewAI Source | IR Field | Notes |
|---------------|----------|-------|
| Agent key name | `name` | Normalized to slug |
| `agents.yaml[].role` | `name` (if more descriptive) | Fallback from key |
| `agents.yaml[].goal` | `description` | Truncated to 200 chars |
| `agents.yaml[].backstory` | `persona.system_prompt` | Primary instruction text |
| `agents.yaml[].role` + `goal` + `backstory` | `persona.system_prompt` (joined) | Joined with `\n\n` when backstory alone is insufficient |
| `agents.yaml[].llm` | `model` | If present |
| `tasks.yaml[].description` | `triggers[kind=manual].message` | Task as trigger |
| `tasks.yaml` tasks | `persona.sections["tasks"]` | Serialized as markdown |
| Tool names in YAML `tools:` list | `tools[kind=function]` stubs | Best-effort, no code execution |

**Note:** Tools are defined in Python code, not YAML — the parser cannot extract tool implementations,
only stubs based on tool names referenced in `agents.yaml` or `crew.py` patterns. The parser scans
for `tools:` lists in agent configs and imports in `crew.py` to infer tool names.

---

## Platform Constraints

| Constraint | Detail |
|------------|--------|
| Tools in Python only | No YAML-native tool definitions |
| Single `Process` type | Sequential or hierarchical (no DAG) |
| Template variables | `{variables}` in YAML replaced at runtime |
| No native triggers | External scheduler required |
| No system knowledge base | Use RAG tools (e.g., `crewai_tools`) |

---

## Portability Notes

- **Instructions**: ✅ 100% portable (mapped to role/goal/backstory)
- **Tools**: ✅ Stubs generated in crew.py
- **Model**: ✅ Direct mapping via `llm:` field
- **Knowledge**: ⚠️ Stub + README
- **Triggers**: ⚠️ README only
- **Multi-agent**: ⚠️ Only first agent extracted on parse; emit supports multi-task

---

## Example: IR → agents.yaml (pregnancy-companion)

```yaml
# Generated by agentshift from openclaw format
pregnancy_companion:
  role: >
    Pregnancy Health Companion
  goal: >
    Provide 24/7 support answering questions, tracking symptoms,
    giving weekly updates, and supporting a healthy pregnancy journey
  backstory: >
    You are a knowledgeable and compassionate pregnancy companion with
    deep expertise in prenatal health. You answer questions with
    evidence-based information, track reported symptoms, and offer
    weekly pregnancy milestone updates. You are warm, supportive,
    and always remind users to consult their healthcare provider
    for medical decisions.
  verbose: true
  llm: gpt-4o
```

---

## References

- CrewAI Docs (Agents): https://docs.crewai.com/en/concepts/agents
- CrewAI Docs (Tasks): https://docs.crewai.com/en/concepts/tasks
- Quickstart: https://docs.crewai.com/en/quickstart
- Examples: https://github.com/crewAIInc/crewAI-examples
