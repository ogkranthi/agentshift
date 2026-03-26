"""Microsoft 365 Declarative Agent emitter.

Produces:
  declarative-agent.json   — agent manifest (schema v1.4, max 8,000 char instructions)
  manifest.json            — Teams app manifest (v1.17) referencing the agent
  instructions-full.txt    — (optional) full instructions when truncated
  README.md                — deployment instructions
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from agentshift.ir import AgentIR

_MAX_INSTRUCTIONS = 8000
_TRUNCATION_SAFE_LIMIT = 7800

_DECLARATIVE_AGENT_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/copilot/declarative-agent/v1.4/schema.json"
)
_TEAMS_MANIFEST_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/teams/v1.17/MicrosoftTeams.schema.json"
)

# MCP tool names that map to known M365 capabilities
_MCP_CAPABILITY_MAP: dict[str, dict] = {
    "teams": {"name": "TeamsMessages"},
    "email": {"name": "Email"},
    "notion": {
        "name": "GraphConnectors",
        "connections": [{"connectionId": "TODO-replace-with-graph-connection-id"}],
    },
    "graph": {
        "name": "GraphConnectors",
        "connections": [{"connectionId": "TODO-replace-with-graph-connection-id"}],
    },
}

# Shell tool command patterns that imply web access
_WEB_PATTERNS = re.compile(r"\bcurl\b|\bwget\b|\bhttp\b|\bweb\b|\bfetch\b", re.IGNORECASE)


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write M365 Declarative Agent artifacts from an AgentIR."""
    output_dir.mkdir(parents=True, exist_ok=True)

    instructions, truncated = _build_instructions(ir)
    capabilities = _build_capabilities(ir)
    starters = _extract_conversation_starters(ir)

    _write_declarative_agent(ir, output_dir, instructions, capabilities, starters)
    _write_manifest(ir, output_dir)
    if truncated:
        raw = (ir.persona.system_prompt or "").strip() or ir.description
        (output_dir / "instructions-full.txt").write_text(raw, encoding="utf-8")
    _write_readme(ir, output_dir)


# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------


def _build_instructions(ir: AgentIR) -> tuple[str, bool]:
    """Return (instructions_text, was_truncated)."""
    raw = (ir.persona.system_prompt or "").strip()
    if not raw:
        raw = ir.description

    if len(raw) <= _MAX_INSTRUCTIONS:
        return raw, False

    notice = "[AGENTSHIFT: truncated to 8,000 char M365 limit. Full text in instructions-full.txt]"
    max_body = _TRUNCATION_SAFE_LIMIT

    candidate = raw[:max_body]
    match = re.search(r"[.!?][^.!?]*$", candidate)
    if match:
        candidate = candidate[: match.start() + 1]
    else:
        ws = candidate.rfind(" ")
        if ws > 0:
            candidate = candidate[:ws]

    truncated_text = candidate + "\n\n" + notice
    return truncated_text, True


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


def _build_capabilities(ir: AgentIR) -> list[dict]:
    """Map IR tools/knowledge to M365 capability objects."""
    caps: list[dict] = []
    seen: set[str] = set()
    dropped_shell: list[str] = []

    # MCP tools
    for tool in ir.tools:
        if tool.kind == "mcp":
            cap = _MCP_CAPABILITY_MAP.get(tool.name.lower())
            if cap is not None:
                key = cap["name"]
                if key not in seen:
                    seen.add(key)
                    caps.append(dict(cap))
            # MCP tools not in the map are silently dropped (no M365 equivalent)

        elif tool.kind == "shell":
            desc = (tool.description or "") + " " + tool.name
            if _WEB_PATTERNS.search(desc):
                if "WebSearch" not in seen:
                    seen.add("WebSearch")
                    caps.append({"name": "WebSearch"})
            else:
                dropped_shell.append(tool.name)

    # URL knowledge → WebSearch with sites
    url_sites = [{"url": ks.path} for ks in ir.knowledge if ks.kind == "url" and ks.path]
    if url_sites:
        if "WebSearch" in seen:
            # Merge sites into existing WebSearch cap
            for cap in caps:
                if cap.get("name") == "WebSearch":
                    existing = cap.get("sites", [])
                    cap["sites"] = existing + url_sites
                    break
        else:
            seen.add("WebSearch")
            caps.append({"name": "WebSearch", "sites": url_sites})

    return caps


# ---------------------------------------------------------------------------
# Conversation starters
# ---------------------------------------------------------------------------

_STARTER_SECTIONS = re.compile(
    r"(?:when to use|examples?|try|getting started)[^\n]*\n((?:\s*[-*].+\n?)+)",
    re.IGNORECASE,
)


def _extract_conversation_starters(ir: AgentIR) -> list[dict]:
    """Extract up to 6 conversation starters from the system prompt."""
    text = ir.persona.system_prompt or ""
    starters: list[dict] = []

    for section_match in _STARTER_SECTIONS.finditer(text):
        block = section_match.group(1)
        for bullet_match in re.finditer(r"[-*]\s+(.+)", block):
            line = bullet_match.group(1).strip()
            if not line:
                continue
            title = line[:50].rstrip(".").strip()
            starters.append({"title": title, "text": line})
            if len(starters) >= 6:
                return starters

    return starters


# ---------------------------------------------------------------------------
# declarative-agent.json
# ---------------------------------------------------------------------------


