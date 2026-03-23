"""Claude Code parser — converts a CLAUDE.md + settings.json directory into AgentShift IR."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agentshift.ir import AgentIR, Metadata, Persona, Tool


def parse_agent_dir(path: Path) -> AgentIR:
    """Parse a Claude Code agent directory and return an AgentIR."""
    claude_md = path / "CLAUDE.md"
    settings_json = path / "settings.json"

    if not claude_md.exists():
        raise FileNotFoundError(f"No CLAUDE.md found in {path}")

    body = claude_md.read_text(encoding="utf-8")
    name, description, instructions = _parse_claude_md(body)

    tools = _parse_settings(settings_json)

    metadata = Metadata(
        source_platform="claude-code",
        source_file=str(claude_md),
    )

    persona = Persona(system_prompt=instructions.strip() if instructions.strip() else body.strip())

    return AgentIR(
        name=name,
        description=description,
        persona=persona,
        tools=tools,
        metadata=metadata,
    )


def _parse_claude_md(body: str) -> tuple[str, str, str]:
    """Return (name, description, instructions) from CLAUDE.md content."""
    lines = body.splitlines()

    name = "unnamed-agent"
    description = ""
    instructions_lines: list[str] = []

    # First H1 is the name
    for line in lines:
        h1 = re.match(r"^#\s+(.+)$", line)
        if h1:
            name = _slugify(h1.group(1).strip())
            break

    # First non-empty, non-heading paragraph after H1 is the description
    found_h1 = False
    for line in lines:
        if re.match(r"^#\s+", line):
            if not found_h1:
                found_h1 = True
                continue
            else:
                break
        if found_h1 and line.strip() and not line.startswith("#"):
            description = line.strip()
            break

    # "## Instructions" section body → system prompt
    in_instructions = False
    for line in lines:
        if re.match(r"^##\s+Instructions\s*$", line, re.IGNORECASE):
            in_instructions = True
            continue
        if in_instructions:
            if re.match(r"^##\s+", line):
                break
            instructions_lines.append(line)

    instructions = "\n".join(instructions_lines).strip()

    return name, description, instructions


def _slugify(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    # Ensure it starts and ends with alphanumeric
    if not slug or not re.match(r"^[a-z0-9]", slug):
        slug = "a" + slug
    if not re.match(r".*[a-z0-9]$", slug):
        slug = slug + "0"
    return slug


def _parse_settings(settings_path: Path) -> list[Tool]:
    """Extract tool list from settings.json permissions."""
    tools: list[Tool] = []
    if not settings_path.exists():
        return tools

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return tools

    allow = data.get("permissions", {}).get("allow", [])
    seen: set[str] = set()

    for rule in allow:
        tool_name, kind, description = _parse_permission_rule(rule)
        if tool_name and tool_name not in seen:
            tools.append(Tool(name=tool_name, description=description, kind=kind))
            seen.add(tool_name)

    return tools


def _parse_permission_rule(rule: str) -> tuple[str, str, str]:
    """Parse a permission rule string into (name, kind, description)."""
    builtin_tools = {
        "Bash",
        "Read",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "WebSearch",
        "WebFetch",
        "TodoWrite",
        "Agent",
        "NotebookEdit",
    }

    # Bare tool name e.g. "WebSearch"
    if re.match(r"^[A-Za-z]+$", rule):
        name = rule
        kind = "builtin" if name in builtin_tools else "unknown"
        return name, kind, f"Allowed tool: {name}"

    # ToolName(pattern) e.g. "Bash(git:*)" or "Bash(npm run build)"
    m = re.match(r"^(\w+)\((.+)\)$", rule)
    if m:
        tool_name = m.group(1)
        arg = m.group(2)
        if tool_name == "Bash":
            # Extract the command name
            cmd = arg.split(":")[0].split(" ")[0]
            kind = "shell" if cmd else "builtin"
            return cmd or tool_name, kind, f"Shell command: {arg}"
        if tool_name in builtin_tools:
            return tool_name, "builtin", f"Allowed: {rule}"
        return tool_name, "unknown", f"Allowed: {rule}"

    return "", "unknown", ""
