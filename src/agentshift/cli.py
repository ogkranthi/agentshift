"""AgentShift CLI — convert AI agents between platforms."""

from __future__ import annotations

import importlib
import json
import traceback
from difflib import get_close_matches
from pathlib import Path

import typer
from rich.console import Console

import agentshift

app = typer.Typer(
    name="agentshift",
    help="Convert AI agents between platforms. OpenClaw → Claude Code, GitHub Copilot, and more.",
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)

_PARSERS = {
    "openclaw": "agentshift.parsers.openclaw:parse_skill_dir",
    "claude-code": "agentshift.parsers.claude_code:parse_agent_dir",
    "bedrock": "agentshift.parsers.bedrock:parse",
    "vertex": "agentshift.parsers.vertex:parse",
    "copilot": "agentshift.parsers.copilot:parse",
    "agents-md": "agentshift.parsers.agents_md:parse",
}

_EMITTERS = {
    "claude-code": "agentshift.emitters.claude_code:emit",
    "copilot": "agentshift.emitters.copilot:emit",
    "bedrock": "agentshift.emitters.bedrock:emit",
    "m365": "agentshift.emitters.m365:emit",
    "vertex": "agentshift.emitters.vertex:emit",
    "langgraph": "agentshift.emitters.langgraph:emit",
    "a2a": "agentshift.emitters.a2a:emit",
}


class _State:
    verbose: bool = False


state = _State()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"agentshift {agentshift.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Enable verbose/debug output.",
        is_eager=False,
    ),
) -> None:
    state.verbose = verbose


def _did_you_mean(value: str, choices: list[str]) -> str | None:
    """Return the closest matching choice, or None if no good match."""
    matches = get_close_matches(value.lower(), choices, n=1, cutoff=0.5)
    return matches[0] if matches else None


