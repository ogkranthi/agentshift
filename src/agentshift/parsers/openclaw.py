"""OpenClaw SKILL.md parser — converts a skill directory into AgentShift IR."""

from __future__ import annotations

import contextlib
import json
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
    Trigger,
    TriggerDelivery,
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
        with contextlib.suppress(Exception):
            install_steps.append(InstallStep(**step))

    # Tools: parse bash blocks and tool mentions from body
    tools = _extract_tools(body)

    # Triggers: read jobs.json and match by agentId == skill name
    triggers = _extract_triggers(path, name)

    # Knowledge sources — from body text AND from disk
    knowledge = _extract_knowledge(body, name)
    knowledge = _merge_knowledge_from_disk(knowledge, path)

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
        triggers=triggers,
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
    body = rest[end + 4 :].lstrip("\n")
    return frontmatter, body


def _extract_triggers(skill_dir: Path, agent_name: str) -> list[Trigger]:
    """Read ~/.openclaw/cron/jobs.json and return triggers matching this skill's agentId."""
    jobs_path = Path.home() / ".openclaw" / "cron" / "jobs.json"
    if not jobs_path.exists():
        return []

    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    triggers: list[Trigger] = []
    for job in data.get("jobs", []):
        if job.get("agentId") != agent_name:
            continue
        if not job.get("enabled", True):
            continue

        cron_expr = job.get("schedule", {}).get("expr")
        message = job.get("payload", {}).get("message")
        job_id = job.get("id")
        session_target = job.get("sessionTarget", "isolated")

        # Map delivery
        delivery = None
        raw_delivery = job.get("delivery", {})
        if raw_delivery:
            channel = raw_delivery.get("channel")
            to = raw_delivery.get("to")
            mode = raw_delivery.get("mode", "announce")
            account_id = raw_delivery.get("accountId")
            delivery = TriggerDelivery(
                mode=mode,
                channel=channel,
                to=to,
                account_id=account_id,
            )

        triggers.append(
            Trigger(
                id=job_id,
                kind="cron",
                cron_expr=cron_expr,
                message=message,
                session_target=session_target,
                delivery=delivery,
                enabled=True,
            )
        )

    return triggers


_SHELL_BUILTINS: frozenset[str] = frozenset(
    [
        "if",
        "for",
        "while",
        "until",
        "do",
        "done",
        "then",
        "else",
        "elif",
        "fi",
        "case",
        "esac",
        "function",
        "return",
        "exit",
        "break",
        "continue",
        "echo",
        "export",
        "cd",
        "source",
        ".",
        "set",
        "read",
        "local",
        "declare",
        "typeset",
        "eval",
        "exec",
        "test",
        "true",
        "false",
        "[",
        "[[",
        "]]",
        "]",
        "shift",
        "unset",
        "wait",
        "trap",
        "printf",
        "type",
        "alias",
        "unalias",
        "let",
        "select",
        "time",
        "in",
    ]
)

_KNOWN_MCP_TOOLS: frozenset[str] = frozenset(
    [
        "slack",
        "github",
        "notion",
        "discord",
        "trello",
        "linear",
        "jira",
        "asana",
        "figma",
        "zoom",
        "calendar",
    ]
)