def _write_declarative_agent(
    ir: AgentIR,
    output_dir: Path,
    instructions: str,
    capabilities: list[dict],
    starters: list[dict],
) -> None:
    doc: dict = {
        "$schema": _DECLARATIVE_AGENT_SCHEMA,
        "version": "v1.4",
        "name": ir.name,
        "description": (ir.description or "")[:1000],
        "instructions": instructions,
    }

    if capabilities:
        doc["capabilities"] = capabilities

    if starters:
        doc["conversation_starters"] = starters

    (output_dir / "declarative-agent.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# manifest.json
# ---------------------------------------------------------------------------


def _write_manifest(ir: AgentIR, output_dir: Path) -> None:
    description = ir.description or ""

    doc = {
        "$schema": _TEAMS_MANIFEST_SCHEMA,
        "manifestVersion": "1.17",
        "version": "1.0.0",
        "id": str(uuid.uuid4()),
        "name": {
            "short": ir.name,
            "full": description[:100],
        },
        "description": {
            "short": description[:80],
            "full": description[:4000],
        },
        "icons": {
            "color": "color.png",
            "outline": "outline.png",
        },
        "accentColor": "#6264A7",
        "copilotAgents": {
            "declarativeAgents": [
                {
                    "id": "declarativeAgent",
                    "file": "declarative-agent.json",
                }
            ]
        },
        "permissions": ["identity", "messageTeamMembers"],
        "validDomains": [],
    }

    (output_dir / "manifest.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


def _write_readme(ir: AgentIR, output_dir: Path) -> None:
    dropped_shell = [
        t.name
        for t in ir.tools
        if t.kind == "shell" and not _WEB_PATTERNS.search((t.description or "") + " " + t.name)
    ]
    dropped_mcp = [
        t.name for t in ir.tools if t.kind == "mcp" and t.name.lower() not in _MCP_CAPABILITY_MAP
    ]
    gc_tools = [
        t.name
        for t in ir.tools
        if t.kind == "mcp" and t.name.lower() in ("graph", "notion")
    ]

    lines: list[str] = [
        f"# {ir.name} — Microsoft 365 Declarative Agent",
        "",
        ir.description or "",
        "",
        "> **Converted from OpenClaw by [AgentShift](https://agentshift.sh)**",
        "",
        "## Generated Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        "| `declarative-agent.json` | Agent manifest with instructions and capabilities |",
        "| `manifest.json` | Teams app manifest referencing the declarative agent |",
        "| `README.md` | This file |",
        "",
    ]

    if dropped_shell or dropped_mcp or gc_tools:
        lines += [
            "## Conversion Notes",
            "",
        ]
        if gc_tools:
            lines += [
                "### Graph Connectors Setup",
                "",
                "The following tools map to Microsoft Graph Connectors and require a real connection ID:",
                "",
            ]
            for name in gc_tools:
                lines.append(
                    f"- `{name}` — TODO: replace `TODO-replace-with-graph-connection-id` in"
                    f" `declarative-agent.json` with the real connection ID from Microsoft 365 Admin Center"
                )
            lines.append("")
        if dropped_shell:
            lines += [
                "### Dropped Shell Tools",
                "",
                "The following shell tools have no M365 equivalent and were dropped:",
                "",
            ]
            for name in dropped_shell:
                lines.append(f"- `{name}` — TODO: implement manually if needed")
            lines.append("")

        if dropped_mcp:
            lines += [
                "### Dropped MCP Tools",
                "",
                "The following MCP tools have no direct M365 capability mapping and were dropped:",
                "",
            ]
            for name in dropped_mcp:
                lines.append(f"- `{name}` — TODO: check M365 connector catalog")
            lines.append("")

    lines += [
        "## Prerequisites",
        "",
        "- Microsoft 365 tenant with Copilot license",
        "- Admin access to Teams Admin Center or Microsoft 365 Developer Portal",
        "- Two icon files: `color.png` (192x192 px) and `outline.png` (32x32 px)",
        "",
        "## Deploy",
        "",
        "### 1. Add Icons",
        "",
        "Place your `color.png` and `outline.png` icons in this directory.",
        "Teams Toolkit provides default icons if you don't have custom ones.",
        "",
        "### 2. Package",
        "",
        "```bash",
        "zip -j agent-package.zip declarative-agent.json manifest.json color.png outline.png",
        "```",
        "",
        "### 3. Upload",
        "",
        "Upload via **Teams Admin Center**:",
        "- Go to **Teams apps > Manage apps > Upload new app**",
        "- Select `agent-package.zip`",
        "",
        "Or use the **Microsoft 365 Developer Portal**:",
        "- Visit https://dev.teams.microsoft.com/",
        "- Import the app package",
        "",
        "### 4. (Optional) Teams Toolkit",
        "",
        "If you use VS Code with Teams Toolkit:",
        "```bash",
        "teamsapp package",
        "teamsapp deploy",
        "```",
        "",
        "## About",
        "",
        "This agent was automatically converted using AgentShift.",
        "",
        "- **Source format:** OpenClaw SKILL.md",
        "- **Target format:** Microsoft 365 Declarative Agent",
        "- **Converter:** [AgentShift](https://agentshift.sh)",
        "",
        "To convert other OpenClaw skills:",
        "```bash",
        "agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to m365 --output /tmp/m365-output",
        "```",
    ]

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
