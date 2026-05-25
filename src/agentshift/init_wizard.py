"""agentshift init — interactive scaffold wizard for new agents."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import typer
from rich.console import Console

from agentshift.ir import (
    AgentIR,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
    ToolAuth,
    Trigger,
)

console = Console()

TARGET_FORMATS = [
    "openclaw",
    "claude-code",
    "copilot",
    "bedrock",
    "vertex",
    "crewai",
    "autogen",
    "openai-agents",
    "langgraph",
    "a2a",
]

_EMITTER_MAP = {
    "openclaw": None,  # No emitter — just writes IR JSON
    "claude-code": "agentshift.emitters.claude_code:emit",
    "copilot": "agentshift.emitters.copilot:emit",
    "bedrock": "agentshift.emitters.bedrock:emit",
    "vertex": "agentshift.emitters.vertex:emit",
    "crewai": "agentshift.emitters.crewai:emit",
    "autogen": "agentshift.emitters.autogen:emit",
    "openai-agents": "agentshift.emitters.openai_agents:emit",
    "langgraph": "agentshift.emitters.langgraph:emit",
    "a2a": "agentshift.emitters.a2a:emit",
}


def _build_ir(
    name: str,
    description: str,
    tools: list[str],
    has_cron: bool,
    has_knowledge: bool,
    auth_type: str,
) -> AgentIR:
    """Build an AgentIR object from wizard inputs."""
    tool_objs = [
        Tool(name=t.strip(), description=f"{t.strip()} tool", kind="function")
        for t in tools
        if t.strip()
    ]

    triggers = []
    if has_cron:
        triggers.append(Trigger(kind="cron", cron_expr="0 * * * *", id="default-cron"))

    knowledge = []
    if has_knowledge:
        knowledge.append(KnowledgeSource(name="docs", kind="directory", path="./knowledge/"))

    auth = None
    if auth_type and auth_type != "none":
        auth = ToolAuth(type=auth_type)
        for tool in tool_objs:
            tool.auth = auth

    return AgentIR(
        name=name,
        description=description,
        persona=Persona(system_prompt=f"You are {name}. {description}"),
        tools=tool_objs,
        triggers=triggers,
        knowledge=knowledge,
        metadata=Metadata(source_platform="openclaw"),
    )


def _resolve_emitter(target: str):
    """Dynamically load the emit function for a target format."""
    entry = _EMITTER_MAP.get(target)
    if entry is None:
        return None
    module_path, fn_name = entry.split(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


def init_agent(
    name: str,
    description: str,
    target: str,
    tools: list[str] | None = None,
    has_cron: bool = False,
    has_knowledge: bool = False,
    auth_type: str = "none",
    output_dir: Path | None = None,
) -> Path:
    """Build IR and emit scaffold files. Returns the output directory."""
    ir = _build_ir(
        name=name,
        description=description,
        tools=tools or [],
        has_cron=has_cron,
        has_knowledge=has_knowledge,
        auth_type=auth_type,
    )

    out = output_dir or Path(f"./output/{name}")
    out.mkdir(parents=True, exist_ok=True)

    emit_fn = _resolve_emitter(target)
    if emit_fn:
        emit_fn(ir, out)
    else:
        # Fallback: write IR as JSON
        ir_path = out / "agent-ir.json"
        ir_path.write_text(ir.model_dump_json(indent=2), encoding="utf-8")

    return out


def init_interactive() -> None:
    """Run the interactive init wizard via typer prompts."""
    name = typer.prompt("Agent name")
    description = typer.prompt("Description")
    target = typer.prompt(
        f"Target format ({', '.join(TARGET_FORMATS)})",
        default="claude-code",
    )
    if target not in TARGET_FORMATS:
        console.print(f"[red]Unknown format:[/red] {target}")
        console.print(f"  Choices: {', '.join(TARGET_FORMATS)}")
        raise typer.Exit(1)

    tools_input = typer.prompt("Tool names (comma-separated, or leave empty)", default="")
    tools = [t.strip() for t in tools_input.split(",") if t.strip()]

    has_cron = typer.confirm("Add cron trigger?", default=False)
    has_knowledge = typer.confirm("Add knowledge source?", default=False)

    auth_type = "none"
    if typer.confirm("Configure auth?", default=False):
        auth_type = typer.prompt("Auth type (api_key/oauth2/none)", default="api_key")

    out = init_agent(
        name=name,
        description=description,
        target=target,
        tools=tools,
        has_cron=has_cron,
        has_knowledge=has_knowledge,
        auth_type=auth_type,
    )

    console.print(f"\n[green]✓[/green] Agent [bold]{name}[/bold] scaffolded → [cyan]{out}[/cyan]")
    # List generated files
    for f in sorted(out.rglob("*")):
        if f.is_file():
            console.print(f"  [dim]{f.relative_to(out)}[/dim]")


def init_from_config(config_path: Path) -> None:
    """Non-interactive mode: read config from JSON file."""
    if not config_path.exists():
        console.print(f"[red]Config file not found:[/red] {config_path}")
        raise typer.Exit(1)

    data = json.loads(config_path.read_text(encoding="utf-8"))

    name = data.get("name")
    description = data.get("description", "")
    target = data.get("target", "claude-code")
    tools = data.get("tools", [])
    has_cron = data.get("cron", False)
    has_knowledge = data.get("knowledge", False)
    auth_type = data.get("auth_type", "none")
    output_dir = Path(data["output"]) if "output" in data else None

    if not name:
        console.print("[red]Config must include 'name' field[/red]")
        raise typer.Exit(1)

    if target not in TARGET_FORMATS:
        console.print(f"[red]Unknown format in config:[/red] {target}")
        raise typer.Exit(1)

    out = init_agent(
        name=name,
        description=description,
        target=target,
        tools=tools,
        has_cron=has_cron,
        has_knowledge=has_knowledge,
        auth_type=auth_type,
        output_dir=output_dir,
    )

    console.print(f"[green]✓[/green] Agent [bold]{name}[/bold] scaffolded → [cyan]{out}[/cyan]")
    for f in sorted(out.rglob("*")):
        if f.is_file():
            console.print(f"  [dim]{f.relative_to(out)}[/dim]")
