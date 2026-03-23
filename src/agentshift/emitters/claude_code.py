"""Claude Code emitter — converts AgentShift IR into CLAUDE.md + settings.json."""

from __future__ import annotations

import json
from pathlib import Path

from agentshift.ir import AgentIR


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write a Claude Code agent directory from an AgentIR."""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_claude_md(ir, output_dir)
    _write_settings_json(ir, output_dir)


def _write_claude_md(ir: AgentIR, output_dir: Path) -> None:
    lines: list[str] = []

    lines.append(f"# {ir.name}")
    lines.append("")
    lines.append(ir.description)
    lines.append("")

    if ir.persona and ir.persona.system_prompt:
        lines.append("## Instructions")
        lines.append("")
        lines.append(ir.persona.system_prompt.strip())
        lines.append("")

    if ir.tools:
        lines.append("## Tools")
        lines.append("")
        for tool in ir.tools:
            lines.append(f"- **{tool.name}** ({tool.kind}): {tool.description}")
        lines.append("")

    if ir.knowledge:
        lines.append("## Knowledge")
        lines.append("")
        for ks in ir.knowledge:
            path_info = f" — `{ks.path}`" if ks.path else ""
            lines.append(f"- **{ks.name}**{path_info}: {ks.description or ''}")
        lines.append("")

    if ir.constraints.guardrails:
        lines.append("## Guardrails")
        lines.append("")
        for g in ir.constraints.guardrails:
            lines.append(f"- {g}")
        lines.append("")

    (output_dir / "CLAUDE.md").write_text("\n".join(lines), encoding="utf-8")


def _write_settings_json(ir: AgentIR, output_dir: Path) -> None:
    allow: list[str] = []
    deny: list[str] = []

    for tool in ir.tools:
        if tool.kind == "shell":
            allow.append(f"Bash({tool.name}:*)")
        elif tool.kind == "builtin":
            allow.append(tool.name)
        elif tool.kind == "mcp":
            allow.append(f"mcp__{tool.name}__*")

    # Guardrail-based denies
    if "no-web-search" in ir.constraints.guardrails:
        deny.append("WebSearch")

    settings: dict = {"permissions": {}}
    if allow:
        settings["permissions"]["allow"] = allow
    if deny:
        settings["permissions"]["deny"] = deny

    if ir.constraints.supported_os:
        settings["supportedOs"] = ir.constraints.supported_os

    (output_dir / "settings.json").write_text(
        json.dumps(settings, indent=2), encoding="utf-8"
    )
