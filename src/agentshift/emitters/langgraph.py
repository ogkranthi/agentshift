"""LangGraph emitter — converts AgentShift IR into a LangGraph agent package.

Produces:
  agent.py          — StateGraph definition, nodes, edges, compiled graph export
  tools.py          — @tool-decorated functions translated from IR tools[]
  requirements.txt  — pinned Python dependencies
  langgraph.json    — LangGraph Platform deployment manifest
  .env.example      — required environment variables
  README.md         — setup and usage instructions
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from agentshift.ir import AgentIR, Tool, Trigger

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write a LangGraph agent package from an AgentIR."""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_agent_py(ir, output_dir)
    _write_tools_py(ir, output_dir)
    _write_requirements_txt(ir, output_dir)
    _write_langgraph_json(ir, output_dir)
    _write_env_example(ir, output_dir)
    _write_readme(ir, output_dir)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pkg_name(name: str) -> str:
    """Convert an agent name to a valid Python identifier (hyphens → underscores)."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    # Strip leading digits / underscores
    s = re.sub(r"^[^a-zA-Z]+", "", s) or "agent"
    return s.lower()


def _slug(name: str) -> str:
    """Lowercase hyphen-separated slug for file/dir names."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "agent"


def _fn_name(tool_name: str) -> str:
    """Convert a tool name to a valid Python function/class identifier."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", tool_name)
    s = re.sub(r"^[^a-zA-Z]+", "", s) or "tool"
    return s.lower()


def _class_name(tool_name: str) -> str:
    """PascalCase class name for Pydantic input schemas."""
    parts = re.split(r"[^a-zA-Z0-9]+", tool_name)
    return "".join(p.capitalize() for p in parts if p) + "Input"


def _collect_tool_env_vars(ir: AgentIR) -> list[str]:
    """Return env vars required by tool auth."""
    env_vars: list[str] = []
    for tool in ir.tools:
        if (
            tool.auth
            and tool.auth.type != "none"
            and tool.auth.env_var
            and tool.auth.env_var not in env_vars
        ):
            env_vars.append(tool.auth.env_var)
    return env_vars


def _uses_requests(ir: AgentIR) -> bool:
    """True if any tools need the requests library."""
    return any(t.kind in ("openapi", "url") for t in ir.tools)


def _uses_anthropic(ir: AgentIR) -> bool:
    """Prefer Anthropic unless platform_extensions say otherwise."""
    provider = ir.metadata.platform_extensions.get("langgraph", {}).get(
        "llm_provider", "anthropic"
    )
    return provider != "openai"


# ---------------------------------------------------------------------------
# agent.py
# ---------------------------------------------------------------------------


def _write_agent_py(ir: AgentIR, output_dir: Path) -> None:
    pkg = _pkg_name(ir.name)
    source = ir.metadata.source_platform or "unknown"
    created = ir.metadata.created_at or ""

    lines: list[str] = []

    # Module docstring
    lines.append('"""')
    lines.append(f"{ir.name} — LangGraph agent.")
    lines.append("")
    lines.append(f"Converted from {source} via AgentShift.")
    if created:
        lines.append(f"Source created: {created}")
    lines.append("")
    lines.append("Exports:")
    lines.append(
        "  graph  — compiled CompiledStateGraph ready for LangGraph Platform deployment"
    )
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from typing import Annotated, Literal")
    lines.append("")
    lines.append("from langchain_core.messages import AnyMessage, SystemMessage")

    if _uses_anthropic(ir):
        lines.append("from langchain_anthropic import ChatAnthropic")
    else:
        lines.append("from langchain_openai import ChatOpenAI")

    lines.append("from langgraph.checkpoint.memory import InMemorySaver")
    lines.append("from langgraph.graph import END, START, StateGraph")
    lines.append("from langgraph.graph.message import add_messages")
    lines.append("from langgraph.prebuilt import ToolNode, tools_condition")
    lines.append("from typing_extensions import TypedDict")
    lines.append("")
    lines.append(f"from {pkg}.tools import get_tools")
    lines.append("")

    # Knowledge references (always-load mode → note in module)
    always_load = [k for k in ir.knowledge if k.load_mode == "always"]
    if always_load:
        lines.append(
            "# ---------------------------------------------------------------------------"
        )
        lines.append(
            "# Knowledge sources (always-load) — inject into system prompt or preload"
        )
        lines.append(
            "# ---------------------------------------------------------------------------"
        )
        for ks in always_load:
            lines.append(f"# TODO: preload knowledge '{ks.name}' ({ks.kind})")
            if ks.path:
                lines.append(f"#   path: {ks.path}")
            if ks.description:
                lines.append(f"#   description: {ks.description}")
        lines.append("")

    # Trigger notes
    non_manual = [t for t in ir.triggers if t.kind != "manual"]
    if non_manual:
        lines.append(
            "# ---------------------------------------------------------------------------"
        )
        lines.append("# Triggers — LangGraph Platform handles scheduling externally")
        lines.append(
            "# ---------------------------------------------------------------------------"
        )
        for trig in non_manual:
            _trigger_comment(lines, trig)
        lines.append("")

    # State
    lines.append("")
    lines.append("class AgentState(TypedDict):")
    lines.append('    """Working state passed between graph nodes."""')
    lines.append("")
    lines.append("    messages: Annotated[list[AnyMessage], add_messages]")
    lines.append("")
    lines.append("")

    # System prompt
    system_prompt = ""
    if ir.persona.system_prompt:
        system_prompt = ir.persona.system_prompt.strip()
    elif ir.description:
        system_prompt = ir.description.strip()

    # Apply guardrails / topic restrictions from constraints
    suffix_parts: list[str] = []
    for g in ir.constraints.guardrails:
        suffix_parts.append(f"Guardrail: {g}")
    for topic in ir.constraints.topic_restrictions:
        suffix_parts.append(f"Do not discuss: {topic}")
    if suffix_parts:
        system_prompt = (
            system_prompt + "\n\n" + "\n".join(suffix_parts)
            if system_prompt
            else "\n".join(suffix_parts)
        )

    # Truncate if max_instruction_chars is set
    max_chars = ir.constraints.max_instruction_chars
    if max_chars and len(system_prompt) > max_chars:
        system_prompt = system_prompt[:max_chars]

    escaped_prompt = system_prompt.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')

    lines.append('_SYSTEM_PROMPT = """')
    if system_prompt:
        lines.append(escaped_prompt)
    lines.append('""".strip()')
    lines.append("")
    lines.append("")

    # LLM instantiation
    if _uses_anthropic(ir):
        model_id = ir.metadata.platform_extensions.get("langgraph", {}).get(
            "model", "claude-sonnet-4-5"
        )
        lines.append(f'_llm = ChatAnthropic(model="{model_id}", temperature=0)')
    else:
        model_id = ir.metadata.platform_extensions.get("langgraph", {}).get(
            "model", "gpt-4o"
        )
        lines.append(f'_llm = ChatOpenAI(model="{model_id}", temperature=0)')

    lines.append("")
    lines.append("")

    # call_llm node
    lines.append("def _call_llm(state: AgentState) -> dict:")
    lines.append(
        '    """Invoke the LLM with tools bound and system prompt prepended."""'
    )
    lines.append("    tools = get_tools()")
    lines.append("    llm_with_tools = _llm.bind_tools(tools)")
    lines.append('    messages = state["messages"]')
    lines.append("    if _SYSTEM_PROMPT:")
    lines.append(
        "        messages = [SystemMessage(content=_SYSTEM_PROMPT)] + list(messages)"
    )
    lines.append("    response = llm_with_tools.invoke(messages)")
    lines.append('    return {"messages": [response]}')
    lines.append("")
    lines.append("")

    # Routing function
    lines.append(
        'def _should_continue(state: AgentState) -> Literal["tools", "__end__"]:'
    )
    lines.append('    """Route to tools if the LLM made a tool call, otherwise end."""')
    lines.append('    last_msg = state["messages"][-1]')
    lines.append('    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:')
    lines.append('        return "tools"')
    lines.append('    return "__end__"')
    lines.append("")
    lines.append("")

    # build_graph
    lines.append("def build_graph() -> StateGraph:")
    lines.append(f'    """Build and return the {ir.name} StateGraph (uncompiled)."""')
    lines.append("    tools = get_tools()")
    lines.append("    tool_node = ToolNode(tools)")
    lines.append("")
    lines.append("    builder = StateGraph(AgentState)")
    lines.append('    builder.add_node("llm_call", _call_llm)')
    lines.append('    builder.add_node("tools", tool_node)')
    lines.append('    builder.add_edge(START, "llm_call")')
    lines.append("    builder.add_conditional_edges(")
    lines.append('        "llm_call",')
    lines.append("        _should_continue,")
    lines.append('        ["tools", END],')
    lines.append("    )")
    lines.append('    builder.add_edge("tools", "llm_call")')
    lines.append("    return builder")
    lines.append("")
    lines.append("")

    # Exported graph
    lines.append("# Compiled graph — exported for LangGraph Platform deployment")
    lines.append("graph = build_graph().compile(checkpointer=InMemorySaver())")

    (output_dir / "agent.py").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _trigger_comment(lines: list[str], trig: Trigger) -> None:
    if trig.kind == "cron":
        expr = trig.cron_expr or trig.every or "?"
        lines.append(f"# Trigger [{trig.id or 'unnamed'}]: cron — schedule: {expr}")
        lines.append(
            "#   Use APScheduler, `schedule` lib, or LangSmith Deployment cron jobs."
        )
        lines.append("#   Example:")
        lines.append("#     import schedule")
        lines.append(
            f"#     schedule.every().day.do(lambda: graph.invoke(...))  # {expr}"
        )
    elif trig.kind == "webhook":
        path = trig.webhook_path or "/webhook"
        lines.append(f"# Trigger [{trig.id or 'unnamed'}]: webhook — path: {path}")
        lines.append("#   Expose a FastAPI endpoint that calls graph.invoke().")
    elif trig.kind == "message":
        msg = trig.message or "(any message)"
        lines.append(f"# Trigger [{trig.id or 'unnamed'}]: message — pattern: {msg}")
        lines.append(
            "#   Connect via messaging platform webhook → FastAPI → graph.invoke()."
        )
    elif trig.kind == "event":
        lines.append(
            f"# Trigger [{trig.id or 'unnamed'}]: event — name: {trig.event_name or '?'}"
        )
        lines.append("#   Subscribe your event bus consumer to call graph.invoke().")


