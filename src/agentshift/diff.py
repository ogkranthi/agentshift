"""AgentShift diff — portability matrix for an agent across target platforms."""

from __future__ import annotations

import difflib

from rich import box
from rich.console import Console
from rich.table import Table

from agentshift.ir import AgentIR

# ---------------------------------------------------------------------------
# Section-to-platform mapping (which platforms have a direct mapping)
# ---------------------------------------------------------------------------
# Maps canonical section slug → set of platforms that handle it explicitly.
# 'guardrails' on bedrock is "mapped" because it routes to guardrailConfiguration.
SECTION_PLATFORM_SUPPORT: dict[str, set[str]] = {
    "overview": {"claude-code", "copilot", "vertex", "m365"},
    "behavior": {"claude-code", "copilot", "bedrock", "vertex", "m365"},
    "guardrails": {"claude-code", "copilot", "bedrock", "vertex", "m365"},
    "tools": {"claude-code", "copilot", "bedrock", "vertex", "m365"},
    "knowledge": {"claude-code", "copilot", "bedrock", "vertex", "m365"},
    "persona": {"claude-code", "copilot", "bedrock", "vertex", "m365"},
    "examples": {"claude-code", "copilot"},  # Others omit for budget reasons
    "triggers": {"claude-code"},
    "output-format": {"claude-code", "copilot", "bedrock", "vertex", "m365"},
    "auth": {"claude-code"},
}

# ---------------------------------------------------------------------------
# Fidelity levels
# ---------------------------------------------------------------------------
FULL = "full"
PARTIAL = "partial"
STUB = "stub"
NONE = "none"

# ---------------------------------------------------------------------------
# Weight of each component for portability score (must sum to 100)
# ---------------------------------------------------------------------------
COMPONENT_WEIGHTS = {
    "instructions": 30,
    "tools_shell": 15,
    "tools_mcp": 10,
    "knowledge": 15,
    "triggers_cron": 15,
    "triggers_delivery": 10,
    "constraints": 5,
    "persona_sections": 0,  # Informational only — does not affect portability score
}

# ---------------------------------------------------------------------------
# Platform support matrix
# ---------------------------------------------------------------------------
PLATFORM_SUPPORT: dict[str, dict[str, str]] = {
    "claude-code": {
        "instructions": FULL,
        "tools_shell": FULL,
        "tools_mcp": FULL,
        "knowledge": FULL,
        "triggers_cron": PARTIAL,
        "triggers_delivery": STUB,
        "constraints": FULL,
    },
    "copilot": {
        "instructions": FULL,
        "tools_shell": FULL,
        "tools_mcp": PARTIAL,
        "knowledge": FULL,
        "triggers_cron": NONE,
        "triggers_delivery": NONE,
        "constraints": STUB,
    },
    "bedrock": {
        "instructions": PARTIAL,
        "tools_shell": NONE,
        "tools_mcp": STUB,
        "knowledge": PARTIAL,
        "triggers_cron": STUB,
        "triggers_delivery": NONE,
        "constraints": STUB,
    },
    "m365": {
        "instructions": FULL,
        "tools_shell": NONE,
        "tools_mcp": PARTIAL,
        "knowledge": PARTIAL,
        "triggers_cron": NONE,
        "triggers_delivery": NONE,
        "constraints": STUB,
    },
    "vertex": {
        "instructions": FULL,
        "tools_shell": STUB,
        "tools_mcp": STUB,
        "knowledge": STUB,
        "triggers_cron": STUB,
        "triggers_delivery": NONE,
        "constraints": STUB,
    },
}

FIDELITY_SCORE = {FULL: 100, PARTIAL: 60, STUB: 20, NONE: 0}

FIDELITY_SYMBOL = {
    FULL: ("✅", "green"),
    PARTIAL: ("⚠️ ", "yellow"),
    STUB: ("⚠️ ", "yellow"),
    NONE: ("❌", "red"),
}

