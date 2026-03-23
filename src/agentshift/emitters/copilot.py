"""GitHub Copilot emitter — converts AgentShift IR into .agent.md format."""

from __future__ import annotations

import re
from pathlib import Path

from agentshift.ir import AgentIR

_DEFAULT_MODELS = [
    "Claude Sonnet 4.6 (copilot)",
    "Claude Opus 4.6 (copilot)",
    "GPT-5.3-Codex",
]


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write a GitHub Copilot agent directory from an AgentIR."""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_agent_md(ir, output_dir)
    _write_readme(ir, output_dir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_tools(ir: AgentIR) -> list[str]:
    """Derive Copilot tool IDs from IR tools + knowledge + data writes."""
    tools: list[str] = []
    seen: set[str] = set()

    def add(t: str) -> None:
        if t not in seen:
            tools.append(t)
            seen.add(t)

    for tool in ir.tools:
        if tool.kind == "shell":
            add("execute/runInTerminal")
        elif tool.kind == "mcp":
            # MCP servers can't be declared in .agent.md — handled as comments
            pass
        elif tool.kind in ("builtin", "function", "unknown"):
            name_lower = tool.name.lower()
            if any(k in name_lower for k in ("web", "search", "fetch", "curl", "http")):
                add("web")
                add("search")

    # web_search / curl anywhere in tool names
    for tool in ir.tools:
        if tool.name.lower() in ("web_search", "websearch", "curl"):
            add("web")
            add("search")

    # knowledge files → read/readFile
    if ir.knowledge:
        add("read/readFile")

    # data writes detected in system prompt → edit/editFiles
    if ir.persona and ir.persona.system_prompt:
        write_re = re.compile(
            r"(?:append to|write to|log to|save to|create|edit)\s+[`'\"]?"
            r"((?:~/|/|\./)[\w./-]+|[\w/-]+\.(?:md|json|txt|log|csv|yaml|yml|toml))",
            re.IGNORECASE,
        )
        if write_re.search(ir.persona.system_prompt):
            add("edit/editFiles")

    # If any shell tool exists but we haven't added read/edit yet, files may be needed
    if "execute/runInTerminal" in seen and "read/readFile" not in seen:
        pass  # Don't add speculatively — only add when there's evidence

    return tools


def _mcp_tools(ir: AgentIR) -> list[str]:
    """Return names of MCP tools (need external server config)."""
    return [t.name for t in ir.tools if t.kind == "mcp"]


def _slug(name: str) -> str:
    """Convert agent name to filename slug."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _write_agent_md(ir: AgentIR, output_dir: Path) -> None:
    tools = _build_tools(ir)
    mcp_names = _mcp_tools(ir)

    # YAML frontmatter
    lines: list[str] = ["---"]
    lines.append(f'name: "{ir.name}"')
    lines.append(f'description: "{ir.description}"')
    lines.append("model:")
    for m in _DEFAULT_MODELS:
        lines.append(f'  - "{m}"')
    if tools:
        lines.append("tools:")
        for t in tools:
            lines.append(f"  - {t}")
    else:
        lines.append("tools: []")
    lines.append("---")
    lines.append("")

    # MCP comment block (before body)
    if mcp_names:
        for mcp in mcp_names:
            lines.append(f"<!-- MCP: configure {mcp} server separately in VS Code settings -->")
        lines.append("")

    # Body: system prompt
    if ir.persona and ir.persona.system_prompt:
        lines.append(ir.persona.system_prompt.strip())
    else:
        lines.append(f"# {ir.name}")
        lines.append("")
        lines.append(ir.description)

    lines.append("")

    filename = f"{_slug(ir.name)}.agent.md"
    (output_dir / filename).write_text("\n".join(lines), encoding="utf-8")


def _write_readme(ir: AgentIR, output_dir: Path) -> None:
    mcp_names = _mcp_tools(ir)
    slug = _slug(ir.name)
    filename = f"{slug}.agent.md"

    lines: list[str] = [
        f"# {ir.name} — GitHub Copilot Agent",
        "",
        ir.description,
        "",
        "> **Converted from OpenClaw by [AgentShift](https://github.com/agentshift/agentshift)**",
        "",
        "## Installation",
        "",
        "### VS Code (recommended)",
        "",
        "1. Open VS Code.",
        "2. Open the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`).",
        "3. Run **GitHub Copilot: Install Agent from File**.",
        f"4. Select `{filename}` from this directory.",
        "5. The agent will appear in the Copilot Chat agent picker (`@` menu).",
        "",
        "### Manual install",
        "",
        "Copy the `.agent.md` file to your VS Code user agents directory:",
        "",
        "- **macOS/Linux:** `~/.vscode/extensions/github.copilot-*/agents/`",
        "- **Windows:** `%USERPROFILE%\\.vscode\\extensions\\github.copilot-*\\agents\\`",
        "",
        "Or place it in your workspace at `.github/copilot-agents/` to share with your team.",
        "",
    ]

    if mcp_names:
        lines += [
            "## MCP Servers Required",
            "",
            "This agent uses MCP (Model Context Protocol) tools that require server-side configuration.",
            "Add the following to your VS Code `settings.json`:",
            "",
            "```json",
            '"github.copilot.chat.agent.mcp.server": {',
        ]
        for name in mcp_names:
            lines += [
                f'  "{name}": {{',
                f'    "command": "npx",',
                f'    "args": ["-y", "@modelcontextprotocol/server-{name}"]',
                "  },",
            ]
        lines += [
            "}",
            "```",
            "",
            "> **Note:** Exact server configuration depends on the MCP server package.",
            "> Consult each server's documentation for the correct `command` and `args`.",
            "",
        ]

    lines += [
        "## About",
        "",
        "This agent was automatically converted from an OpenClaw skill using AgentShift.",
        "",
        "- **Source format:** OpenClaw SKILL.md",
        "- **Target format:** GitHub Copilot `.agent.md`",
        "- **Converter:** [AgentShift](https://github.com/agentshift/agentshift)",
        "",
        "To convert other OpenClaw skills:",
        "```bash",
        "agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to copilot --output /tmp/copilot-output",
        "```",
    ]

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