# ---------------------------------------------------------------------------
# tools.py
# ---------------------------------------------------------------------------


def _write_tools_py(ir: AgentIR, output_dir: Path) -> None:
    lines: list[str] = []

    lines.append(f'"""Tool definitions for the {ir.name} agent."""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import os")

    needs_requests = _uses_requests(ir) or any(t.kind == "openapi" for t in ir.tools)
    needs_subprocess = any(t.kind == "shell" for t in ir.tools)

    if needs_requests:
        lines.append("import requests")
    if needs_subprocess:
        lines.append("import subprocess")

    # Check if we need pydantic for structured args
    has_params = any(
        t.parameters and isinstance(t.parameters.get("properties"), dict)
        for t in ir.tools
        if t.kind not in ("builtin",)
    )

    if has_params:
        lines.append("")
        lines.append("from pydantic import BaseModel, Field")

    lines.append("")
    lines.append("from langchain_core.tools import tool")
    lines.append("")

    tool_fn_names: list[str] = []

    # Emit tool functions
    for t in ir.tools:
        if t.kind == "builtin":
            lines.append(
                f"# NOTE: Skipping builtin tool '{t.name}' — no LangGraph equivalent."
            )
            lines.append("")
            continue

        fn = _fn_name(t.name)
        tool_fn_names.append(fn)

        # Pydantic input schema if parameters provided
        props = (t.parameters or {}).get("properties", {}) if t.parameters else {}
        required_params: list[str] = (
            (t.parameters or {}).get("required", []) if t.parameters else []
        )

        if props:
            cls = _class_name(t.name)
            lines.append(f"class {cls}(BaseModel):")
            for param_name, param_info in props.items():
                p_desc = (
                    param_info.get("description", param_name)
                    if isinstance(param_info, dict)
                    else param_name
                )
                p_type = _json_type_to_py(
                    param_info.get("type", "string")
                    if isinstance(param_info, dict)
                    else "string"
                )
                p_default = "" if param_name in required_params else " = None"
                lines.append(
                    f'    {param_name}: {p_type}{p_default} = Field(description="{p_desc}")'
                )
            lines.append("")
            lines.append("")
            lines.append(f"@tool(args_schema={cls})")
        else:
            lines.append("@tool")

        # Build function signature
        sig_parts: list[str] = []
        for param_name, param_info in props.items():
            p_type = _json_type_to_py(
                param_info.get("type", "string")
                if isinstance(param_info, dict)
                else "string"
            )
            if param_name not in required_params:
                sig_parts.append(f"{param_name}: {p_type} | None = None")
            else:
                sig_parts.append(f"{param_name}: {p_type}")

        if not sig_parts:
            # Generic string input for tools with no declared parameters
            sig_parts = ["input: str"]

        sig = ", ".join(sig_parts)
        lines.append(f"def {fn}({sig}) -> str:")

        # Docstring
        desc = t.description or f"Call the {t.name} tool."
        lines.append(f'    """{desc}"""')

        # Body
        if t.kind == "function":
            lines.append("    # TODO: implement")
            lines.append("    raise NotImplementedError")

        elif t.kind == "shell":
            lines.append(
                f"    # WARNING: shell tool '{t.name}' — only valid in local dev environments."
            )
            cmd_parts = sig_parts[0].split(":")[0].strip() if sig_parts else "input"
            lines.append(
                f"    result = subprocess.run([{cmd_parts}], capture_output=True, text=True, check=False)"
            )
            lines.append('    return result.stdout or result.stderr or ""')

        elif t.kind == "openapi":
            endpoint = t.endpoint or "https://example.com/api"
            auth_lines = _auth_snippet(t)
            lines.extend(auth_lines)
            lines.append(f'    url = "{endpoint}"')
            lines.append(
                "    params = {k: v for k, v in locals().items() if v is not None and k != 'input'}"
            )
            lines.append("    resp = requests.get(url, params=params)")
            lines.append("    resp.raise_for_status()")
            lines.append("    return resp.text")

        elif t.kind == "mcp":
            endpoint = t.endpoint or ""
            lines.append(
                f"    # MCP tool — connect to server: {endpoint or '(endpoint not specified)'}"
            )
            lines.append(
                "    # Use langchain-mcp-adapters to load tools from an MCP server."
            )
            lines.append(
                "    # See: https://github.com/langchain-ai/langchain-mcp-adapters"
            )
            lines.append("    # TODO: implement MCP invocation")
            lines.append("    raise NotImplementedError")

        else:  # unknown
            lines.append(f"    # TODO: implement '{t.name}' ({t.kind})")
            lines.append("    raise NotImplementedError")

        lines.append("")
        lines.append("")

    # Knowledge on-demand tools
    for ks in ir.knowledge:
        if ks.load_mode not in ("on_demand", "indexed"):
            continue
        fn = _fn_name(f"retrieve_{ks.name}")
        tool_fn_names.append(fn)
        lines.append("@tool")
        lines.append(f"def {fn}(query: str) -> str:")
        desc = ks.description or f"Retrieve content from {ks.name}."
        lines.append(f'    """{desc}"""')
        lines.append(f"    # Knowledge source: {ks.name} ({ks.kind})")
        if ks.path:
            lines.append(f"    # path: {ks.path}")
        if ks.kind in ("file", "directory"):
            if ks.path:
                lines.append(f'    with open("{ks.path}", "r", encoding="utf-8") as f:')
                lines.append("        return f.read()")
            else:
                lines.append("    # TODO: specify path for this knowledge source")
                lines.append("    raise NotImplementedError")
        elif ks.kind == "url":
            if ks.path:
                lines.append("    import urllib.request")
                lines.append(f'    with urllib.request.urlopen("{ks.path}") as resp:')
                lines.append("        return resp.read().decode()")
            else:
                lines.append("    # TODO: specify URL for this knowledge source")
                lines.append("    raise NotImplementedError")
        elif ks.kind == "vector_store":
            lines.append(
                f"    # TODO: connect to vector store at {ks.path or '(path not set)'}"
            )
            lines.append("    raise NotImplementedError")
        elif ks.kind == "database":
            lines.append(
                f"    # TODO: connect to database at {ks.path or '(path not set)'}"
            )
            lines.append("    raise NotImplementedError")
        elif ks.kind == "s3":
            lines.append("    # TODO: implement S3 retrieval")
            lines.append("    raise NotImplementedError")
        else:
            lines.append("    # TODO: implement retrieval")
            lines.append("    raise NotImplementedError")
        lines.append("")
        lines.append("")

    # get_tools() factory
    lines.append("")
    lines.append("def get_tools() -> list:")
    lines.append(f'    """Return all tools for the {ir.name} agent."""')
    if tool_fn_names:
        items = ", ".join(tool_fn_names)
        lines.append(f"    return [{items}]")
    else:
        lines.append("    return []")
    lines.append("")

    (output_dir / "tools.py").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _json_type_to_py(json_type: str) -> str:
    mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
    }
    return mapping.get(json_type, "str")


