"""AgentShift CLI — convert AI agents between platforms."""

from __future__ import annotations

import importlib
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

_PARSERS = {
    "openclaw": "agentshift.parsers.openclaw:parse_skill_dir",
    "claude-code": "agentshift.parsers.claude_code:parse_agent_dir",
}

_EMITTERS = {
    "claude-code": "agentshift.emitters.claude_code:emit",
    "copilot": "agentshift.emitters.copilot:emit",
    "bedrock": "agentshift.emitters.bedrock:emit",
    "m365": "agentshift.emitters.m365:emit",
}


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
) -> None:
    pass


def _get_parser(platform: str):
    if platform not in _PARSERS:
        console.print(f"[red]Unknown source platform: {platform}[/red]")
        console.print(f"Supported: {', '.join(_PARSERS)}")
        raise typer.Exit(1)
    module_path, fn_name = _PARSERS[platform].split(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


def _load_emitter(platform: str):
    module_path, fn_name = _EMITTERS[platform].split(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


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
            console.print(f"[red]Unknown target platform: {to_platform}[/red]")
            console.print(f"Supported: {', '.join(_EMITTERS)}, all")
            raise typer.Exit(1)
        targets = [to_platform]

    # Parse once
    try:
        ir = parse_fn(source)
    except FileNotFoundError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise typer.Exit(1) from e

    target_label = "all targets" if to_platform == "all" else to_platform
    console.print(
        f"[bold]AgentShift[/bold] converting [cyan]{source}[/cyan] ({from_platform}) → [green]{target_label}[/green]"
    )

    # Emit to each target
    for target in targets:
        emit_fn = _load_emitter(target)
        target_dir = output / target if to_platform == "all" else output
        emit_fn(ir, target_dir)
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
    try:
        ir = parse_fn(source)
    except FileNotFoundError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise typer.Exit(1) from e

    target_list = (
        list(PLATFORM_SUPPORT.keys())
        if targets == "all"
        else [t.strip() for t in targets.split(",")]
    )
    render_diff_table(ir, target_list)


@app.command()
def validate(
    source: str = typer.Argument(help="Path to generated agent config"),
    target: str = typer.Option(..., help="Target platform to validate against"),
) -> None:
    """Validate a generated config against the target platform's schema."""
    console.print(f"Validating {source} for {target}")
    console.print("[yellow]Not yet implemented.[/yellow]")


if __name__ == "__main__":
    app()
