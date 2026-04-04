"""CrewAI parser — reads a CrewAI project directory into AgentShift IR.

Reads:
  config/agents.yaml (or agents.yaml at root)
  config/tasks.yaml  (or tasks.yaml at root)

Maps the first agent's role/goal/backstory into the IR persona, and tasks
into triggers.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from agentshift.ir import (
    AgentIR,
    Metadata,
    Persona,
    Tool,
    Trigger,
)

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse(input_dir: Path) -> AgentIR:
    """Read a CrewAI project directory and return an AgentIR."""
    if not input_dir.exists():
        raise FileNotFoundError(f"CrewAI project directory not found: {input_dir}")

    agents_yaml = _load_agents_yaml(input_dir)
    tasks_yaml = _load_tasks_yaml(input_dir)

    if not agents_yaml:
        raise ValueError(f"No agents.yaml found in {input_dir} or {input_dir / 'config'}")

    # Extract first agent
    first_key = next(iter(agents_yaml))
    agent_data = agents_yaml[first_key]

    # Identity
    role = _get_str(agent_data, "role", "").strip()
    goal = _get_str(agent_data, "goal", "").strip()
    backstory = _get_str(agent_data, "backstory", "").strip()

    name = _slugify(role or first_key)
    description = goal or role or ""

    # Build system prompt from backstory (+ role/goal context)
    system_prompt = backstory
    if not system_prompt:
        parts = []
        if role:
            parts.append(f"Role: {role}")
        if goal:
            parts.append(f"Goal: {goal}")
        system_prompt = "\n\n".join(parts)

    # Tools — extract from agent's tools list (names only)
    tools: list[Tool] = []
    agent_tools = agent_data.get("tools", [])
    if isinstance(agent_tools, list):
        for t in agent_tools:
            if isinstance(t, str):
                tools.append(
                    Tool(
                        name=t,
                        description=f"Tool: {t}",
                        kind="function",
                    )
                )

    # Triggers — extract from tasks
    triggers: list[Trigger] = []
    if tasks_yaml:
        for task_key, task_data in tasks_yaml.items():
            if not isinstance(task_data, dict):
                continue
            task_desc = _get_str(task_data, "description", "").strip()
            if task_desc:
                triggers.append(
                    Trigger(
                        kind="manual",
                        id=task_key,
                        message=task_desc,
                    )
                )

    # Model
    model = _get_str(agent_data, "llm", "")

    # Build metadata
    platform_extensions: dict = {}
    if model:
        platform_extensions["crewai"] = {"model": model}

    return AgentIR(
        name=name,
        description=description,
        persona=Persona(system_prompt=system_prompt or None),
        tools=tools,
        triggers=triggers,
        metadata=Metadata(
            source_platform="unknown",
            platform_extensions=platform_extensions,
        ),
    )


# ---------------------------------------------------------------------------
# File loading helpers
# ---------------------------------------------------------------------------


def _load_agents_yaml(input_dir: Path) -> dict | None:
    """Try config/agents.yaml then agents.yaml at root."""
    for candidate in [
        input_dir / "config" / "agents.yaml",
        input_dir / "agents.yaml",
    ]:
        if candidate.exists():
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    return None


def _load_tasks_yaml(input_dir: Path) -> dict | None:
    """Try config/tasks.yaml then tasks.yaml at root."""
    for candidate in [
        input_dir / "config" / "tasks.yaml",
        input_dir / "tasks.yaml",
    ]:
        if candidate.exists():
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    return None


def _get_str(data: dict, key: str, default: str = "") -> str:
    """Safely get a string value from a dict."""
    val = data.get(key, default)
    return str(val) if val is not None else default


def _slugify(name: str) -> str:
    """Convert a display name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"