FIDELITY_LABEL: dict[str, dict[str, str]] = {
    "instructions": {
        FULL: "100%",
        PARTIAL: "truncated",
        STUB: "stub",
        NONE: "dropped",
    },
    "tools_shell": {
        FULL: "Bash(bin:*)",
        PARTIAL: "generic",
        STUB: "stub",
        NONE: "dropped",
    },
    "tools_mcp": {
        FULL: "mcp__name__*",
        PARTIAL: "MCP*",
        STUB: "stub",
        NONE: "dropped",
    },
    "knowledge": {
        FULL: "Read(path)",
        PARTIAL: "partial",
        STUB: "stub",
        NONE: "dropped",
    },
    "triggers_cron": {
        FULL: "native",
        PARTIAL: "/schedule",
        STUB: "stub",
        NONE: "❌ none",
    },
    "triggers_delivery": {
        FULL: "native",
        PARTIAL: "workaround",
        STUB: "stub",
        NONE: "❌ none",
    },
    "constraints": {
        FULL: "supportedOs",
        PARTIAL: "partial",
        STUB: "stub",
        NONE: "dropped",
    },
}

# Human-friendly notes per (target, component, fidelity)
_NOTES: dict[str, dict[str, dict[str, str]]] = {
    "claude-code": {
        "triggers_cron": {
            PARTIAL: "Cron triggers use /schedule — cloud-only, no proactive delivery",
        },
        "triggers_delivery": {
            STUB: "No native Telegram/Slack push; manual webhook integration required",
        },
    },
    "copilot": {
        "tools_mcp": {
            PARTIAL: "MCP tools require separate MCP server configuration",
        },
        "triggers_cron": {
            NONE: "No scheduled triggers (chat-only)",
        },
        "triggers_delivery": {
            NONE: "No proactive delivery support",
        },
        "constraints": {
            STUB: "No direct OS/binary constraint equivalent",
        },
    },
    "m365": {
        "instructions": {
            FULL: "8,000 character limit — instructions truncated if exceeded",
        },
        "tools_shell": {
            NONE: "No shell access in M365 Declarative Agents — shell tools dropped",
        },
        "tools_mcp": {
            PARTIAL: "Only Teams/Email/Graph MCP tools map to capabilities; others dropped",
        },
        "knowledge": {
            PARTIAL: "URL-based WebSearch supported; local files dropped",
        },
        "triggers_cron": {
            NONE: "No scheduled triggers in M365 Declarative Agents",
        },
        "triggers_delivery": {
            NONE: "No proactive delivery support",
        },
        "constraints": {
            STUB: "No direct OS/binary constraint equivalent",
        },
    },
    "vertex": {
        "instructions": {
            FULL: "8,000 character limit — goal field in agent.json",
        },
        "tools_shell": {
            STUB: "Shell tools stubbed — implement as Cloud Function or Cloud Run service",
        },
        "tools_mcp": {
            STUB: "MCP tools stubbed — implement as MCP-compatible endpoint",
        },
        "knowledge": {
            STUB: "Knowledge sources stubbed — requires Vertex AI Search data store",
        },
        "triggers_cron": {
            STUB: "Cloud Scheduler stubs generated — manual wiring required",
        },
        "triggers_delivery": {
            NONE: "No proactive delivery support",
        },
        "constraints": {
            STUB: "No direct OS/binary constraint equivalent",
        },
    },
    "bedrock": {
        "instructions": {
            PARTIAL: "4,000 character limit on system prompt — instructions may be truncated",
        },
        "tools_shell": {
            NONE: "No shell access in Bedrock agents",
        },
        "tools_mcp": {
            STUB: "Action groups require manual conversion from MCP",
        },
        "knowledge": {
            PARTIAL: "S3 knowledge base — requires manual setup and indexing",
        },
        "triggers_cron": {
            STUB: "EventBridge rules generated as stub — manual wiring required",
        },
        "triggers_delivery": {
            NONE: "No proactive delivery support",
        },
        "constraints": {
            STUB: "No direct OS/binary constraint equivalent",
        },
    },
}


