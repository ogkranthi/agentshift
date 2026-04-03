"""GitHub Copilot → IR parser.

Reads Copilot .agent.md files from a directory and produces an AgentIR.

Input artifacts:
  *.agent.md   — YAML frontmatter + markdown body (primary, required)
  README.md    — Optional MCP server enrichment

Spec: specs/copilot-parser-spec.md (A15)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from agentshift.ir import (
    AgentIR,
    Governance,
    Guardrail,
    Metadata,
    Persona,
    PlatformAnnotation,
    Tool,
    ToolAuth,
    ToolPermission,
)
from agentshift.parsers.utils import (
    extract_guardrails_from_text,
    infer_guardrail_category,
    infer_guardrail_severity,
)
from agentshift.sections import extract_sections

# ---------------------------------------------------------------------------
# Regex patterns (from spec Appendix A)
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

MCP_COMMENT_RE = re.compile(
    r"<!--\s*MCP:\s*configure\s+(\S+)\s+server\s+separately.*?-->",
    re.IGNORECASE,
)

GUARDRAILS_SECTION_RE = re.compile(
    r"^##\s+Guardrails\s*\n(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)

ELEVATED_SECTION_RE = re.compile(
    r"^##\s+Governance\s+Constraints\s+\(Elevated\)\s*\n(.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)

BULLET_RE = re.compile(r"^-\s+(.+)$", re.MULTILINE)

# Elevation template reversal patterns
DISABLED_TOOL_RE = re.compile(
    r"Do NOT use the (\S+) tool\. It is disabled\.",
    re.IGNORECASE,
)
DENY_PATTERN_RE = re.compile(
    r"When using (\S+), NEVER access paths matching:\s*(.+)",
    re.IGNORECASE,
)
READ_ONLY_RE = re.compile(
    r"The (\S+) tool is READ-ONLY",
    re.IGNORECASE,
)
RATE_LIMIT_RE = re.compile(
    r"Rate limit for (\S+): do not exceed (.+)\.",
    re.IGNORECASE,
)
MAX_VALUE_RE = re.compile(
    r"Maximum value constraint for (\S+): (.+)\.",
    re.IGNORECASE,
)
ALLOW_PATTERN_RE = re.compile(
    r"The (\S+) tool may ONLY be used for paths matching:\s*(.+)",
    re.IGNORECASE,
)
CONTENT_POLICY_RE = re.compile(r"^CONTENT POLICY:\s*(.+)", re.IGNORECASE)
PII_PROTECTION_RE = re.compile(r"^PII PROTECTION:\s*(.+)", re.IGNORECASE)
DENIED_TOPIC_RE = re.compile(r"^DENIED TOPIC:\s*(.+)", re.IGNORECASE)
GROUNDING_REQ_RE = re.compile(r"^GROUNDING REQUIREMENT:\s*(.+)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Standard tool ID mapping (§4.1 + §4.2)
# ---------------------------------------------------------------------------

_TOOL_ID_MAP: dict[str, dict[str, str]] = {
    "execute/runInTerminal": {
        "name": "bash",
        "description": "Run shell commands",
        "kind": "shell",
    },
    "read/readFile": {
        "name": "read",
        "description": "Read files from the workspace",
        "kind": "builtin",
    },
    "edit/editFiles": {
        "name": "edit",
        "description": "Create, modify, or delete files",
        "kind": "builtin",
    },
    "web": {
        "name": "web_fetch",
        "description": "Fetch web pages or call HTTP APIs",
        "kind": "builtin",
    },
    "search": {
        "name": "web_search",
        "description": "Search the web",
        "kind": "builtin",
    },
    "execute/runTask": {
        "name": "run_task",
        "description": "Run a VS Code task by name",
        "kind": "builtin",
    },
    "execute/createAndRunTask": {
        "name": "create_and_run_task",
        "description": "Create and run a VS Code task",
        "kind": "builtin",
    },
    "execute/getTerminalOutput": {
        "name": "get_terminal_output",
        "description": "Read output from last terminal run",
        "kind": "builtin",
    },
    "read/problems": {
        "name": "read_problems",
        "description": "Read compiler/linter diagnostics",
        "kind": "builtin",
    },
    "read/terminalLastCommand": {
        "name": "terminal_last_command",
        "description": "Read last terminal command + output",
        "kind": "builtin",
    },
    "read/getTaskOutput": {
        "name": "get_task_output",
        "description": "Read output from a named task",
        "kind": "builtin",
    },
    "agent": {
        "name": "agent",
        "description": "Invoke another Copilot agent",
        "kind": "builtin",
    },
    "todo": {
        "name": "todo",
        "description": "Manage VS Code TODO items",
        "kind": "builtin",
    },
    "vscode/runCommand": {
        "name": "vscode_run_command",
        "description": "Run a VS Code command by ID",
        "kind": "builtin",
    },
    "vscode/getProjectSetupInfo": {
        "name": "vscode_project_info",
        "description": "Read project language/framework info",
        "kind": "builtin",
    },
    "github.vscode-pull-request-github/doSearch": {
        "name": "github_search",
        "description": "Search GitHub issues, PRs, code",
        "kind": "builtin",
    },
    "github.vscode-pull-request-github/activePullRequest": {
        "name": "github_active_pr",
        "description": "Get context of the active PR",
        "kind": "builtin",
    },
}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def parse(input_dir: Path) -> AgentIR:
    """Parse Copilot agent artifacts from a directory into an AgentIR.

    Reads:
    - *.agent.md (primary — uses first found alphabetically)
    - README.md (optional — MCP server enrichment)

    Raises ParseError (FileNotFoundError) if no .agent.md files are found.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Copilot input directory not found: {input_dir}")

    # Support single file path
    if input_dir.is_file() and input_dir.name.endswith(".agent.md"):
        content = input_dir.read_text(encoding="utf-8")
        readme = _load_text(input_dir.parent / "README.md")
        return _parse_content(content, input_dir.name, readme)

    if not input_dir.is_dir():
        raise FileNotFoundError(f"Expected a directory, got: {input_dir}")

    agent_files = sorted(input_dir.glob("*.agent.md"))
    if not agent_files:
        raise FileNotFoundError(
            f"No .agent.md files found in {input_dir}"
        )

    primary = agent_files[0]
    content = primary.read_text(encoding="utf-8")
    readme = _load_text(input_dir / "README.md")

    return _parse_content(content, primary.name, readme)