def _get_parser(platform: str):
    if platform not in _PARSERS:
        err_console.print(f"[red]Unknown source platform:[/red] {platform!r}")
        suggestion = _did_you_mean(platform, list(_PARSERS))
        if suggestion:
            err_console.print(f"  Did you mean [bold]{suggestion}[/bold]?")
        err_console.print(f"  Supported platforms: {', '.join(_PARSERS)}")
        raise typer.Exit(1)
    module_path, fn_name = _PARSERS[platform].split(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


def _load_emitter(platform: str):
    module_path, fn_name = _EMITTERS[platform].split(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


def _parse_with_errors(parse_fn, source: Path):
    """Run a parser and surface friendly errors for common failure modes."""
    # Check source directory exists first
    if not source.exists():
        err_console.print(f"[red]Error:[/red] Source directory not found: [cyan]{source}[/cyan]")
        err_console.print("  Tip: provide the path to a directory containing a SKILL.md file.")
        raise typer.Exit(1)

    try:
        ir = parse_fn(source)
    except FileNotFoundError as e:
        msg = str(e)
        err_console.print(f"[red]Error:[/red] {msg}")
        if "SKILL.md" in msg:
            err_console.print(
                f"  Tip: [cyan]{source}[/cyan] must contain a SKILL.md file with valid YAML frontmatter."
            )
            err_console.print("  See: https://github.com/ogkranthi/agentshift#skill-format")
        elif "agent.json" in msg:
            err_console.print(
                f"  Tip: [cyan]{source}[/cyan] must contain an agent.json file (Vertex AI agent definition)."
            )
        elif "Bedrock artifact" in msg or "bedrock" in msg.lower():
            err_console.print(
                f"  Tip: [cyan]{source}[/cyan] must contain at least one of: "
                "bedrock-agent.json, cloudformation.yaml, instruction.txt"
            )
        if state.verbose:
            err_console.print(traceback.format_exc())
        raise typer.Exit(1) from e
    except ValueError as e:
        err_console.print(f"[red]Parse error:[/red] {e}")
        if state.verbose:
            err_console.print(traceback.format_exc())
        raise typer.Exit(1) from e
    except Exception as e:
        err_console.print(f"[red]Unexpected error while parsing:[/red] {e}")
        if state.verbose:
            err_console.print(traceback.format_exc())
        else:
            err_console.print("  Re-run with [bold]--verbose[/bold] for full traceback.")
        raise typer.Exit(1) from e

    if state.verbose:
        console.print(
            f"[dim]Parsed IR:[/dim] name={ir.name!r}, tools={len(ir.tools)}, "
            f"knowledge={len(ir.knowledge)}, triggers={len(ir.triggers)}"
        )
    return ir


@app.command()
def convert(
    source: Path = typer.Argument(help="Path to source agent directory"),
    from_platform: str = typer.Option(
        ..., "--from", help=f"Source platform: {', '.join(_PARSERS)}"
    ),
    to_platform: str = typer.Option(
        ...,
        "--to",
        help=f"Target platform: {', '.join(_EMITTERS)}, all",
    ),
    output: Path = typer.Option(
        Path("./agentshift-output"), "--output", "-o", help="Output directory"
    ),
) -> None:
    """Convert an agent from one platform to another. Use --to all for every supported target."""
    parse_fn = _get_parser(from_platform)

    # Resolve targets — "all" expands to every registered emitter
    if to_platform == "all":
        targets = list(_EMITTERS.keys())
    else:
        if to_platform not in _EMITTERS:
            err_console.print(f"[red]Unknown target platform:[/red] {to_platform!r}")
            suggestion = _did_you_mean(to_platform, [*list(_EMITTERS), "all"])
            if suggestion:
                err_console.print(f"  Did you mean [bold]{suggestion}[/bold]?")
            err_console.print(f"  Supported targets: {', '.join(_EMITTERS)}, all")
            raise typer.Exit(1)
        targets = [to_platform]

    ir = _parse_with_errors(parse_fn, source)

    target_label = "all targets" if to_platform == "all" else to_platform
    console.print(
        f"[bold]AgentShift[/bold] converting [cyan]{source}[/cyan] ({from_platform}) → [green]{target_label}[/green]"
    )

    # Emit to each target
    for target in targets:
        emit_fn = _load_emitter(target)
        target_dir = output / target if to_platform == "all" else output
        try:
            emit_fn(ir, target_dir)
        except Exception as e:
            err_console.print(f"  [red]✗[/red] [bold]{target}[/bold] failed: {e}")
            if state.verbose:
                err_console.print(traceback.format_exc())
            continue
        console.print(f"  [green]✓[/green] [bold]{target}[/bold] → [cyan]{target_dir}[/cyan]")

    if to_platform == "all":
        console.print(
            f"\n[green]✓[/green] Converted [bold]{ir.name}[/bold] to {len(targets)} targets → [cyan]{output}[/cyan]"
        )


@app.command()
def diff(
    source: Path = typer.Argument(help="Path to source agent directory"),
    from_platform: str = typer.Option("openclaw", "--from", help="Source platform"),
    targets: str = typer.Option("all", "--targets", help="Comma-separated targets or 'all'"),
    output_format: str = typer.Option(
        "text", "--output-format", help="Output format: text or json"
    ),
) -> None:
    """Show portability matrix — what converts cleanly vs. what needs manual work."""
    from agentshift.diff import PLATFORM_SUPPORT, compute_diff, render_diff_table

    parse_fn = _get_parser(from_platform)
    ir = _parse_with_errors(parse_fn, source)

    target_list = (
        list(PLATFORM_SUPPORT.keys())
        if targets == "all"
        else [t.strip() for t in targets.split(",")]
    )

    # Validate requested targets
    unknown = [t for t in target_list if t not in PLATFORM_SUPPORT]
    if unknown:
        for u in unknown:
            err_console.print(f"[red]Unknown diff target:[/red] {u!r}")
            suggestion = _did_you_mean(u, list(PLATFORM_SUPPORT))
            if suggestion:
                err_console.print(f"  Did you mean [bold]{suggestion}[/bold]?")
        err_console.print(f"  Supported: {', '.join(PLATFORM_SUPPORT)}")
        raise typer.Exit(1)

    if output_format == "json":
        from agentshift.diff import _component_display

        result = compute_diff(ir, target_list)
        scores = {t: int(s) for t, s in result["scores"].items()}
        components = []
        for comp in result["active"]:
            row: dict = {"name": _component_display(comp, ir), "source": True}
            for target in target_list:
                fidelity, _, _ = result["components"][comp][target]
                row[target] = fidelity
            components.append(row)
        payload = {
            "agent_name": ir.name,
            "source_platform": ir.metadata.source_platform or from_platform,
            "targets": target_list,
            "scores": scores,
            "components": components,
        }
        print(json.dumps(payload, indent=2))
    else:
        render_diff_table(ir, target_list)


@app.command(name="mcp-to-openapi")
def mcp_to_openapi(
    source: Path = typer.Argument(help="Path to source agent directory"),
    from_platform: str = typer.Option(
        "openclaw", "--from", help=f"Source platform: {', '.join(_PARSERS)}"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path (default: print to stdout)"
    ),
) -> None:
    """Generate OpenAPI 3.0 schema from MCP/shell tools in the source agent."""
    from agentshift.mcp_converter import mcp_to_openapi as _mcp_to_openapi

    parse_fn = _get_parser(from_platform)
    ir = _parse_with_errors(parse_fn, source)

    mcp_tools = [
        {
            "name": tool.name,
            "description": tool.description or tool.name,
            "inputSchema": tool.parameters or {"type": "object", "properties": {}},
        }
        for tool in ir.tools
        if tool.kind in ("mcp", "shell")
    ]

    if state.verbose:
        console.print(f"[dim]Converting {len(mcp_tools)} MCP/shell tools to OpenAPI schema[/dim]")

    schema = _mcp_to_openapi(mcp_tools, server_name=ir.name, title=f"{ir.name} Tools")
    output_json = json.dumps(schema, indent=2)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_json, encoding="utf-8")
        console.print(f"[green]✓[/green] OpenAPI schema → [cyan]{output}[/cyan]")
    else:
        console.print(output_json)


@app.command()
def validate(
    source: str = typer.Argument(help="Path to generated agent output directory"),
    target: str = typer.Option(
        ...,
        help=f"Target platform: {', '.join(['claude-code', 'copilot', 'bedrock', 'm365', 'vertex'])}",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON report"),
) -> None:
    """Validate a generated config against the target platform's schema."""
    from agentshift.validators import validate_output

    valid_targets = ["claude-code", "copilot", "bedrock", "m365", "vertex"]
    if target not in valid_targets:
        err_console.print(f"[red]Unknown validate target:[/red] {target!r}")
        suggestion = _did_you_mean(target, valid_targets)
        if suggestion:
            err_console.print(f"  Did you mean [bold]{suggestion}[/bold]?")
        err_console.print(f"  Supported: {', '.join(valid_targets)}")
        raise typer.Exit(1)

    source_path = Path(source)
    if not source_path.exists():
        err_console.print(f"[red]Error:[/red] Directory not found: [cyan]{source}[/cyan]")
        err_console.print(
            "  Run [bold]agentshift convert[/bold] first to generate output before validating."
        )
        raise typer.Exit(1)

    ok = validate_output(source_path, target, as_json=as_json)
    if not ok:
        raise typer.Exit(1)


@app.command()
def audit(
    source: Path = typer.Argument(help="Path to source agent directory"),
    from_platform: str = typer.Option("openclaw", "--from", help="Source platform"),
    targets: str = typer.Option(
        "claude-code,copilot", "--targets", help="Comma-separated target platforms"
    ),
    agent_id: str = typer.Option("", "--agent-id", help="Agent ID for the audit report"),
    domain: str = typer.Option("", "--domain", help="Agent domain (e.g., General, Finance)"),
    complexity: str = typer.Option("", "--complexity", help="Agent complexity (Low/Medium/High)"),
    output_csv: Path | None = typer.Option(None, "--csv", help="Export results to CSV"),
    output_json: Path | None = typer.Option(None, "--json", help="Export results to JSON"),
) -> None:
    """Run governance preservation audit on an agent conversion."""
    from agentshift.governance_audit import (
        audit_conversion,
        export_csv,
        export_json,
        render_audit_table,
        render_elevation_analysis,
    )

    parse_fn = _get_parser(from_platform)
    ir = _parse_with_errors(parse_fn, source)

    target_list = [t.strip() for t in targets.split(",")]
    audits = []
    for target in target_list:
        if target not in _EMITTERS and target not in {"bedrock", "vertex", "m365"}:
            err_console.print(f"[yellow]Skipping unknown target: {target}[/yellow]")
            continue
        a = audit_conversion(ir, target, agent_id or ir.name, domain, complexity)
        audits.append(a)

    render_audit_table(audits)
    render_elevation_analysis(audits)

    if output_csv:
        export_csv(audits, output_csv)
        console.print(f"[green]✓[/green] CSV exported → [cyan]{output_csv}[/cyan]")

    if output_json:
        export_json(audits, output_json)
        console.print(f"[green]✓[/green] JSON exported → [cyan]{output_json}[/cyan]")


@app.command(name="audit-batch")
def audit_batch_cmd(
    agents_dir: Path = typer.Argument(help="Directory containing agent subdirectories"),
    from_platform: str = typer.Option("openclaw", "--from", help="Source platform"),
    targets: str = typer.Option(
        "claude-code,copilot", "--targets", help="Comma-separated target platforms"
    ),
    output_csv: Path | None = typer.Option(None, "--csv", help="Export results to CSV"),
    output_json: Path | None = typer.Option(None, "--json", help="Export results to JSON"),
) -> None:
    """Run governance audit across all agents in a directory (batch mode for paper)."""
    from agentshift.governance_audit import (
        audit_batch,
        export_csv,
        export_json,
        render_audit_table,
        render_elevation_analysis,
        render_per_agent_breakdown,
        render_summary_by_target,
    )

    if not agents_dir.is_dir():
        err_console.print(f"[red]Error:[/red] Not a directory: {agents_dir}")
        raise typer.Exit(1)

    parse_fn = _get_parser(from_platform)
    target_list = [t.strip() for t in targets.split(",")]

    # Discover agents — each subdirectory with a SKILL.md
    agent_data = []
    for subdir in sorted(agents_dir.iterdir()):
        if not subdir.is_dir():
            continue
        skill_md = subdir / "SKILL.md"
        if not skill_md.exists():
            continue

        ir = _parse_with_errors(parse_fn, subdir)

        # Read metadata from agent_meta.json if present
        meta_file = subdir / "agent_meta.json"
        meta = {}
        if meta_file.exists():
            import contextlib
            import json as _json

            with contextlib.suppress(Exception):
                meta = _json.loads(meta_file.read_text(encoding="utf-8"))

        agent_id = meta.get("id", subdir.name)
        domain_val = meta.get("domain", "")
        complexity_val = meta.get("complexity", "")
        agent_data.append((ir, agent_id, domain_val, complexity_val))

    if not agent_data:
        err_console.print(f"[red]No agents found in {agents_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Found {len(agent_data)} agents[/bold]")

    audits = audit_batch(agent_data, target_list)

    render_audit_table(audits)
    render_summary_by_target(audits)
    render_per_agent_breakdown(audits)
    render_elevation_analysis(audits)

    if output_csv:
        export_csv(audits, output_csv)
        console.print(f"[green]✓[/green] CSV exported → [cyan]{output_csv}[/cyan]")

    if output_json:
        export_json(audits, output_json)
        console.print(f"[green]✓[/green] JSON exported → [cyan]{output_json}[/cyan]")


@app.command()
def compliance(
    source: Path = typer.Argument(help="Path to source agent directory"),
    from_platform: str = typer.Option("openclaw", "--from", help="Source platform"),
    framework: str = typer.Option(
        "eu-ai-act", "--framework", help="Compliance framework: eu-ai-act"
    ),
    output_format: str = typer.Option(
        "text", "--output-format", help="Output format: text or json"
    ),
) -> None:
    """Run compliance checks against a regulatory framework (e.g., EU AI Act)."""
    from agentshift.compliance import (
        compliance_score,
        render_compliance_report,
        run_compliance,
    )

    parse_fn = _get_parser(from_platform)
    ir = _parse_with_errors(parse_fn, source)

    try:
        checks = run_compliance(ir, framework)
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    if output_format == "json":
        score = compliance_score(checks)
        payload = {
            "agent": ir.name,
            "framework": framework,
            "score": score,
            "checks": [
                {
                    "article": c.article,
                    "requirement": c.requirement,
                    "status": c.status,
                    "evidence": c.evidence,
                    "recommendation": c.recommendation,
                }
                for c in checks
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        render_compliance_report(ir, framework, checks)


# ---------------------------------------------------------------------------
# Registry subcommand group
# ---------------------------------------------------------------------------

registry_app = typer.Typer(
    name="registry",
    help="Local agent registry — register, list, diff, and export agent snapshots.",
    no_args_is_help=True,
)
app.add_typer(registry_app, name="registry")


@registry_app.command(name="register")
def registry_register(
    source: Path = typer.Argument(help="Path to agent directory"),
    from_platform: str = typer.Option(
        "openclaw", "--from", help=f"Source platform: {', '.join(_PARSERS)}"
    ),
    name: str = typer.Option("", "--name", help="Override agent name"),
) -> None:
    """Register an agent in the local registry (snapshot for drift detection)."""
    from agentshift.registry import Registry

    parse_fn = _get_parser(from_platform)
    ir = _parse_with_errors(parse_fn, source)

    agent_name = name or ir.name
    registry = Registry()
    entry = registry.register(
        name=agent_name,
        source_path=str(source.resolve()),
        platform=from_platform,
        ir_dict=ir.model_dump(),
    )
    console.print(
        f"[green]✓[/green] Registered [bold]{agent_name}[/bold] "
        f"(hash: {entry.content_hash}) from [cyan]{source}[/cyan]"
    )


@registry_app.command(name="list")
def registry_list() -> None:
    """List all registered agents."""
    from agentshift.registry import Registry

    registry = Registry()
    agents = registry.list_agents()

    if not agents:
        console.print(
            "[dim]No agents registered. Use [bold]agentshift registry register[/bold] to add one.[/dim]"
        )
        return

    from rich.table import Table

    table = Table(title="Registered Agents")
    table.add_column("Name", style="bold")
    table.add_column("Platform")
    table.add_column("Source Path")
    table.add_column("Registered At")
    table.add_column("Hash", style="dim")

    for agent in agents:
        table.add_row(
            agent.name,
            agent.platform,
            agent.source_path,
            agent.registered_at[:19],
            agent.content_hash[:8],
        )

    console.print(table)


@registry_app.command(name="diff")
def registry_diff(
    name: str = typer.Argument(help="Registered agent name to compare"),
    source: Path = typer.Option(
        None, "--source", help="Path to current agent (default: use registered source_path)"
    ),
    from_platform: str = typer.Option(
        "", "--from", help="Source platform (default: use registered platform)"
    ),
) -> None:
    """Compare current agent state against registered snapshot (drift detection)."""
    from agentshift.registry import Registry

    registry = Registry()
    entry = registry.get(name)
    if entry is None:
        err_console.print(f"[red]Agent not found in registry:[/red] {name!r}")
        err_console.print("  Use [bold]agentshift registry list[/bold] to see registered agents.")
        raise typer.Exit(1)

    # Resolve source path
    agent_path = source or Path(entry.source_path)
    platform = from_platform or entry.platform

    parse_fn = _get_parser(platform)
    ir = _parse_with_errors(parse_fn, agent_path)

    report = registry.diff(name, ir.model_dump())

    if not report.has_drift:
        console.print(f"[green]✓[/green] [bold]{name}[/bold] — no drift detected")
        return

    console.print(f"[yellow]⚠[/yellow] [bold]{name}[/bold] — drift detected!")
    console.print()

    from rich.table import Table

    table = Table(title=f"Drift Report: {name}")
    table.add_column("Field", style="bold")
    table.add_column("Change")
    table.add_column("Old Value", style="red")
    table.add_column("New Value", style="green")

    for change in report.changes:
        old_str = _truncate(str(change.old_value), 60) if change.old_value is not None else ""
        new_str = _truncate(str(change.new_value), 60) if change.new_value is not None else ""
        table.add_row(change.field, change.kind, old_str, new_str)

    console.print(table)


@registry_app.command(name="export")
def registry_export(
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
) -> None:
    """Export the full registry as JSON."""
    from agentshift.registry import Registry

    registry = Registry()
    export_data = registry.export()

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(export_data + "\n", encoding="utf-8")
        console.print(f"[green]✓[/green] Registry exported → [cyan]{output}[/cyan]")
    else:
        console.print(export_data)


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string for display."""
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


if __name__ == "__main__":
    app()
