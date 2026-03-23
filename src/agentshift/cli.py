"""AgentShift CLI — convert AI agents between platforms."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="agentshift",
    help="Convert AI agents between platforms. OpenClaw → Claude Code and more.",
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
}


def _get_parser(platform: str):
    if platform not in _PARSERS:
        console.print(f"[red]Unknown source platform: {platform}[/red]")
        console.print(f"Supported: {', '.join(_PARSERS)}")
        raise typer.Exit(1)
    module_path, fn_name = _PARSERS[platform].split(":")
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


def _get_emitter(platform: str):
    if platform not in _EMITTERS:
        console.print(f"[red]Unknown target platform: {platform}[/red]")
        console.print(f"Supported: {', '.join(_EMITTERS)}")
        raise typer.Exit(1)
    module_path, fn_name = _EMITTERS[platform].split(":")
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


@app.command()
def convert(
    source: Path = typer.Argument(help="Path to source agent directory"),
    from_platform: str = typer.Option(..., "--from", help="Source platform: openclaw, claude-code"),
    to_platform: str = typer.Option(..., "--to", help="Target platform: claude-code"),
    output: Path = typer.Option(
        Path("./agentshift-output"), "--output", "-o", help="Output directory"
    ),
) -> None:
    """Convert an agent from one platform to another."""
    parse_fn = _get_parser(from_platform)
    emit_fn = _get_emitter(to_platform)

    console.print(
        f"[bold]AgentShift[/bold] converting [cyan]{source}[/cyan] ({from_platform}) → [green]{to_platform}[/green]"
    )

    try:
        ir = parse_fn(source)
    except FileNotFoundError as e:
        console.print(f"[red]Parse error:[/red] {e}")
        raise typer.Exit(1) from e

    emit_fn(ir, output)

    console.print(f"[green]✓[/green] Converted [bold]{ir.name}[/bold] → [cyan]{output}[/cyan]")


@app.command()
def diff(
    source: str = typer.Argument(help="Path to source agent"),
    targets: str = typer.Option(
        "all", help="Comma-separated targets: claude-code,copilot,bedrock,vertex"
    ),
) -> None:
    """Show portability matrix — what converts cleanly vs. needs manual work."""
    console.print(f"Diffing {source} against {targets}")
    console.print("[yellow]Not yet implemented.[/yellow]")


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
