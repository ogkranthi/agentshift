"""GCP Vertex AI Agent Builder emitter — converts AgentShift IR into Vertex AI agent artifacts.

Produces:
  agent.json  — Vertex AI Agent Builder configuration
  README.md   — deploy instructions (gcloud commands)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from agentshift.ir import AgentIR

_MAX_GOAL_CHARS = 8000
_MAX_INSTRUCTION_CHARS = 500
_MAX_INSTRUCTIONS = 20


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write Vertex AI Agent Builder artifacts from an AgentIR."""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_agent_json(ir, output_dir)
    _write_readme(ir, output_dir)


# ---------------------------------------------------------------------------
# agent.json
# ---------------------------------------------------------------------------


def _build_goal(ir: AgentIR) -> str:
    """Build the Vertex AI goal field.

    When persona.sections is present, uses sections['overview'] as the goal.
    Falls back to system_prompt when sections is absent.
    """
    sections = ir.persona.sections
    if sections:
        overview = sections.get("overview")
        if overview:
            return overview[:_MAX_GOAL_CHARS]

    raw = (ir.persona.system_prompt or "").strip()
    if not raw:
        raw = ir.description
    return raw[:_MAX_GOAL_CHARS]


def _build_structured_instructions(ir: AgentIR) -> list[str]:
    """Build instructions from persona.sections when available.

    Per spec §5.2:
    - behavior + persona + tools + knowledge → instructions body
    - guardrails → appended as "Restrictions:" block
    - examples → omitted

    Returns list of instruction strings (≤ 500 chars each, max 20).
    """
    sections = ir.persona.sections
    if not sections:
        return []

    parts: list[str] = []

    # Primary instruction sections
    for key in ["behavior", "persona", "tools", "knowledge"]:
        val = sections.get(key)
        if val:
            heading = key.replace("-", " ").title()
            parts.append(f"{heading}:\n{val}")

    # Custom sections (not overview, guardrails, examples, preamble)
    skip = {
        "overview",
        "behavior",
        "persona",
        "tools",
        "knowledge",
        "guardrails",
        "examples",
        "preamble",
    }
    for key, val in sections.items():
        if key not in skip and val:
            heading = key.replace("-", " ").title()
            parts.append(f"{heading}:\n{val}")

    # Guardrails appended as "Restrictions:" block
    guardrails = sections.get("guardrails")
    if guardrails:
        parts.append(f"Restrictions:\n{guardrails}")

    # Split into individual lines for the instructions array
    instructions: list[str] = []
    for part in parts:
        for line in part.splitlines():
            line = line.strip()
            if not line:
                continue
            instructions.append(line[:_MAX_INSTRUCTION_CHARS])
            if len(instructions) >= _MAX_INSTRUCTIONS:
                return instructions

    return instructions


def _extract_instructions(system_prompt: str) -> list[str]:
    """Split system_prompt into up to 20 non-empty, non-heading lines (≤ 500 chars each)."""
    instructions: list[str] = []
    for line in system_prompt.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip markdown headings
        if re.match(r"^#{1,6}\s", line):
            continue
        instructions.append(line[:_MAX_INSTRUCTION_CHARS])
        if len(instructions) >= _MAX_INSTRUCTIONS:
            break
    return instructions


def _map_tools(ir: AgentIR) -> list[dict]:
    tools: list[dict] = []
    for tool in ir.tools:
        if tool.kind == "shell":
            tools.append(
                {
                    "name": tool.name,
                    "type": "FUNCTION",
                    "description": tool.description
                    or f"Run the {tool.name} shell tool.",
                    "x-agentshift-stub": "Implement as Cloud Function or Cloud Run service",
                }
            )
        elif tool.kind == "mcp":
            desc = tool.description or f"Invoke action on {tool.name} MCP tool."
            tools.append(
                {
                    "name": tool.name,
                    "type": "FUNCTION",
                    "description": desc,
                    "x-agentshift-stub": f"Implement as MCP-compatible endpoint. {desc[:200]}",
                }
            )
        elif tool.kind == "openapi":
            tools.append(
                {
                    "name": tool.name,
                    "type": "OPEN_API",
                    "description": tool.description or f"OpenAPI tool: {tool.name}",
                }
            )
    return tools


