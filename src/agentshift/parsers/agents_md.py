"""AGENTS.md parser — converts community AGENTS.md files into AgentShift IR.

AGENTS.md is a convention used in 60,000+ GitHub repos where developers write
instructions for AI coding agents. Format: pure markdown with sections like
Architecture, Commands, Code Style, Do NOT, etc.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentshift.ir import (
    AgentIR,
    Constraints,
    Governance,
    Guardrail,
    Metadata,
    Persona,
    Tool,
)

# ---------------------------------------------------------------------------
# Section heading → IR mapping categories
# ---------------------------------------------------------------------------

_ARCHITECTURE_HEADINGS = {"architecture", "overview", "project", "about", "introduction"}
_COMMAND_HEADINGS = {"commands", "scripts", "run", "build", "test", "testing", "tests"}
_DONOT_HEADINGS = {"do not", "don't", "dont", "never", "avoid"}
_STYLE_HEADINGS = {"style", "code style", "conventions", "formatting", "code conventions"}


def _normalize_heading(heading: str) -> str:
    """Lowercase and strip heading text for matching."""
    return heading.strip().lower()


def _heading_matches(heading: str, category: set[str]) -> bool:
    """Check if a heading matches a category (prefix match)."""
    h = _normalize_heading(heading)
    return any(h == c or h.startswith(c) for c in category)


# ---------------------------------------------------------------------------
# Tool extraction from bullets and code blocks
# ---------------------------------------------------------------------------

_BULLET_CMD_RE = re.compile(r"^[-*]\s+(?:(\w[\w\s/]*?):\s*)?[`]?(.+?)[`]?\s*$")

_CODE_BLOCK_RE = re.compile(r"```(?:bash|sh|shell|zsh)?\s*\n(.*?)```", re.DOTALL)


def _extract_binary(cmd: str) -> str:
    """Extract the binary/command name from a shell command string."""
    # Strip env vars, sudo, etc.
    cmd = cmd.strip()
    for prefix in ("sudo ", "npx ", "bunx "):
        if cmd.startswith(prefix):
            cmd = cmd[len(prefix) :]
    # First word is the binary
    parts = cmd.split()
    if not parts:
        return "unknown"
    binary = parts[0]
    # Strip path prefixes
    if "/" in binary:
        binary = binary.rsplit("/", 1)[-1]
    return binary


def _extract_tools_from_section(body: str) -> list[Tool]:
    """Extract Tool entries from a commands/scripts section."""
    tools: list[Tool] = []
    seen: set[str] = set()

    # Parse bullet points: "- Run: uvicorn src.main:app --reload"
    for line in body.splitlines():
        line = line.strip()
        m = _BULLET_CMD_RE.match(line)
        if m:
            label = m.group(1)
            cmd = m.group(2).strip().strip("`")
            if not cmd:
                continue
            binary = _extract_binary(cmd)
            name = binary
            desc = label.strip() if label else f"Run {binary}"
            key = cmd
            if key not in seen:
                seen.add(key)
                tools.append(Tool(name=name, description=f"{desc}: {cmd}", kind="shell"))

    # Parse code blocks
    for m in _CODE_BLOCK_RE.finditer(body):
        block = m.group(1).strip()
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            binary = _extract_binary(line)
            key = line
            if key not in seen:
                seen.add(key)
                tools.append(Tool(name=binary, description=f"Run: {line}", kind="shell"))

    return tools


# ---------------------------------------------------------------------------
# Guardrail extraction from "Do NOT" sections
# ---------------------------------------------------------------------------


def _extract_guardrails(body: str) -> list[Guardrail]:
    """Extract guardrails from a Do NOT / Never / Avoid section."""
    guardrails: list[Guardrail] = []
    idx = 0
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip bullet prefix
        text = re.sub(r"^[-*]\s+", "", line).strip()
        if not text:
            continue
        idx += 1
        guardrails.append(
            Guardrail(
                id=f"agents-md-rule-{idx}",
                text=text,
                category="operational",
                severity="medium",
            )
        )
    return guardrails


# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------


def parse(path: Path) -> AgentIR:
    """Parse an AGENTS.md file or directory into AgentShift IR.

    Parameters
    ----------
    path : Path
        Either a direct path to an AGENTS.md file, or a directory that
        contains one (searched at root first, then subdirectories).

    Returns
    -------
    AgentIR

    Raises
    ------
    FileNotFoundError
        If no AGENTS.md file is found.
    """
    path = Path(path)

    if path.is_file():
        md_file = path
    elif path.is_dir():
        md_file = _find_agents_md(path)
    else:
        raise FileNotFoundError(f"Path does not exist: {path}")

    content = md_file.read_text(encoding="utf-8")
    return _parse_content(content, md_file)


def _find_agents_md(directory: Path) -> Path:
    """Locate AGENTS.md in a directory (root first, then subdirs)."""
    root = directory / "AGENTS.md"
    if root.exists():
        return root

    # Search subdirectories (one level)
    for child in sorted(directory.iterdir()):
        if child.is_dir():
            candidate = child / "AGENTS.md"
            if candidate.exists():
                return candidate

    raise FileNotFoundError(f"No AGENTS.md found in {directory} or its subdirectories.")


def _parse_content(content: str, source_file: Path) -> AgentIR:
    """Parse raw AGENTS.md content into AgentIR."""
    lines = content.splitlines()

    # Extract H1 title and first paragraph (description)
    name: str | None = None
    description: str | None = None
    h1_re = re.compile(r"^#\s+(.+)$")
    first_para_lines: list[str] = []
    past_h1 = False

    for line in lines:
        m = h1_re.match(line)
        if m and name is None:
            name = m.group(1).strip()
            past_h1 = True
            continue
        if past_h1 and description is None:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                first_para_lines.append(stripped)
            elif first_para_lines:
                description = " ".join(first_para_lines)
            elif stripped.startswith("#"):
                # Hit next heading without a paragraph
                break

    # Flush description if we ran out of lines
    if description is None and first_para_lines:
        description = " ".join(first_para_lines)

    # Fallback name/description
    if not name:
        name = source_file.parent.name if source_file.parent.name != "." else "unnamed-agent"
    if not description:
        description = f"Agent instructions from {source_file.name}"

    # Parse sections by H2/H3 headings
    sections = _extract_sections(lines)

    # Map sections to IR components
    system_prompt_parts: list[str] = []
    tools: list[Tool] = []
    guardrails: list[Guardrail] = []
    guardrail_refs: list[str] = []

    for heading, body in sections:
        if _heading_matches(heading, _ARCHITECTURE_HEADINGS):
            system_prompt_parts.insert(0, f"## {heading}\n{body}")
        elif _heading_matches(heading, _COMMAND_HEADINGS):
            extracted = _extract_tools_from_section(body)
            tools.extend(extracted)
        elif _heading_matches(heading, _DONOT_HEADINGS):
            extracted_gr = _extract_guardrails(body)
            guardrails.extend(extracted_gr)
            guardrail_refs.extend(g.id for g in extracted_gr)
        elif _heading_matches(heading, _STYLE_HEADINGS):
            system_prompt_parts.append(f"## Code Style\n{body}")
        else:
            # Everything else → system_prompt
            system_prompt_parts.append(f"## {heading}\n{body}")

    system_prompt = "\n\n".join(system_prompt_parts) if system_prompt_parts else None

    return AgentIR(
        name=_slugify(name),
        description=description,
        persona=Persona(system_prompt=system_prompt),
        tools=tools,
        constraints=Constraints(guardrails=guardrail_refs),
        governance=Governance(guardrails=guardrails),
        metadata=Metadata(
            source_platform="agents-md",
            source_file=str(source_file),
        ),
    )


def _extract_sections(lines: list[str]) -> list[tuple[str, str]]:
    """Extract H2/H3 sections from lines. Returns (heading_text, body) pairs."""
    h2_re = re.compile(r"^##\s+(.+)$")
    h3_re = re.compile(r"^###\s+(.+)$")

    # Determine heading level: prefer H2, fallback to H3
    has_h2 = any(h2_re.match(line) for line in lines)
    heading_re = h2_re if has_h2 else h3_re

    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    for line in lines:
        m = heading_re.match(line)
        if m:
            if current_heading is not None:
                sections.append((current_heading, "\n".join(current_body).strip()))
            current_heading = m.group(1).strip()
            current_body = []
        elif current_heading is not None:
            current_body.append(line)

    # Flush last section
    if current_heading is not None:
        sections.append((current_heading, "\n".join(current_body).strip()))

    return sections


def _slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")