def _extract_tools(body: str) -> list[Tool]:
    """Heuristically extract tool references from the markdown body."""
    tools: list[Tool] = []
    seen: set[str] = set()

    # --- Shell binaries from ```bash / ```sh / ```shell code blocks ---
    bash_block_re = re.compile(r"```(?:bash|sh|shell)\n(.*?)```", re.DOTALL | re.IGNORECASE)
    _heredoc_start_re = re.compile(r"<<[-]?\s*['\"]?([A-Z_][A-Z0-9_]*)['\"]?")
    found_bash_block = False
    for block_match in bash_block_re.finditer(body):
        found_bash_block = True
        heredoc_terminator: str | None = None
        for line in block_match.group(1).splitlines():
            stripped = line.strip()
            # Heredoc end
            if heredoc_terminator is not None:
                if stripped == heredoc_terminator:
                    heredoc_terminator = None
                continue
            if not stripped or stripped.startswith("#"):
                continue
            # Detect heredoc start on this line (e.g. <<'EOF' or <<"HTML")
            hdoc = _heredoc_start_re.search(stripped)
            if hdoc:
                heredoc_terminator = hdoc.group(1)
            tokens = stripped.split()
            if not tokens:
                continue
            token = tokens[0]
            # Handle inline env-var assignments like VAR=val command
            while "=" in token and not token.startswith("-"):
                tokens = tokens[1:]
                if not tokens:
                    break
                token = tokens[0]
            if not tokens:
                continue
            # Handle sudo / env / command prefix
            if token in ("sudo", "env", "command") and len(tokens) > 1:
                token = tokens[1]
            # Must start with a letter
            if not token or not re.match(r"^[a-zA-Z]", token):
                continue
            m = re.match(r"^([a-zA-Z][a-zA-Z0-9_.+-]*)", token)
            if not m:
                continue
            binary = m.group(1).lower()
            if binary in _SHELL_BUILTINS:
                continue
            if binary not in seen:
                tools.append(Tool(name=binary, description=f"Run {binary} commands", kind="shell"))
                seen.add(binary)

    # Fallback: bash block existed but no specific binaries found → generic bash
    if found_bash_block and not any(t.kind == "shell" for t in tools):
        tools.append(Tool(name="bash", description="Run shell commands", kind="shell"))
        seen.add("bash")

    # --- MCP tools from prose patterns ---
    # Pattern 1: "`<name>` tool" or "<name> tool" where name is a known MCP service
    mcp_name_alts = "|".join(re.escape(n) for n in sorted(_KNOWN_MCP_TOOLS))
    prose_tool_re = re.compile(rf"\b({mcp_name_alts})\b\s*tool", re.IGNORECASE)
    for m in prose_tool_re.finditer(body):
        name = m.group(1).lower()
        if name not in seen:
            tools.append(Tool(name=name, description=f"{name} MCP tool", kind="mcp"))
            seen.add(name)

    # Pattern 2: "use `<name>`" or "use the `<name>`"
    use_backtick_re = re.compile(r"use\s+(?:the\s+)?`([a-z][a-z0-9_-]*)`", re.IGNORECASE)
    for m in use_backtick_re.finditer(body):
        name = m.group(1).lower()
        if name in _KNOWN_MCP_TOOLS and name not in seen:
            tools.append(Tool(name=name, description=f"{name} MCP tool", kind="mcp"))
            seen.add(name)

    # Pattern 3: "`<name>` tool" (backtick-quoted)
    backtick_tool_re = re.compile(r"`([a-z][a-z0-9_-]*)`\s+tool", re.IGNORECASE)
    for m in backtick_tool_re.finditer(body):
        name = m.group(1).lower()
        if name in _KNOWN_MCP_TOOLS and name not in seen:
            tools.append(Tool(name=name, description=f"{name} MCP tool", kind="mcp"))
            seen.add(name)

    # Pattern 4: "via `<name>`"
    via_re = re.compile(r"via\s+`([a-z][a-z0-9_-]*)`", re.IGNORECASE)
    for m in via_re.finditer(body):
        name = m.group(1).lower()
        if name in _KNOWN_MCP_TOOLS and name not in seen:
            tools.append(Tool(name=name, description=f"{name} MCP tool", kind="mcp"))
            seen.add(name)

    # --- JSON action blocks (e.g. bluebubbles, wacli) ---
    # Detect ```json blocks with "channel" or "action" fields → OpenClaw message tool
    json_block_re = re.compile(r"```json\n(.*?)```", re.DOTALL | re.IGNORECASE)
    channel_re = re.compile(r'"channel"\s*:\s*"([a-z][a-z0-9_-]*)"', re.IGNORECASE)
    for block_match in json_block_re.finditer(body):
        block = block_match.group(1)
        if '"action"' in block:
            for cm in channel_re.finditer(block):
                channel_name = cm.group(1).lower()
                if channel_name not in seen:
                    tools.append(
                        Tool(
                            name=channel_name,
                            description=f"{channel_name} messaging channel (OpenClaw message tool)",
                            kind="mcp",
                        )
                    )
                    seen.add(channel_name)

    # --- Prose backtick CLI extraction ---
    # Only extract from patterns that strongly indicate a CLI invocation:
    #   `<binary> <arg>...`  — binary followed by at least one argument/flag
    # This avoids picking up JSON field names, prose words, etc.
    # Require: snippet starts with a word, has at least one space (i.e. has an argument)
    inline_cli_re = re.compile(r"`([a-zA-Z][a-zA-Z0-9_.-]+\s+[^`\n]{1,80})`")
    for m in inline_cli_re.finditer(body):
        snippet = m.group(1).strip()
        tokens = snippet.split()
        if len(tokens) < 2:
            continue
        token = tokens[0]
        if token.startswith("-") or token.startswith("/") or token.startswith("."):
            continue
        binary = re.match(r"^([a-zA-Z][a-zA-Z0-9_.+-]*)", token)
        if not binary:
            continue
        bin_name = binary.group(1).lower()
        if bin_name in _SHELL_BUILTINS or bin_name in seen:
            continue
        if bin_name in _KNOWN_MCP_TOOLS:
            tools.append(Tool(name=bin_name, description=f"{bin_name} MCP tool", kind="mcp"))
        else:
            tools.append(Tool(name=bin_name, description=f"Run {bin_name} commands", kind="shell"))
        seen.add(bin_name)

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


def _merge_knowledge_from_disk(
    existing: list[KnowledgeSource], skill_dir: Path
) -> list[KnowledgeSource]:
    """Scan the skill's knowledge/ directory on disk and add any files not already in the list."""
    knowledge_dir = skill_dir / "knowledge"
    if not knowledge_dir.is_dir():
        return existing

    seen_names = {k.name for k in existing}
    result = list(existing)

    for f in sorted(knowledge_dir.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        stem = f.stem
        if stem in seen_names:
            continue
        fmt = _infer_format(f.name)
        canonical_path = f"~/.openclaw/skills/{skill_dir.name}/knowledge/{f.name}"
        result.append(
            KnowledgeSource(
                name=stem,
                kind="file",
                path=canonical_path,
                description=f"Knowledge file: {f.name}",
                format=fmt,
                load_mode="on_demand",
            )
        )
        seen_names.add(stem)

    return result


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