def _auth_snippet(tool: Tool) -> list[str]:
    """Return lines to inject auth into a tool function body."""
    if not tool.auth or tool.auth.type == "none":
        return []
    auth = tool.auth
    if auth.type == "api_key":
        env = auth.env_var or f"{tool.name.upper().replace('-', '_')}_API_KEY"
        return [
            f'    api_key = os.environ["{env}"]',
            '    headers = {"X-API-Key": api_key}',
        ]
    if auth.type == "bearer":
        env = auth.env_var or f"{tool.name.upper().replace('-', '_')}_TOKEN"
        return [
            f'    token = os.environ["{env}"]',
            '    headers = {"Authorization": f"Bearer {token}"}',
        ]
    if auth.type == "basic":
        env = auth.env_var or f"{tool.name.upper().replace('-', '_')}_CREDENTIALS"
        return [
            f'    credentials = os.environ["{env}"]  # format: user:password',
            '    auth = tuple(credentials.split(":", 1))',
        ]
    if auth.type == "oauth2":
        return ["    # TODO: OAuth2 setup — acquire token before calling endpoint"]
    if auth.type == "config_key":
        ckey = auth.config_key or "?"
        return [f"    # TODO: Map from OpenClaw config key '{ckey}'"]
    return []


# ---------------------------------------------------------------------------
# requirements.txt
# ---------------------------------------------------------------------------