def parse_agent_md(content: str, filename: str = "agent.agent.md") -> AgentIR:
    """Parse a single .agent.md file content string into an AgentIR."""
    return _parse_content(content, filename, readme=None)


def parse_multiple(input_dir: Path) -> list[AgentIR]:
    """Parse all .agent.md files in a directory, returning one IR per file."""
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Expected a directory, got: {input_dir}")

    agent_files = sorted(input_dir.glob("*.agent.md"))
    if not agent_files:
        raise FileNotFoundError(
            f"No .agent.md files found in {input_dir}"
        )

    readme = _load_text(input_dir / "README.md")
    results = []
    for f in agent_files:
        content = f.read_text(encoding="utf-8")
        results.append(_parse_content(content, f.name, readme))
    return results


# ---------------------------------------------------------------------------
# Core parse logic
# ---------------------------------------------------------------------------


def _parse_content(content: str, filename: str, readme: str | None) -> AgentIR:
    """Parse .agent.md content into an AgentIR."""
    # Extract frontmatter and body
    frontmatter, body = _split_frontmatter(content, filename)

    # Core fields from frontmatter
    name = frontmatter.get("name", "")
    if isinstance(name, str):
        name = name.strip().strip('"').strip("'")
    if not name:
        name = _slug_from_filename(filename)

    description = frontmatter.get("description", "")
    if isinstance(description, str):
        # Collapse multiline YAML scalars
        description = " ".join(description.split())
        description = description.strip().strip('"').strip("'")
    if not description and body:
        # First non-heading line
        for line in body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped[:200]
                break

    model_list = frontmatter.get("model", [])
    if isinstance(model_list, str):
        model_list = [model_list]

    tool_ids = frontmatter.get("tools", [])
    if tool_ids is None:
        tool_ids = []

    # Extract MCP tools from body comments
    mcp_names = MCP_COMMENT_RE.findall(body) if body else []

    # Strip MCP comments from body
    clean_body = MCP_COMMENT_RE.sub("", body).strip() if body else ""

    # Extract governance sections before cleaning
    guardrails_text = ""
    elevated_text = ""

    m = GUARDRAILS_SECTION_RE.search(clean_body)
    if m:
        guardrails_text = m.group(1)

    m = ELEVATED_SECTION_RE.search(clean_body)
    if m:
        elevated_text = m.group(1)

    # Remove governance sections from body for clean system_prompt
    clean_body = GUARDRAILS_SECTION_RE.sub("", clean_body).strip()
    clean_body = ELEVATED_SECTION_RE.sub("", clean_body).strip()

    # Build persona
    sections = extract_sections(clean_body) if clean_body else None
    language = _detect_language(clean_body)

    persona = Persona(
        system_prompt=clean_body or None,
        sections=sections if sections else None,
        language=language,
    )

    # Build tools from frontmatter tool IDs
    tools = _map_tools(tool_ids)

    # Add MCP tools from comments
    mcp_info = _parse_readme_mcp(readme) if readme else {}
    for mcp_name in mcp_names:
        desc = f"MCP server: {mcp_name}"
        pkg = mcp_info.get(mcp_name, {}).get("package")
        if pkg:
            desc = f"MCP server: {mcp_name} ({pkg})"

        auth = None
        if mcp_info.get(mcp_name, {}).get("has_env_vars"):
            auth = ToolAuth(type="config_key", config_key=f"channels.{mcp_name}")

        tools.append(
            Tool(
                name=mcp_name,
                description=desc,
                kind="mcp",
                platform_availability=["copilot"],
                auth=auth,
            )
        )

    # Build governance
    governance = _build_governance(guardrails_text, elevated_text, clean_body)

    # Build metadata
    copilot_ext: dict[str, Any] = {"source_file": filename}
    if model_list:
        copilot_ext["model"] = model_list

    metadata = Metadata(
        source_platform="copilot",
        source_file=filename,
        platform_extensions={"copilot": copilot_ext},
    )

    return AgentIR(
        name=name,
        description=description or f"Copilot agent from {filename}",
        persona=persona,
        tools=tools,
        governance=governance,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _split_frontmatter(content: str, filename: str) -> tuple[dict[str, Any], str]:
    """Split .agent.md into (frontmatter_dict, body_text)."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        # No frontmatter — entire content is the body
        return {}, content.strip()

    yaml_text = m.group(1)
    body = content[m.end():].strip()

    try:
        fm = yaml.safe_load(yaml_text)
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}

    return fm, body


def _slug_from_filename(filename: str) -> str:
    """Derive agent name from filename: 'pr-reviewer.agent.md' → 'pr-reviewer'."""
    name = filename
    if name.endswith(".agent.md"):
        name = name[: -len(".agent.md")]
    elif name.endswith(".md"):
        name = name[: -len(".md")]
    return name or "unnamed"


# ---------------------------------------------------------------------------
# Tool mapping
# ---------------------------------------------------------------------------


def _map_tools(tool_ids: list[str]) -> list[Tool]:
    """Map Copilot tool IDs to IR Tools."""
    tools: list[Tool] = []
    seen_names: set[str] = set()

    for tid in tool_ids:
        if not isinstance(tid, str):
            continue

        mapping = _TOOL_ID_MAP.get(tid)
        if mapping:
            if mapping["name"] in seen_names:
                continue
            seen_names.add(mapping["name"])
            tools.append(
                Tool(
                    name=mapping["name"],
                    description=mapping["description"],
                    kind=mapping["kind"],  # type: ignore[arg-type]
                    platform_availability=["copilot"],
                )
            )
        else:
            # Unknown tool ID — fallback
            fallback_name = tid.replace("/", "_")
            if fallback_name in seen_names:
                continue
            seen_names.add(fallback_name)
            tools.append(
                Tool(
                    name=fallback_name,
                    description=f"Copilot tool: {tid}",
                    kind="unknown",
                    platform_availability=["copilot"],
                )
            )

    return tools


# ---------------------------------------------------------------------------
# MCP README enrichment
# ---------------------------------------------------------------------------


def _parse_readme_mcp(readme: str) -> dict[str, dict[str, Any]]:
    """Extract MCP server info from README.md content.

    Returns dict of {server_name: {"package": ..., "has_env_vars": bool}}.
    """
    result: dict[str, dict[str, Any]] = {}

    # Find MCP Servers Required section
    section_re = re.compile(
        r"##\s+MCP\s+Servers\s+Required\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    m = section_re.search(readme)
    if not m:
        return result

    section_text = m.group(1)

    # Extract JSON code blocks
    json_blocks = re.findall(r"```json\s*\n(.*?)\n```", section_text, re.DOTALL)
    for block in json_blocks:
        # Try to parse the JSON — it may be a fragment
        # Look for server name patterns: "name": { "command": ... }
        server_re = re.compile(
            r'"(\w+)"\s*:\s*\{[^}]*"command"[^}]*'
            r'"args"\s*:\s*\[[^\]]*"(@[^"]+)"',
            re.DOTALL,
        )
        for match in server_re.finditer(block):
            server_name = match.group(1)
            package_name = match.group(2)
            result[server_name] = {"package": package_name, "has_env_vars": False}

    # Check for environment variable references
    env_re = re.compile(r"\b([A-Z_]+_TOKEN|[A-Z_]+_KEY|[A-Z_]+_SECRET)\b")
    has_env = bool(env_re.search(section_text))
    for name in result:
        result[name]["has_env_vars"] = has_env

    return result


# ---------------------------------------------------------------------------
# Governance extraction
# ---------------------------------------------------------------------------


def _build_governance(
    guardrails_text: str,
    elevated_text: str,
    clean_body: str,
) -> Governance:
    """Build Governance from extracted sections and body heuristics."""
    guardrails: list[Guardrail] = []
    tool_permissions: list[ToolPermission] = []
    platform_annotations: list[PlatformAnnotation] = []

    # Parse ## Guardrails section bullets
    if guardrails_text:
        bullets = BULLET_RE.findall(guardrails_text)
        for i, text in enumerate(bullets, 1):
            text = text.strip()
            if not text:
                continue
            guardrails.append(
                Guardrail(
                    id=f"G{i:03d}",
                    text=text,
                    category=infer_guardrail_category(text),
                    severity=infer_guardrail_severity(text),
                )
            )

    # Parse ## Governance Constraints (Elevated) section
    if elevated_text:
        # Strip HTML comments
        clean_elevated = re.sub(r"<!--.*?-->", "", elevated_text, flags=re.DOTALL)
        bullets = BULLET_RE.findall(clean_elevated)
        pa_idx = 1

        for text in bullets:
            text = text.strip()
            if not text:
                continue

            # Try to reverse elevation templates
            parsed = _reverse_elevation(text)
            if parsed:
                kind, data = parsed
                if kind == "tool_permission":
                    data["notes"] = (
                        "Elevated from L2 — recovered from Copilot prompt instruction"
                    )
                    tool_permissions.append(ToolPermission(**data))
                elif kind == "platform_annotation":
                    data["id"] = f"PA-{pa_idx:03d}"
                    data["platform_target"] = "any"
                    data["config"] = {}
                    platform_annotations.append(PlatformAnnotation(**data))
                    pa_idx += 1
            else:
                # Unrecognised elevation — treat as guardrail
                idx = len(guardrails) + 1
                guardrails.append(
                    Guardrail(
                        id=f"G{idx:03d}",
                        text=text,
                        category="general",
                        severity=infer_guardrail_severity(text),
                    )
                )

    # Heuristic scan of clean body for additional guardrails
    if clean_body:
        heuristic_guardrails = extract_guardrails_from_text(
            clean_body, id_prefix="G", start_index=len(guardrails) + 1
        )
        # Deduplicate against explicit guardrails
        existing_texts = {g.text.lower().strip(".") for g in guardrails}
        for hg in heuristic_guardrails:
            if hg.text.lower().strip(".") not in existing_texts:
                guardrails.append(hg)
                existing_texts.add(hg.text.lower().strip("."))

    return Governance(
        guardrails=guardrails,
        tool_permissions=tool_permissions,
        platform_annotations=platform_annotations,
    )


def _reverse_elevation(text: str) -> tuple[str, dict[str, Any]] | None:
    """Attempt to reverse an elevation template back to L2/L3 governance."""
    # Disabled tool
    m = DISABLED_TOOL_RE.search(text)
    if m:
        return "tool_permission", {
            "tool_name": m.group(1),
            "enabled": False,
            "access": "disabled",
        }

    # Read-only tool
    m = READ_ONLY_RE.search(text)
    if m:
        return "tool_permission", {
            "tool_name": m.group(1),
            "enabled": True,
            "access": "read-only",
        }

    # Deny patterns
    m = DENY_PATTERN_RE.search(text)
    if m:
        return "tool_permission", {
            "tool_name": m.group(1),
            "enabled": True,
            "deny_patterns": [m.group(2).strip()],
        }

    # Allow patterns
    m = ALLOW_PATTERN_RE.search(text)
    if m:
        return "tool_permission", {
            "tool_name": m.group(1),
            "enabled": True,
            "allow_patterns": [m.group(2).strip()],
        }

    # Rate limit
    m = RATE_LIMIT_RE.search(text)
    if m:
        return "tool_permission", {
            "tool_name": m.group(1),
            "enabled": True,
            "rate_limit": m.group(2).strip(),
        }

    # Max value
    m = MAX_VALUE_RE.search(text)
    if m:
        return "tool_permission", {
            "tool_name": m.group(1),
            "enabled": True,
            "max_value": m.group(2).strip(),
        }

    # Platform annotations
    m = CONTENT_POLICY_RE.match(text)
    if m:
        return "platform_annotation", {
            "kind": "content_filter",
            "description": m.group(1).strip(),
        }

    m = PII_PROTECTION_RE.match(text)
    if m:
        return "platform_annotation", {
            "kind": "pii_detection",
            "description": m.group(1).strip(),
        }

    m = DENIED_TOPIC_RE.match(text)
    if m:
        return "platform_annotation", {
            "kind": "denied_topics",
            "description": m.group(1).strip(),
        }

    m = GROUNDING_REQ_RE.match(text)
    if m:
        return "platform_annotation", {
            "kind": "grounding_check",
            "description": m.group(1).strip(),
        }

    return None


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def _detect_language(body: str) -> str:
    """Simple language directive detection."""
    if not body:
        return "en"
    lang_re = re.compile(r"[Rr]espond\s+in\s+(\w+)", re.IGNORECASE)
    m = lang_re.search(body)
    if m:
        lang = m.group(1).lower()
        lang_map = {
            "spanish": "es",
            "french": "fr",
            "german": "de",
            "italian": "it",
            "portuguese": "pt",
            "japanese": "ja",
            "chinese": "zh",
            "korean": "ko",
            "arabic": "ar",
            "hindi": "hi",
            "russian": "ru",
            "english": "en",
        }
        return lang_map.get(lang, "en")
    return "en"


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _load_text(path: Path) -> str | None:
    """Load a plain-text file, returning None if absent."""
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