def _write_agent_json(ir: AgentIR, output_dir: Path) -> None:
    goal = _build_goal(ir)
    sections = ir.persona.sections
    if sections:
        instructions = _build_structured_instructions(ir)
    else:
        raw_prompt = (ir.persona.system_prompt or "").strip()
        instructions = _extract_instructions(raw_prompt) if raw_prompt else []

    config = {
        "displayName": ir.name,
        "goal": goal,
        "instructions": instructions,
        "tools": _map_tools(ir),
        "defaultLanguageCode": "en",
        "supportedLanguageCodes": ["en"],
    }

    (output_dir / "agent.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


def _slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _write_readme(ir: AgentIR, output_dir: Path) -> None:
    slug = _slug(ir.name)

    lines: list[str] = [
        f"# {ir.name} — GCP Vertex AI Agent",
        "",
        ir.description,
        "",
        "> **Converted from OpenClaw by [AgentShift](https://agentshift.sh)**",
        "",
        "## Generated Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        "| `agent.json` | Vertex AI Agent Builder configuration |",
        "| `README.md` | This file — setup and deploy instructions |",
        "",
        "## Prerequisites",
        "",
        "1. A Google Cloud project with billing enabled",
        "2. The `gcloud` CLI installed and authenticated:",
        "",
        "```bash",
        "gcloud auth login",
        "gcloud config set project YOUR_PROJECT_ID",
        "```",
        "",
        "3. Enable required APIs:",
        "",
        "```bash",
        "gcloud services enable aiplatform.googleapis.com",
        "```",
        "",
        "## Deploy",
        "",
        "### Import the agent",
        "",
        "```bash",
        "gcloud alpha agent-builder agents import \\",
        f"  --agent-id={slug} \\",
        "  --source=agent.json \\",
        "  --location=us-central1",
        "```",
        "",
        "### Test the agent",
        "",
        "```bash",
        "gcloud alpha agent-builder agents run \\",
        f"  --agent-id={slug} \\",
        "  --location=us-central1 \\",
        '  --query="Hello!"',
        "```",
        "",
    ]

    stub_tools = [t for t in ir.tools if t.kind in ("shell", "mcp")]
    if stub_tools:
        lines += [
            "## Tools (Stubs — manual implementation required)",
            "",
            "The following tools are marked as stubs and require implementation as",
            "Cloud Functions or Cloud Run services before the agent is fully functional:",
            "",
        ]
        for tool in stub_tools:
            if tool.kind == "shell":
                lines.append(
                    f"- **{tool.name}** (shell) — implement as Cloud Function or Cloud Run service"
                )
            elif tool.kind == "mcp":
                lines.append(
                    f"- **{tool.name}** (mcp) — implement as MCP-compatible endpoint"
                )
        lines += [
            "",
            "See the [Vertex AI Agent Builder docs](https://cloud.google.com/vertex-ai/docs/agent-builder/create-manage-agents) for integration details.",
            "",
        ]

    if ir.knowledge:
        lines += [
            "## Knowledge (Stubs)",
            "",
            "Knowledge sources require a Vertex AI Search data store or Agent Builder data store:",
            "",
        ]
        for ks in ir.knowledge:
            lines.append(
                f"- **{ks.name}** ({ks.kind}) — {ks.description or 'no description'}"
            )
        lines += [
            "",
            "See the [Vertex AI data stores guide](https://cloud.google.com/generative-ai-app-builder/docs/create-datastore-ingest) for setup instructions.",
            "",
        ]

    cron_triggers = [t for t in ir.triggers if t.kind == "cron"]
    if cron_triggers:
        lines += [
            "## Scheduled Triggers (Cloud Scheduler stubs)",
            "",
            "Use Cloud Scheduler to invoke this agent on a schedule:",
            "",
        ]
        for trigger in cron_triggers:
            lines += [
                f"### {trigger.id or 'trigger'}",
                "",
                "```bash",
                "gcloud scheduler jobs create http \\",
                f"  --schedule='{trigger.cron_expr or '0 9 * * *'}' \\",
                "  --uri=YOUR_AGENT_ENDPOINT \\",
                f"  --message-body='{trigger.message or 'Run agent'}' \\",
                "  --location=us-central1",
                "```",
                "",
            ]

    lines += [
        "## About",
        "",
        "This agent was automatically converted using AgentShift.",
        "",
        "- **Source format:** OpenClaw SKILL.md",
        "- **Target format:** GCP Vertex AI Agent Builder",
        "- **Converter:** [AgentShift](https://agentshift.sh)",
        "",
        "To convert other OpenClaw skills:",
        "```bash",
        "agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to vertex --output /tmp/vertex-output",
        "```",
    ]

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