def _active_components(ir: AgentIR) -> list[str]:
    """Return only the IR components that are actually present in the agent."""
    present: list[str] = []

    if ir.persona.system_prompt:
        present.append("instructions")

    shell_tools = [t for t in ir.tools if t.kind == "shell"]
    if shell_tools:
        present.append("tools_shell")

    mcp_tools = [t for t in ir.tools if t.kind == "mcp"]
    if mcp_tools:
        present.append("tools_mcp")

    if ir.knowledge:
        present.append("knowledge")

    cron_triggers = [t for t in ir.triggers if t.kind == "cron"]
    if cron_triggers:
        present.append("triggers_cron")

    delivery_triggers = [t for t in ir.triggers if t.delivery is not None]
    if delivery_triggers:
        present.append("triggers_delivery")

    if ir.constraints.supported_os or ir.constraints.required_bins:
        present.append("constraints")

    # Add persona_sections when sections are populated
    if ir.persona.sections:
        present.append("persona_sections")

    return present


def _count_mapped_sections(sections: dict[str, str], target: str) -> tuple[int, int]:
    """Return (mapped_count, total_count) for sections on a given target platform."""
    total = len(sections)
    mapped = 0
    for slug in sections:
        supported_platforms = SECTION_PLATFORM_SUPPORT.get(slug, set())
        if target in supported_platforms or (slug not in SECTION_PLATFORM_SUPPORT and target == "claude-code"):
            mapped += 1
    return mapped, total


def compute_diff(
    ir: AgentIR, targets: list[str]
) -> dict[str, dict[str, tuple[str, str, str | None]]]:
    """Return per-component per-target (fidelity, label, note) and per-target score.

    Return structure:
        {
            "components": {
                component_key: {
                    target: (fidelity, label, note_or_None)
                }
            },
            "scores": {target: score_0_to_100},
            "active": [component_key, ...],
        }
    """
    active = _active_components(ir)

    components: dict[str, dict[str, tuple[str, str, str | None]]] = {}
    for comp in active:
        components[comp] = {}
        for target in targets:
            if comp == "persona_sections":
                # Special handling: calculate per-section mapping coverage
                sections = ir.persona.sections or {}
                mapped, total = _count_mapped_sections(sections, target)
                if total == 0:
                    fidelity = NONE
                    label = "0/0"
                elif mapped == total:
                    fidelity = FULL
                    label = f"{mapped}/{total} mapped"
                elif mapped > 0:
                    fidelity = PARTIAL
                    label = f"{mapped}/{total} mapped"
                else:
                    fidelity = NONE
                    label = f"0/{total} mapped"
                components[comp][target] = (fidelity, label, None)
            else:
                support = PLATFORM_SUPPORT.get(target, {})
                fidelity = support.get(comp, NONE)
                label = FIDELITY_LABEL[comp][fidelity]
                note = _NOTES.get(target, {}).get(comp, {}).get(fidelity)
                components[comp][target] = (fidelity, label, note)

    # Score per target — weighted average over active components only
    scores: dict[str, float] = {}
    for target in targets:
        total_weight = sum(COMPONENT_WEIGHTS.get(c, 0) for c in active)
        if total_weight == 0:
            scores[target] = 100.0
            continue
        weighted_sum = sum(
            COMPONENT_WEIGHTS.get(comp, 0) * FIDELITY_SCORE[components[comp][target][0]]
            for comp in active
        )
        scores[target] = round(weighted_sum / total_weight, 1)

    return {"components": components, "scores": scores, "active": active}


def _score_color(score: float) -> str:
    if score >= 80:
        return "green"
    if score >= 50:
        return "yellow"
    return "red"


