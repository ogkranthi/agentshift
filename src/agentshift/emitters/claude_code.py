"""Claude Code emitter — converts AgentShift IR into CLAUDE.md + settings.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agentshift.elevation import ElevationResult, elevate_governance
from agentshift.ir import AgentIR


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write a Claude Code agent directory from an AgentIR."""
    output_dir.mkdir(parents=True, exist_ok=True)

    elevation = elevate_governance(ir, "claude-code")
    _write_claude_md(ir, output_dir, elevation)
    _write_settings_json(ir, output_dir, elevation)
    if ir.triggers:
        _write_schedules_md(ir, output_dir)


def _write_claude_md(ir: AgentIR, output_dir: Path, elevation: ElevationResult) -> None:
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

    # L1 guardrails (always preserved)
    if elevation.l1_preserved:
        lines.append("## Guardrails")
        lines.append("")
        for g in elevation.l1_preserved:
            lines.append(f"- {g.text}")
        lines.append("")

    # Legacy guardrails from constraints (backward compat)
    elif ir.constraints.guardrails:
        lines.append("## Guardrails")
        lines.append("")
        for g in ir.constraints.guardrails:
            lines.append(f"- {g}")
        lines.append("")

    # Elevated L2/L3 → L1 instructions
    if elevation.extra_instructions:
        lines.append("## Governance Constraints (Elevated)")
        lines.append("")
        lines.append("<!-- These constraints were elevated from enforcement-level (L2/L3)")
        lines.append("     to prompt-level (L1) because Claude Code does not natively support")
        lines.append("     the original enforcement mechanism. -->")
        lines.append("")
        for instr in elevation.extra_instructions:
            lines.append(f"- {instr}")
        lines.append("")

    (output_dir / "CLAUDE.md").write_text("\n".join(lines), encoding="utf-8")


def _write_settings_json(ir: AgentIR, output_dir: Path, elevation: ElevationResult) -> None:
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

    # L2 governance: apply preserved permissions as deny/allow rules
    for perm_obj in elevation.l2_preserved:
        if not perm_obj.enabled:
            # Disabled tools → deny
            tool_id = perm_obj.tool_name
            deny.append(f"Bash({tool_id}:*)")
        for pattern in perm_obj.deny_patterns:
            deny.append(f"Bash({perm_obj.tool_name} {pattern})")

    # Legacy guardrail-based denies
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


def _write_schedules_md(ir: AgentIR, output_dir: Path) -> None:
    """Write SCHEDULES.md with Claude Code setup instructions for each cron trigger."""
    lines: list[str] = []
    lines.append(f"# Scheduled Tasks — {ir.name}")
    lines.append("")
    lines.append(
        "This skill has scheduled triggers in OpenClaw. "
        "Below are the equivalent setups for Claude Code."
    )
    lines.append("")
    lines.append(
        "> **Note:** Delivery to Telegram/Slack/Discord is not natively supported in Claude Code. "
        "Use cloud scheduled tasks for durable scheduling, or see the workarounds below."
    )
    lines.append("")

    for trigger in ir.triggers:
        if trigger.kind != "cron":
            continue

        lines.append(f"## {trigger.id or 'trigger'}")
        lines.append("")
        if trigger.cron_expr:
            lines.append(f"**Schedule:** `{trigger.cron_expr}`")
        if trigger.delivery:
            ch = trigger.delivery.channel or "unknown"
            to = trigger.delivery.to or ""
            lines.append(f"**OpenClaw delivery:** {ch} → `{to}`")
        lines.append("")

        if trigger.message:
            lines.append("**Prompt:**")
            lines.append("```")
            lines.append(trigger.message.strip())
            lines.append("```")
            lines.append("")

        lines.append("**Set up in Claude Code:**")
        lines.append("")
        lines.append("Option 1 — Cloud scheduled task (recommended, survives restarts):")
        lines.append("```")
        lines.append("# In any Claude Code session:")
        if trigger.cron_expr:
            lines.append(
                f"/schedule cron({trigger.cron_expr}) {(trigger.message or '').splitlines()[0][:80]}"
            )
        lines.append("# Or visit: https://claude.ai/code/scheduled → New scheduled task")
        lines.append("```")
        lines.append("")
        lines.append("Option 2 — In-session loop (disappears when Claude Code exits):")
        lines.append("```")
        every = _cron_to_human(trigger.cron_expr or "")
        lines.append(f"/loop {every} {(trigger.message or '').splitlines()[0][:80]}")
        lines.append("```")
        lines.append("")

    (output_dir / "SCHEDULES.md").write_text("\n".join(lines), encoding="utf-8")


def _cron_to_human(expr: str) -> str:
    """Convert common cron expressions to a human interval for /loop."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return "1h"
    minute, hour, dom, month, dow = parts
    # Daily at specific hour
    if minute.isdigit() and hour.isdigit() and dom == "*" and month == "*" and dow == "*":
        return "1d"
    # Weekly
    if minute.isdigit() and hour.isdigit() and dom == "*" and month == "*" and dow.isdigit():
        return "7d"
    # Every N hours
    if minute.isdigit() and hour.startswith("*/"):
        n = hour[2:]
        return f"{n}h"
    # Every N minutes
    if minute.startswith("*/") and hour == "*":
        n = minute[2:]
        return f"{n}m"
    return "1h"
