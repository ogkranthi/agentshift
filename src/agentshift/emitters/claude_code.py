"""Claude Code emitter — converts AgentShift IR into CLAUDE.md + settings.json."""

from __future__ import annotations

import json
import re
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
            if tool.name == "bash":
                allow.append("Bash(*)")
            else:
                allow.append(f"Bash({tool.name}:*)")
        elif tool.kind == "builtin":
            allow.append(tool.name)
        elif tool.kind == "mcp":
            allow.append(f"mcp__{tool.name}__*")

    # Add permissions for required_bins declared in frontmatter (covers prose-only skills)
    tool_names_seen = {p for p in allow}
    for bin_name in ir.constraints.required_bins:
        perm = f"Bash({bin_name}:*)"
        if perm not in tool_names_seen:
            allow.append(perm)
            tool_names_seen.add(perm)
    for bin_name in ir.constraints.any_required_bins:
        perm = f"Bash({bin_name}:*)"
        if perm not in tool_names_seen:
            allow.append(perm)
            tool_names_seen.add(perm)

    # Read permissions for knowledge sources with file/directory paths
    for ks in ir.knowledge:
        if ks.kind in ("file", "directory") and ks.path:
            perm = f"Read({ks.path})"
            if perm not in allow:
                allow.append(perm)

    # Write permissions inferred from system prompt (require path-like string)
    if ir.persona and ir.persona.system_prompt:
        write_re = re.compile(
            r"(?:append to|write to|log to|save to)\s+[`'\"]?"
            r"((?:~/|/|\./)[\w./-]+|[\w/-]+\.(?:md|json|txt|log|csv|yaml|yml|toml))",
            re.IGNORECASE,
        )
        for m in write_re.finditer(ir.persona.system_prompt):
            file_path = m.group(1).rstrip(".,;")
            perm = f"Write({file_path})"
            if perm not in allow:
                allow.append(perm)

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

    (output_dir / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
