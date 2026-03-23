"""AgentShift CLI — convert AI agents between platforms."""

import typer

app = typer.Typer(
    name="agentshift",
    help="Convert AI agents between platforms. OpenClaw → Copilot, Bedrock, Vertex AI, Claude Code.",
    no_args_is_help=True,
)


@app.command()
def convert(
    source: str = typer.Argument(help="Path to source agent (e.g., ./my-skill/)"),
    to: str = typer.Option(help="Target platform: claude-code, copilot, bedrock, vertex, all"),
    output: str = typer.Option(None, "--output", "-o", help="Output directory (default: ./agentshift-output/)"),
) -> None:
    """Convert an agent from one platform to another."""
    typer.echo(f"Converting {source} → {to}")
    typer.echo("Not yet implemented — agents are building this!")


@app.command()
def diff(
    source: str = typer.Argument(help="Path to source agent"),
    targets: str = typer.Option("all", help="Comma-separated targets: claude-code,copilot,bedrock,vertex"),
) -> None:
    """Show portability matrix — what converts cleanly vs. needs manual work."""
    typer.echo(f"Diffing {source} against {targets}")
    typer.echo("Not yet implemented — agents are building this!")


@app.command()
def validate(
    source: str = typer.Argument(help="Path to generated agent config"),
    target: str = typer.Option(help="Target platform to validate against"),
) -> None:
    """Validate a generated config against the target platform's schema."""
    typer.echo(f"Validating {source} for {target}")
    typer.echo("Not yet implemented — agents are building this!")


if __name__ == "__main__":
    app()
