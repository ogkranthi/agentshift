"""Vertex AI Agent Builder → IR parser.

Reads Vertex AI agent artifacts from a directory and produces an AgentIR.

Supported input files:
  agent.json   — Agent resource definition (required)
  tools.json   — Tool definitions array (optional, richer schemas)
  README.md    — Deployment docs (optional, stub detection hints)

Input resolution order:
  1. agent.json is always required.
  2. tools.json entries take precedence over inline agent.json["tools"] for deduplication.
  3. README.md — scanned for stub tool names to enrich kind inference.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agentshift.ir import (
    AgentIR,
    Governance,
    Guardrail,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
    ToolAuth,
)
from agentshift.parsers.utils import (
    extract_guardrails_from_text,
    slugify,
)
from agentshift.sections import extract_sections

# ---------------------------------------------------------------------------
# Section prefix → canonical section key mapping (per spec §4)
# ---------------------------------------------------------------------------

_SECTION_PREFIX_MAP: dict[str, str] = {
    "behavior": "behavior",
    "persona": "persona",
    "tools": "tools",
    "knowledge": "knowledge",
    "restrictions": "guardrails",
    "guardrails": "guardrails",
    "overview": "overview",
}

_SECTION_PATTERN = re.compile(
    r"^([A-Z][a-zA-Z\s-]+):\n(.+)",
    re.MULTILINE | re.DOTALL,
)

# Pattern to detect "SectionName:\ncontent" in a single instruction string
_INLINE_SECTION_PATTERN = re.compile(
    r"^([A-Z][a-zA-Z\s-]+):\s*\n?(.*)",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def parse(input_dir: Path) -> AgentIR:
    """Parse Vertex AI Agent Builder artifacts from a directory into an AgentIR.

    Reads any combination of:
      - agent.json   (required)
      - tools.json   (optional — additional tool definitions)
      - README.md    (optional — stub detection hints)

    Raises:
        FileNotFoundError: if input_dir or agent.json does not exist.
        ValueError: if agent.json cannot be parsed.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Vertex AI input directory not found: {input_dir}")
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Expected a directory, got: {input_dir}")

    agent_path = input_dir / "agent.json"
    if not agent_path.exists():
        raise FileNotFoundError(
            f"No agent.json found in {input_dir}. "
            "A Vertex AI agent directory must contain an agent.json file."
        )

    try:
        agent_data = json.loads(agent_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {agent_path}: {e}") from e

    # Load optional files
    tools_data: list[dict] | None = None
    tools_path = input_dir / "tools.json"
    if tools_path.exists():
        try:
            raw = json.loads(tools_path.read_text(encoding="utf-8"))
            tools_data = raw if isinstance(raw, list) else None
        except (json.JSONDecodeError, OSError):
            tools_data = None

    readme_text: str | None = None
    readme_path = input_dir / "README.md"
    if readme_path.exists():
        try:
            readme_text = readme_path.read_text(encoding="utf-8")
        except OSError:
            readme_text = None

    return parse_api_response(agent_data, tools_data, readme_text=readme_text)


def parse_api_response(
    agent_data: dict,
    tools_data: list[dict] | None = None,
    *,
    readme_text: str | None = None,
) -> AgentIR:
    """Parse raw Vertex AI API response dicts into an AgentIR."""
    # Core identity
    display_name = agent_data.get("displayName", "")
    name = slugify(display_name) if display_name else "unnamed-vertex-agent"

    # Resource name (full path) — from API response
    resource_name = agent_data.get("name", "")

    # Description
    description = agent_data.get("description", "")

    # Timestamps
    created_at = agent_data.get("createTime")
    updated_at = agent_data.get("updateTime")

    # Language
    language = agent_data.get("defaultLanguageCode", "en")

    # Goal + instructions → system_prompt
    goal = agent_data.get("goal", "")
    instructions = agent_data.get("instructions", [])

    system_prompt, sections = _reconstruct_system_prompt(goal, instructions)

    # Derive description from goal if absent
    if not description and goal:
        first_sentence = re.split(r"[.!?\n]", goal)[0].strip()
        description = first_sentence[:200]

    persona = Persona(
        system_prompt=system_prompt or None,
        sections=sections if sections else None,
        language=language,
    )

    # Tools — merge agent.json["tools"] with tools.json (tools.json wins on dedup)
    inline_tools = agent_data.get("tools", [])
    tools, knowledge = _extract_tools(inline_tools, tools_data, readme_text=readme_text)

    # Guardrails — heuristic scan of instructions
    guardrails: list[Guardrail] = []
    # Scan all instruction strings
    for instr in instructions:
        if isinstance(instr, str):
            guardrails.extend(
                extract_guardrails_from_text(
                    instr,
                    id_prefix="G",
                    start_index=len(guardrails) + 1,
                )
            )
    # Also check the "Restrictions:" section if found
    if sections and "guardrails" in sections:
        extra = extract_guardrails_from_text(
            sections["guardrails"],
            id_prefix="G",
            start_index=len(guardrails) + 1,
        )
        existing_texts = {g.text.lower() for g in guardrails}
        for g in extra:
            if g.text.lower() not in existing_texts:
                guardrails.append(g)

    governance = Governance(guardrails=guardrails)

    # Metadata
    bedrock_ext: dict[str, Any] = {
        "display_name": display_name,
    }
    if resource_name:
        bedrock_ext["resource_name"] = resource_name

    # Model override
    model_override = agent_data.get("platform_extensions", {}).get("vertex_ai", {}).get(
        "model"
    ) or agent_data.get("platform_extensions", {}).get("vertex", {}).get("model")
    if model_override:
        bedrock_ext["model"] = model_override

    metadata = Metadata(
        source_platform="vertex-ai",
        created_at=created_at,
        updated_at=updated_at,
        platform_extensions={"vertex": bedrock_ext},
    )

    return AgentIR(
        name=name,
        description=description or f"Vertex AI agent: {display_name}",
        persona=persona,
        tools=tools,
        knowledge=knowledge,
        governance=governance,
        metadata=metadata,
    )


def parse_agent_json(
    agent_json: str,
    tools_json: str | None = None,
) -> AgentIR:
    """Parse from JSON strings directly."""
    agent_data = json.loads(agent_json)
    tools_data = json.loads(tools_json) if tools_json else None
    if tools_data is not None and not isinstance(tools_data, list):
        tools_data = None
    return parse_api_response(agent_data, tools_data)


# ---------------------------------------------------------------------------
# System prompt reconstruction
# ---------------------------------------------------------------------------


def _reconstruct_system_prompt(
    goal: str,
    instructions: list,
) -> tuple[str, dict[str, str] | None]:
    """Reconstruct system_prompt from goal + instructions.

    Returns (system_prompt, sections_dict_or_None).
    """
    if not goal and not instructions:
        return "", None

    # Build the raw combined text
    parts: list[str] = []
    if goal:
        parts.append(goal)

    instruction_lines: list[str] = []
    for item in instructions:
        if isinstance(item, str):
            instruction_lines.append(item)
        elif isinstance(item, dict):
            # Vertex API may return instruction objects
            text = item.get("text", "")
            if text:
                instruction_lines.append(text)

    if instruction_lines:
        parts.append("---")
        parts.extend(instruction_lines)

    system_prompt = "\n\n".join(parts) if parts else ""

    # Section detection
    # First try: run extract_sections on the combined text (handles ## headings)
    sections = extract_sections(system_prompt) if system_prompt else {}

    # If no heading-based sections found, try the "SectionName:\ncontent" pattern
    # that the Vertex emitter linearizes instructions into
    if not sections and instruction_lines:
        sections = _extract_sections_from_instructions(instruction_lines, goal)

    # If goal is present without headings, treat it as "overview"
    if goal and sections and "overview" not in sections:
        # Goal becomes the overview if not already captured
        sections["overview"] = goal.strip()
    elif goal and not sections:
        sections = {"overview": goal.strip()}

    return system_prompt, sections if sections else None


def _extract_sections_from_instructions(
    instruction_lines: list[str],
    goal: str,
) -> dict[str, str]:
    """Extract structured sections from linearized instruction strings.

    Handles the Vertex emitter's pattern of:
        "Behavior:\n- Always state the location..."
        "Restrictions:\nDo not provide weather advisories..."
    """
    sections: dict[str, str] = {}

    if goal:
        sections["overview"] = goal.strip()

    for line in instruction_lines:
        if not isinstance(line, str):
            continue
        # Check for "SectionName:\ncontent" or "SectionName: content" pattern
        m = re.match(r"^([A-Z][a-zA-Z\s-]+):\s*\n?(.*)", line, re.DOTALL)
        if m:
            prefix = m.group(1).strip()
            content = m.group(2).strip()
            key = _SECTION_PREFIX_MAP.get(prefix.lower(), prefix.lower())
            if key in sections:
                sections[key] = sections[key] + "\n" + content
            else:
                sections[key] = content
        else:
            # No prefix match → append to behavior
            existing = sections.get("behavior", "")
            if existing:
                sections["behavior"] = existing + "\n" + line.strip()
            else:
                sections["behavior"] = line.strip()

    return {k: v for k, v in sections.items() if v}


# ---------------------------------------------------------------------------
# Tool extraction
# ---------------------------------------------------------------------------


def _extract_tools(
    inline_tools: list,
    tools_data: list[dict] | None,
    *,
    readme_text: str | None = None,
) -> tuple[list[Tool], list[KnowledgeSource]]:
    """Extract IR tools and knowledge sources from Vertex tool definitions.

    Returns (tools, knowledge_sources).
    """
    tools: list[Tool] = []
    knowledge: list[KnowledgeSource] = []
    seen_names: set[str] = set()

    # Process tools.json first (higher precedence)
    if tools_data:
        for entry in tools_data:
            if not isinstance(entry, dict):
                continue
            t_or_k = _parse_tool_entry(entry)
            if t_or_k is None:
                continue
            if isinstance(t_or_k, KnowledgeSource):
                if t_or_k.name not in seen_names:
                    knowledge.append(t_or_k)
                    seen_names.add(t_or_k.name)
            elif isinstance(t_or_k, list):
                # functionDeclarations → multiple tools
                for t in t_or_k:
                    if t.name not in seen_names:
                        tools.append(t)
                        seen_names.add(t.name)
            else:
                if t_or_k.name not in seen_names:
                    tools.append(t_or_k)
                    seen_names.add(t_or_k.name)

    # Process inline tools from agent.json (lower precedence — skip if name already seen)
    for entry in inline_tools:
        if not isinstance(entry, dict):
            continue
        t_or_k = _parse_inline_tool(entry, readme_text=readme_text)
        if t_or_k is None:
            continue
        if isinstance(t_or_k, KnowledgeSource):
            if t_or_k.name not in seen_names:
                knowledge.append(t_or_k)
                seen_names.add(t_or_k.name)
        else:
            if t_or_k.name not in seen_names:
                tools.append(t_or_k)
                seen_names.add(t_or_k.name)

    return tools, knowledge


def _parse_tool_entry(
    entry: dict,
) -> Tool | KnowledgeSource | list[Tool] | None:
    """Parse a tools.json entry into Tool(s) or KnowledgeSource."""
    display_name = entry.get("displayName", "")
    description = entry.get("description", "")

    # Case 3: Data store tool → KnowledgeSource
    if "datastoreSpec" in entry:
        name = slugify(display_name) if display_name else "knowledge-base"
        datastore_id = _extract_datastore_id(entry["datastoreSpec"])
        return KnowledgeSource(
            name=name,
            kind="vector_store",
            path=datastore_id or None,
            description=description or f"Vertex data store: {display_name}",
            load_mode="indexed",
            format="unknown",
        )

    # Case 2: OpenAPI tool
    if "openApiFunctionDeclarations" in entry:
        name = slugify(display_name) if display_name else "openapi-tool"
        endpoint = _extract_server_url(entry)
        auth = _parse_vertex_auth(entry.get("authentication"))
        spec = entry.get("openApiFunctionDeclarations", {})
        params = spec.get("specification") if isinstance(spec, dict) else None
        return Tool(
            name=name,
            description=description or f"OpenAPI tool: {display_name}",
            kind="openapi",
            endpoint=endpoint or None,
            parameters=params,
            auth=auth if auth and auth.type != "none" else None,
        )

    # Case 1: Function tool (has functionDeclarations)
    if "functionDeclarations" in entry:
        result: list[Tool] = []
        for func in entry["functionDeclarations"]:
            func_name = func.get("name", "")
            if not func_name:
                continue
            func_desc = func.get("description", description)
            params = func.get("parameters")
            result.append(
                Tool(
                    name=func_name,
                    description=func_desc,
                    kind="function",
                    parameters=params,
                )
            )
        return result if result else None

    return None


def _parse_inline_tool(
    entry: dict,
    *,
    readme_text: str | None = None,
) -> Tool | KnowledgeSource | None:
    """Parse an inline tool from agent.json["tools"]."""
    name = entry.get("name", "")
    if not name:
        return None

    description = entry.get("description", "")
    tool_type = entry.get("type", "")
    stub = entry.get("x-agentshift-stub", "")

    # Check if this is a full resource path reference (Vertex API response)
    # e.g. "projects/my-project/locations/.../tools/tool-id"
    if "/" in name and not description and not tool_type:
        # Resource reference — extract last segment as name
        short_name = slugify(name.split("/")[-1])
        return Tool(
            name=short_name,
            description=f"Vertex AI tool: {short_name}",
            kind="unknown",
        )

    kind = _infer_kind_from_inline(tool_type, stub)

    return Tool(
        name=name,
        description=description or f"Tool: {name}",
        kind=kind,
    )


def _infer_kind_from_inline(tool_type: str, stub: str) -> str:
    """Infer IR kind from inline agent.json tool fields."""
    if tool_type == "OPEN_API":
        return "openapi"
    if tool_type == "FUNCTION":
        if stub:
            stub_lower = stub.lower()
            if "mcp" in stub_lower:
                return "mcp"
            if "shell" in stub_lower:
                return "shell"
            # Cloud Function or Cloud Run → function kind
            return "function"
        return "function"
    if stub:
        stub_lower = stub.lower()
        if "mcp" in stub_lower:
            return "mcp"
        if "shell" in stub_lower:
            return "shell"
    return "unknown"


# ---------------------------------------------------------------------------
# Auth reconstruction
# ---------------------------------------------------------------------------


def _parse_vertex_auth(auth: dict | None) -> ToolAuth:
    """Reconstruct IR ToolAuth from a Vertex authentication block."""
    if not auth:
        return ToolAuth(type="none")

    if "apiKeyConfig" in auth:
        cfg = auth["apiKeyConfig"]
        env_var = cfg.get("name", "API_KEY").upper().replace("-", "_")
        return ToolAuth(type="api_key", env_var=env_var)

    if "oauthConfig" in auth:
        cfg = auth["oauthConfig"]
        scope_str = cfg.get("scope", "")
        scopes = [s.strip() for s in scope_str.split() if s.strip()] if scope_str else []
        return ToolAuth(type="oauth2", scopes=scopes)

    if "serviceAccountConfig" in auth:
        cfg = auth["serviceAccountConfig"]
        service_account = cfg.get("serviceAccount", "")
        return ToolAuth(type="bearer", notes=service_account or None)

    return ToolAuth(type="none")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_server_url(entry: dict) -> str:
    """Extract a server URL from an OpenAPI tool entry if available."""
    spec = entry.get("openApiFunctionDeclarations", {})
    if isinstance(spec, dict):
        specification = spec.get("specification", {})
        if isinstance(specification, dict):
            servers = specification.get("servers", [])
            if servers and isinstance(servers[0], dict):
                return servers[0].get("url", "")
    return ""


def _extract_datastore_id(datastore_spec: dict) -> str:
    """Extract a data store ID from a Vertex datastoreSpec."""
    data_stores = datastore_spec.get("dataStores", [])
    if data_stores:
        # Return the last segment of the resource path as an identifier
        path = data_stores[0]
        return path.split("/")[-1] if "/" in path else path
    return ""