def _component_display(comp: str, ir: AgentIR) -> str:
    """Human label for a component row, including counts where useful."""
    if comp == "instructions":
        return "Instructions"
    if comp == "tools_shell":
        n = sum(1 for t in ir.tools if t.kind == "shell")
        return f"Tools (shell: {n})"
    if comp == "tools_mcp":
        n = sum(1 for t in ir.tools if t.kind == "mcp")
        return f"Tools (mcp: {n})"
    if comp == "knowledge":
        return f"Knowledge ({len(ir.knowledge)})"
    if comp == "triggers_cron":
        n = sum(1 for t in ir.triggers if t.kind == "cron")
        return f"Cron ({n} job{'s' if n != 1 else ''})"
    if comp == "triggers_delivery":
        channels = {t.delivery.channel for t in ir.triggers if t.delivery}
        ch_str = "/".join(sorted(c for c in channels if c)) if channels else ""
        return f"Delivery ({ch_str})" if ch_str else "Delivery"
    if comp == "constraints":
        return "Constraints"
    if comp == "persona_sections":
        n = len(ir.persona.sections or {})
        return f"Persona Sections ({n})"
    return comp


def _normalize_body(text: str) -> str:
    """Normalize section body for comparison — strip trailing spaces, collapse blank lines."""
    lines = [line.rstrip() for line in text.splitlines()]
    # Collapse multiple blank lines into one
    result: list[str] = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                result.append(line)
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return "\n".join(result).strip()


def diff_agents(ir_a: AgentIR, ir_b: AgentIR) -> list[dict]:
    """Compute section-level diff between two IRs.

    Returns list of dicts with keys: section, status, summary.
    Status values: 'unchanged', 'changed', 'added', 'removed'.
    """
    secs_a = ir_a.persona.sections or {}
    secs_b = ir_b.persona.sections or {}
    all_keys = sorted(set(secs_a) | set(secs_b))

    rows: list[dict] = []
    for key in all_keys:
        in_a = key in secs_a
        in_b = key in secs_b

        if in_a and in_b:
            norm_a = _normalize_body(secs_a[key])
            norm_b = _normalize_body(secs_b[key])
            if norm_a == norm_b:
                rows.append({"section": key, "status": "unchanged", "summary": "—"})
            else:
                lines_a = norm_a.splitlines()
                lines_b = norm_b.splitlines()
                matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
                added = sum(b2 - b1 for _, _, _, b1, b2 in matcher.get_opcodes() if _ != "equal")
                removed = sum(a2 - a1 for _, a1, a2, _, _ in matcher.get_opcodes() if _ != "equal")
                delta_parts = []
                if added:
                    delta_parts.append(f"+{added} line{'s' if added != 1 else ''}")
                if removed:
                    delta_parts.append(f"-{removed} line{'s' if removed != 1 else ''}")
                summary = ", ".join(delta_parts) if delta_parts else "whitespace only"
                rows.append({"section": key, "status": "changed", "summary": summary})
        elif in_b:
            char_count = len(secs_b[key])
            rows.append({"section": key, "status": "added", "summary": f"New section ({char_count} chars)"})
        else:
            rows.append({"section": key, "status": "removed", "summary": "Was present in v1"})

    return rows


