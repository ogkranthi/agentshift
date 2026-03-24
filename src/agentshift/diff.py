"""AgentShift diff — portability matrix for an agent across target platforms."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table

from agentshift.ir import AgentIR

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

    return present


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
    return comp


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
