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
}

_EMITTERS = {
    "claude-code": "agentshift.emitters.claude_code:emit",
    "copilot": "agentshift.emitters.copilot:emit",
    "bedrock": "agentshift.emitters.bedrock:emit",
    "m365": "agentshift.emitters.m365:emit",
    "vertex": "agentshift.emitters.vertex:emit",
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
        if state.verbose:
            err_console.print(traceback.format_exc())
        raise typer.Exit(1) from e
    except ValueError as e:
        err_console.print(f"[red]Parse error:[/red] {e}")
        if state.verbose:
            err_console.print(traceback.format_exc())
        raise typer.Exit(1) from e
    except Exception as e:  # noqa: BLE001
        err_console.print(f"[red]Unexpected error while parsing:[/red] {e}")
        if state.verbose:
            err_console.print(traceback.format_exc())
        else:
            err_console.print("  Re-run with [bold]--verbose[/bold] for full traceback.")
        raise typer.Exit(1) from e

    if state.verbose:
        console.print(f"[dim]Parsed IR:[/dim] name={ir.name!r}, tools={len(ir.tools)}, "
                      f"knowledge={len(ir.knowledge)}, triggers={len(ir.triggers)}")
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
            suggestion = _did_you_mean(to_platform, list(_EMITTERS) + ["all"])
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
        except Exception as e:  # noqa: BLE001
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
) -> None:
    """Show portability matrix — what converts cleanly vs. what needs manual work."""
    from agentshift.diff import PLATFORM_SUPPORT, render_diff_table

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


if __name__ == "__main__":
    app()