def render_agent_diff_table(
    ir_a: AgentIR,
    ir_b: AgentIR,
    label_a: str = "agent-v1",
    label_b: str = "agent-v2",
    section_filter: str | None = None,
) -> None:
    """Render agent-to-agent section diff table to stdout."""
    console = Console()

    secs_a = ir_a.persona.sections or {}
    secs_b = ir_b.persona.sections or {}

    if not secs_a and not secs_b:
        # Fall back to unified diff of system_prompt
        prompt_a = ir_a.persona.system_prompt or ""
        prompt_b = ir_b.persona.system_prompt or ""
        unified = list(
            difflib.unified_diff(
                prompt_a.splitlines(keepends=True),
                prompt_b.splitlines(keepends=True),
                fromfile=label_a,
                tofile=label_b,
            )
        )
        if not unified:
            console.print("[green]Agents are identical (system_prompt).[/green]")
        else:
            console.print(f"[bold]{label_a}[/bold] ↔ [bold]{label_b}[/bold] — system_prompt diff\n")
            for line in unified:
                if line.startswith("+"):
                    console.print(f"[green]{line}[/green]", end="")
                elif line.startswith("-"):
                    console.print(f"[red]{line}[/red]", end="")
                else:
                    console.print(line, end="")
        return

    rows = diff_agents(ir_a, ir_b)

    if section_filter:
        matching = [r for r in rows if r["section"] == section_filter]
        if not matching:
            console.print(f"[yellow]Section '{section_filter}' not found in either agent.[/yellow]")
            return
        # Show full unified diff for the specific section
        body_a = secs_a.get(section_filter, "")
        body_b = secs_b.get(section_filter, "")
        unified = list(
            difflib.unified_diff(
                body_a.splitlines(keepends=True),
                body_b.splitlines(keepends=True),
                fromfile=f"{label_a}/{section_filter}",
                tofile=f"{label_b}/{section_filter}",
            )
        )
        console.print(f"[bold]Section diff: {section_filter}[/bold]\n")
        if not unified:
            console.print("[green]No differences.[/green]")
        else:
            for line in unified:
                if line.startswith("+"):
                    console.print(f"[green]{line}[/green]", end="")
                elif line.startswith("-"):
                    console.print(f"[red]{line}[/red]", end="")
                else:
                    console.print(line, end="")
        return

    status_display = {
        "unchanged": ("✅ unchanged", "green"),
        "changed": ("⚠️  changed", "yellow"),
        "added": ("🆕 added", "cyan"),
        "removed": ("❌ removed", "red"),
    }

    table = Table(
        title=f"[bold]{label_a}[/bold] ↔ [bold]{label_b}[/bold] — Section Diff",
        box=box.SIMPLE_HEAVY,
    )
    table.add_column("Section", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Summary")

    for row in rows:
        status_text, color = status_display.get(row["status"], (row["status"], "white"))
        table.add_row(
            row["section"],
            f"[{color}]{status_text}[/{color}]",
            row["summary"],
        )

    console.print()
    console.print(table)


def render_diff_table(ir: AgentIR, targets: list[str]) -> None:
    """Render a rich portability table to stdout."""
    console = Console()

    # Filter to known targets only
    unknown = [t for t in targets if t not in PLATFORM_SUPPORT]
    if unknown:
        console.print(f"[yellow]Warning:[/yellow] Unknown target(s) skipped: {', '.join(unknown)}")
        targets = [t for t in targets if t in PLATFORM_SUPPORT]

    if not targets:
        console.print("[red]No valid targets specified.[/red]")
        return

    result = compute_diff(ir, targets)
    components = result["components"]
    scores = result["scores"]
    active = result["active"]

    table = Table(
        title=f"[bold]{ir.name}[/bold] — Portability Report",
        box=box.SIMPLE_HEAVY,
        show_footer=True,
    )

    # Columns
    table.add_column("Component", style="bold", footer="Portability")
    table.add_column("Source", justify="center", footer="")
    for target in targets:
        score = scores[target]
        color = _score_color(score)
        table.add_column(
            target,
            justify="center",
            footer=f"[{color}]{score:.0f}%[/{color}]",
        )

    # Rows — one per active component
    notes: list[str] = []
    for comp in active:
        label = _component_display(comp, ir)
        row: list[str] = [label, "✅"]
        for target in targets:
            fidelity, flabel, note = components[comp][target]
            sym, color = FIDELITY_SYMBOL[fidelity]
            cell = f"[{color}]{sym} {flabel}[/{color}]"
            row.append(cell)
            if note:
                icon = "❌" if fidelity == NONE else "⚠️ "
                notes.append(f"  {icon}  [bold]{target}[/bold]: {note}")
        table.add_row(*row)

    console.print()
    console.print(table)

    if notes:
        console.print("[bold]Notes:[/bold]")
        for n in notes:
            console.print(n)
        console.print()