def _write_requirements_txt(ir: AgentIR, output_dir: Path) -> None:
    lines: list[str] = [
        "# Generated by AgentShift — LangGraph emitter",
        f"# Agent: {ir.name} v{ir.version}",
        "",
        "langgraph>=0.2.0",
        "langchain>=0.3.0",
        "langchain-core>=0.3.0",
    ]

    if _uses_anthropic(ir):
        lines.append("langchain-anthropic>=0.3.0")
    else:
        lines.append("langchain-openai>=0.2.0")

    lines.append("python-dotenv>=1.0.0")

    if _uses_requests(ir):
        lines.append("requests>=2.31.0")

    # MCP tools
    if any(t.kind == "mcp" for t in ir.tools):
        lines.append("langchain-mcp-adapters>=0.1.0")

    lines.append("")

    (output_dir / "requirements.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# langgraph.json
# ---------------------------------------------------------------------------


def _write_langgraph_json(ir: AgentIR, output_dir: Path) -> None:
    pkg = _pkg_name(ir.name)
    graph_id = _slug(ir.name)

    manifest: dict = {
        "python_version": "3.11",
        "dependencies": ["."],
        "graphs": {
            graph_id: f"./{pkg}/agent.py:graph",
        },
        "env": ".env",
    }

    # Allow overrides via platform_extensions
    ext = ir.metadata.platform_extensions.get("langgraph", {})
    if "base_image" in ext:
        manifest["base_image"] = ext["base_image"]

    (output_dir / "langgraph.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# .env.example
# ---------------------------------------------------------------------------


def _write_env_example(ir: AgentIR, output_dir: Path) -> None:
    lines: list[str] = [
        "# .env.example — copy to .env and fill in your values",
        f"# Agent: {ir.name}",
        "",
    ]

    if _uses_anthropic(ir):
        lines += [
            "# Anthropic LLM",
            "ANTHROPIC_API_KEY=your-anthropic-api-key-here",
            "",
        ]
    else:
        lines += [
            "# OpenAI LLM",
            "OPENAI_API_KEY=your-openai-api-key-here",
            "",
        ]

    # Tool env vars
    tool_env_vars = _collect_tool_env_vars(ir)
    if tool_env_vars:
        lines.append("# Tool API keys")
        for ev in tool_env_vars:
            lines.append(f"{ev}=your-value-here")
        lines.append("")

    lines += [
        "# LangSmith observability (optional but recommended)",
        "LANGSMITH_TRACING=true",
        "LANGSMITH_API_KEY=your-langsmith-api-key-here",
        f"LANGSMITH_PROJECT={_slug(ir.name)}",
        "",
    ]

    (output_dir / ".env.example").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# README.md
# ---------------------------------------------------------------------------


def _write_readme(ir: AgentIR, output_dir: Path) -> None:
    pkg = _pkg_name(ir.name)
    emoji = ir.metadata.emoji or "🤖"
    source = ir.metadata.source_platform or "unknown"

    lines: list[str] = []

    # Title
    lines.append(f"# {emoji} {ir.name} — LangGraph Agent")
    lines.append("")
    lines.append(f"> {ir.description}")
    lines.append("")
    lines.append(
        f"> Generated by [AgentShift](https://github.com/agentshift/agentshift) from {source}."
    )
    lines.append("")

    # Tags
    if ir.metadata.tags:
        tags_str = " ".join(f"`{t}`" for t in ir.metadata.tags)
        lines.append(f"**Tags:** {tags_str}")
        lines.append("")

    # Generated files
    lines += [
        "## Generated Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        "| `agent.py` | LangGraph StateGraph definition; exports `graph` for deployment |",
        "| `tools.py` | `@tool`-decorated functions + `get_tools()` factory |",
        "| `requirements.txt` | Python dependencies |",
        "| `langgraph.json` | LangGraph Platform deployment manifest |",
        "| `.env.example` | Required environment variables (copy to `.env`) |",
        "| `README.md` | This file |",
        "",
    ]

    # Setup
    lines += [
        "## Setup",
        "",
        "### 1. Install dependencies",
        "",
        "```bash",
        "pip install -r requirements.txt",
        "```",
        "",
        "### 2. Configure environment",
        "",
        "```bash",
        "cp .env.example .env",
        "# Edit .env and fill in your API keys",
        "```",
        "",
    ]

    # Required env vars
    env_vars: list[str] = []
    if _uses_anthropic(ir):
        env_vars.append("`ANTHROPIC_API_KEY` — Anthropic API key")
    else:
        env_vars.append("`OPENAI_API_KEY` — OpenAI API key")
    for ev in _collect_tool_env_vars(ir):
        env_vars.append(f"`{ev}` — required by tool auth")

    if env_vars:
        lines.append("### Required environment variables")
        lines.append("")
        for ev in env_vars:
            lines.append(f"- {ev}")
        lines.append("")

    # Usage
    lines += [
        "## Usage",
        "",
        "### Run locally (interactive)",
        "",
        "```bash",
        "pip install langgraph-cli",
        "langgraph dev",
        "```",
        "",
        "### Python API",
        "",
        "```python",
        "from langchain_core.messages import HumanMessage",
        f"from {pkg}.agent import graph",
        "",
        'config = {"configurable": {"thread_id": "session-1"}}',
        "result = graph.invoke(",
        '    {"messages": [HumanMessage(content="Hello!")]},',
        "    config,",
        ")",
        'print(result["messages"][-1].content)',
        "```",
        "",
        "### Deploy to LangSmith",
        "",
        "```bash",
        "pip install langgraph-cli",
        "langgraph deploy",
        "```",
        "",
    ]

    # Triggers
    non_manual = [t for t in ir.triggers if t.kind != "manual"]
    if non_manual:
        lines += [
            "## Triggers",
            "",
            "This agent defines the following triggers. LangGraph does not handle",
            "scheduling natively — configure them externally:",
            "",
        ]
        for trig in non_manual:
            _trigger_readme_item(lines, trig)
        lines.append("")

    # Channels
    channels_from_triggers = [
        t.delivery.channel for t in ir.triggers if t.delivery and t.delivery.channel
    ]
    if channels_from_triggers:
        lines += [
            "## Channel Integration",
            "",
            "The following channels are referenced by triggers:",
            "",
        ]
        for ch in set(channels_from_triggers):
            lines.append(
                f"- **{ch}** — TODO: connect channel to `graph.invoke()` endpoint"
            )
        lines.append("")

    # Knowledge
    if ir.knowledge:
        lines += [
            "## Knowledge Sources",
            "",
            "| Name | Kind | Load Mode | Path/URL |",
            "|------|------|-----------|----------|",
        ]
        for ks in ir.knowledge:
            path = ks.path or "—"
            lines.append(f"| `{ks.name}` | {ks.kind} | {ks.load_mode} | `{path}` |")
        lines.append("")

    # Alternative: create_react_agent
    lines += [
        "## Quickstart Alternative",
        "",
        "For a simpler setup, use LangGraph's prebuilt `create_react_agent`:",
        "",
        "```python",
        "from langgraph.prebuilt import create_react_agent",
        "from langgraph.checkpoint.memory import InMemorySaver",
    ]
    if _uses_anthropic(ir):
        lines.append("from langchain_anthropic import ChatAnthropic")
        lines.append('llm = ChatAnthropic(model="claude-sonnet-4-5")')
    else:
        lines.append("from langchain_openai import ChatOpenAI")
        lines.append('llm = ChatOpenAI(model="gpt-4o")')
    lines += [
        f"from {pkg}.tools import get_tools",
        "",
        "graph = create_react_agent(",
        "    model=llm,",
        "    tools=get_tools(),",
        "    checkpointer=InMemorySaver(),",
        ")",
        "```",
        "",
    ]

    # About
    lines += [
        "## About",
        "",
        "This agent was automatically generated by **AgentShift**.",
        "",
        f"- **Source format:** {source}",
        "- **Target format:** LangGraph (StateGraph)",
        "- **Converter:** [AgentShift](https://github.com/agentshift/agentshift)",
        "",
        "To convert other agents:",
        "```bash",
        f"agentshift convert <skill-dir> --from {source} --to langgraph --output ./output",
        "```",
    ]

    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _trigger_readme_item(lines: list[str], trig: Trigger) -> None:
    tid = trig.id or "unnamed"
    if trig.kind == "cron":
        expr = trig.cron_expr or trig.every or "?"
        lines.append(f"- **cron** (`{tid}`): `{expr}`")
        lines.append("  Use APScheduler or LangSmith Deployment cron jobs.")
    elif trig.kind == "webhook":
        path = trig.webhook_path or "/webhook"
        lines.append(f"- **webhook** (`{tid}`): path `{path}`")
        lines.append("  Expose a FastAPI route that calls `graph.invoke()`.")
    elif trig.kind == "message":
        msg = trig.message or "(any message)"
        lines.append(f"- **message** (`{tid}`): `{msg}`")
        lines.append("  Connect a messaging platform webhook to `graph.invoke()`.")
    elif trig.kind == "event":
        lines.append(f"- **event** (`{tid}`): `{trig.event_name or '?'}`")
        lines.append("  Subscribe your event bus consumer to call `graph.invoke()`.")
