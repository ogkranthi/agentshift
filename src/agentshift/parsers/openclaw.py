"""OpenClaw SKILL.md parser — converts a skill directory into AgentShift IR."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from agentshift.ir import (
    AgentIR,
    Constraints,
    InstallStep,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
)


def parse_skill_dir(path: Path) -> AgentIR:
    """Parse an OpenClaw skill directory and return an AgentIR."""
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"No SKILL.md found in {path}")

    raw = skill_md.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(raw)

    fm = yaml.safe_load(frontmatter) or {}

    name = fm.get("name", path.name)
    description = fm.get("description", "") or _extract_description_from_body(body)
    homepage = fm.get("homepage")
    os_list = fm.get("os", [])

    # Extract openclaw metadata
    oc_meta = {}
    meta_raw = fm.get("metadata", {})
    if isinstance(meta_raw, dict):
        oc_meta = meta_raw.get("openclaw", {})

    emoji = oc_meta.get("emoji")
    requires = oc_meta.get("requires", {})
    required_bins = requires.get("bins", [])
    any_required_bins = requires.get("anyBins", [])
    required_config_keys = requires.get("config", [])

    # Install steps
    install_steps = []
    for step in oc_meta.get("install", []):
        try:
            install_steps.append(InstallStep(**step))
        except Exception:
            pass

    # Tools: parse bash blocks and tool mentions from body
    tools = _extract_tools(body)

    # Knowledge sources from body
    knowledge = _extract_knowledge(body, name)

    # Constraints
    constraints = Constraints(
        supported_os=os_list,
        required_bins=required_bins,
        any_required_bins=any_required_bins,
        required_config_keys=required_config_keys,
    )

    persona = Persona(system_prompt=body.strip() if body.strip() else None)

    metadata = Metadata(
        source_platform="openclaw",
        source_file=str(skill_md),
        emoji=emoji,
        platform_extensions={"openclaw": oc_meta} if oc_meta else {},
    )

    return AgentIR(
        name=name,
        description=description,
        homepage=homepage,
        persona=persona,
        tools=tools,
        knowledge=knowledge,
        constraints=constraints,
        install=install_steps,
        metadata=metadata,
    )


def _extract_description_from_body(body: str) -> str:
    """Extract description from the first non-heading paragraph in the body."""
    lines = body.splitlines()
    in_paragraph = False
    para_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Skip headings, blank lines before first paragraph, code fences
        if stripped.startswith("#") or stripped.startswith("```"):
            if in_paragraph:
                break
            continue
        if not stripped:
            if in_paragraph:
                break
            continue
        in_paragraph = True
        para_lines.append(stripped)
    return " ".join(para_lines)


def _split_frontmatter(raw: str) -> tuple[str, str]:
    """Split SKILL.md into (frontmatter_yaml, body_markdown)."""
    # Must start with ---
    stripped = raw.lstrip()
    if not stripped.startswith("---"):
        return "", raw

    # Find the closing ---
    rest = stripped[3:]
    end = rest.find("\n---")
    if end == -1:
        return "", raw

    frontmatter = rest[:end].strip()
    body = rest[end + 4:].lstrip("\n")
    return frontmatter, body


def _extract_tools(body: str) -> list[Tool]:
    """Heuristically extract tool references from the markdown body."""
    tools: list[Tool] = []
    seen: set[str] = set()

    # Detect bash/shell usage
    if re.search(r"```bash|`bash |Bash\b|shell command", body, re.IGNORECASE):
        tools.append(Tool(name="bash", description="Run shell commands", kind="shell"))
        seen.add("bash")

    # Detect MCP-style tool names mentioned (e.g., "slack tool", "github tool")
    mcp_pattern = re.compile(r"\b(slack|github|jira|linear|notion)\b.*?tool", re.IGNORECASE)
    for m in mcp_pattern.finditer(body):
        tool_name = m.group(1).lower()
        if tool_name not in seen:
            tools.append(Tool(name=tool_name, description=f"{tool_name} MCP tool", kind="mcp"))
            seen.add(tool_name)

    return tools


def _extract_knowledge(body: str, skill_name: str) -> list[KnowledgeSource]:
    """Extract knowledge file references from the markdown body."""
    knowledge: list[KnowledgeSource] = []
    seen: set[str] = set()

    # Look for knowledge/ file references
    pattern = re.compile(
        r"[`'\"]?(~/.openclaw/skills/[^\s`'\"]+/knowledge/([^\s`'\"]+\.[a-z]+))[`'\"]?",
        re.IGNORECASE,
    )
    for m in pattern.finditer(body):
        file_path = m.group(1)
        file_name = m.group(2)
        if file_path not in seen:
            stem = Path(file_name).stem
            fmt = _infer_format(file_name)
            knowledge.append(
                KnowledgeSource(
                    name=stem,
                    kind="file",
                    path=file_path,
                    description=f"Knowledge file: {file_name}",
                    format=fmt,
                    load_mode="on_demand",
                )
            )
            seen.add(file_path)

    return knowledge


def _infer_format(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".txt": "text",
        ".pdf": "pdf",
        ".html": "html",
    }.get(ext, "unknown")
