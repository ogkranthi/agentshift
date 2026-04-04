"""NVIDIA NemoClaw emitter — converts AgentShift IR into NemoClaw sandbox artifacts.

NemoClaw is an open-source reference stack by NVIDIA that runs OpenClaw agents
inside hardened OpenShell sandboxes. It uses the same workspace files as OpenClaw
(SKILL.md, SOUL.md, IDENTITY.md) but wraps them in sandboxed containers with
network policies and inference routing.

Produces:
  workspace/SKILL.md         — agent skill definition (same as OpenClaw)
  workspace/SOUL.md          — agent persona and boundaries
  workspace/IDENTITY.md      — agent identity card
  nemoclaw-config.yaml       — sandbox configuration
  network-policy.yaml        — deny-by-default egress rules
  deploy.sh                  — one-command deployment script
  README.md                  — setup and deploy instructions
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import yaml

from agentshift.ir import AgentIR


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write NemoClaw sandbox artifacts from an AgentIR."""
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_skill_md(ir, output_dir)
    _write_soul_md(ir, output_dir)
    _write_identity_md(ir, output_dir)
    _write_nemoclaw_config(ir, output_dir)
    _write_network_policy(ir, output_dir)
    _write_deploy_sh(ir, output_dir)
    _write_readme(ir, output_dir)


# ---------------------------------------------------------------------------
# workspace/SKILL.md
# ---------------------------------------------------------------------------


def _write_skill_md(ir: AgentIR, output_dir: Path) -> None:
    ws = output_dir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "---",
        f"name: {ir.name}",
        f"description: {ir.description}",
        "---",
        "",
    ]

    # System prompt
    prompt = (ir.persona.system_prompt or "").strip()
    if prompt:
        lines.append(prompt)
        lines.append("")

    # Knowledge section
    if ir.knowledge:
        lines.append("## Knowledge")
        lines.append("")
        for ks in ir.knowledge:
            desc = ks.description or ks.path or ks.name
            lines.append(f"- **{ks.name}** ({ks.kind}): {desc}")
        lines.append("")

    # Tools section
    if ir.tools:
        lines.append("## Tools")
        lines.append("")
        for tool in ir.tools:
            lines.append(f"- **{tool.name}** ({tool.kind}): {tool.description}")
        lines.append("")

    # Guardrails section
    if ir.governance.guardrails:
        lines.append("## Guardrails")
        lines.append("")
        for g in ir.governance.guardrails:
            lines.append(f"- {g.text}")
        lines.append("")

    (ws / "SKILL.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# workspace/SOUL.md
# ---------------------------------------------------------------------------


def _write_soul_md(ir: AgentIR, output_dir: Path) -> None:
    ws = output_dir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    # Extract personality notes or default
    personality = (ir.persona.personality_notes or "").strip()
    if not personality:
        personality = "Be helpful, accurate, and concise."

    lines: list[str] = [
        "# SOUL.md - Agent Persona",
        "",
        "## Core Identity",
        personality,
        "",
        "## Boundaries",
    ]

    if ir.governance.guardrails:
        for g in ir.governance.guardrails:
            lines.append(f"- {g.text}")
    else:
        lines.append("- Follow user instructions within safe boundaries.")

    lines += [
        "",
        "## Vibe",
        "Professional, reliable, task-focused.",
        "",
    ]

    (ws / "SOUL.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# workspace/IDENTITY.md
# ---------------------------------------------------------------------------


def _write_identity_md(ir: AgentIR, output_dir: Path) -> None:
    ws = output_dir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    # Vibe from personality notes or default
    personality = (ir.persona.personality_notes or "").strip()
    vibe = personality.split("\n")[0] if personality else "Helpful and focused"

    emoji = ir.metadata.emoji or "\U0001f916"

    lines: list[str] = [
        "# IDENTITY.md",
        "",
        f"- **Name:** {ir.name}",
        "- **Creature:** AI agent",
        f"- **Vibe:** {vibe}",
        f"- **Emoji:** {emoji}",
        "",
    ]

    (ws / "IDENTITY.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# nemoclaw-config.yaml
# ---------------------------------------------------------------------------


def _write_nemoclaw_config(ir: AgentIR, output_dir: Path) -> None:
    desc = ir.description[:100] if ir.description else ""

    config = {
        "sandbox": {
            "name": ir.name,
            "description": desc,
        },
        "inference": {
            "provider": "nvidia",
        },
        "workspace": {
            "upload_on_deploy": True,
            "files": [
                "workspace/SKILL.md",
                "workspace/SOUL.md",
                "workspace/IDENTITY.md",
            ],
        },
        "security": {
            "posture": "balanced",
            "operator_approval": True,
        },
    }

    header = (
        "# NemoClaw Sandbox Configuration\n"
        "# Generated by AgentShift v0.4.0 — https://agentshift.sh\n"
        "#\n"
        "# Uncomment your preferred inference provider:\n"
        "#   provider: nvidia      — NVIDIA Nemotron via OpenShell gateway\n"
        "#   provider: anthropic   — Claude via OpenShell gateway\n"
        "#   provider: openai      — OpenAI via OpenShell gateway\n"
        "#   provider: ollama      — Local models\n"
        "#\n"
        "# Security postures: strict | balanced | developer\n\n"
    )

    content = header + yaml.dump(config, default_flow_style=False, sort_keys=False)
    (output_dir / "nemoclaw-config.yaml").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# network-policy.yaml
# ---------------------------------------------------------------------------


def _write_network_policy(ir: AgentIR, output_dir: Path) -> None:
    policies: list[dict] = [
        {
            "name": "claude_code",
            "endpoints": ["api.anthropic.com:443"],
            "binaries": ["/usr/local/bin/claude"],
        },
        {
            "name": "nvidia",
            "endpoints": [
                "integrate.api.nvidia.com:443",
                "inference-api.nvidia.com:443",
            ],
            "binaries": ["/usr/local/bin/openclaw"],
        },
    ]

    comments: list[str] = []

    for tool in ir.tools:
        if tool.kind == "shell":
            if tool.name in ("gh", "git"):
                policies.append(
                    {
                        "name": "github",
                        "endpoints": [
                            "api.github.com:443",
                            "github.com:443",
                        ],
                        "binaries": [f"/usr/local/bin/{tool.name}"],
                    }
                )
            elif tool.name in ("curl", "wget"):
                comments.append(
                    f"# TODO: Add network policy for {tool.name}\n"
                    f"# - name: custom_{tool.name}\n"
                    f"#   endpoints: [your-api.example.com:443]\n"
                    f"#   binaries: [/usr/local/bin/{tool.name}]"
                )
            elif tool.name in ("npm", "node"):
                policies.append(
                    {
                        "name": "npm_registry",
                        "endpoints": ["registry.npmjs.org:443"],
                        "binaries": [f"/usr/local/bin/{tool.name}"],
                    }
                )
        elif tool.kind == "mcp":
            comments.append(
                f"# TODO: Add network policy for MCP tool '{tool.name}'\n"
                f"# - name: mcp_{tool.name}\n"
                f"#   endpoints: [your-mcp-endpoint.example.com:443]\n"
                f"#   binaries: [/usr/local/bin/openclaw]"
            )

    header = (
        "# Network Policy — generated by AgentShift\n"
        "# NemoClaw uses deny-by-default. Add endpoints your agent needs.\n\n"
    )

    data = {"policies": policies}
    content = header + yaml.dump(data, default_flow_style=False, sort_keys=False)

    if comments:
        content += "\n" + "\n\n".join(comments) + "\n"

    (output_dir / "network-policy.yaml").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# deploy.sh
# ---------------------------------------------------------------------------


def _write_deploy_sh(ir: AgentIR, output_dir: Path) -> None:
    script = f"""#!/usr/bin/env bash
set -euo pipefail

SANDBOX_NAME="{ir.name}"
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

echo "Deploying ${{SANDBOX_NAME}} to NemoClaw..."

# Check nemoclaw is installed
if ! command -v nemoclaw &> /dev/null; then
  echo "nemoclaw CLI not found. Install: curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash"
  exit 1
fi

# Check openshell is running
if ! openshell gateway status &> /dev/null; then
  echo "OpenShell gateway not running. Start: openshell gateway start"
  exit 1
fi

# Create sandbox
echo "Creating sandbox..."
nemoclaw sandbox create "${{SANDBOX_NAME}}" \\
  --config "${{SCRIPT_DIR}}/nemoclaw-config.yaml" \\
  --network-policy "${{SCRIPT_DIR}}/network-policy.yaml"

# Upload workspace files
echo "Uploading workspace files..."
openshell sandbox upload "${{SANDBOX_NAME}}" \\
  "${{SCRIPT_DIR}}/workspace/SKILL.md" /sandbox/.openclaw/workspace/SKILL.md
openshell sandbox upload "${{SANDBOX_NAME}}" \\
  "${{SCRIPT_DIR}}/workspace/SOUL.md" /sandbox/.openclaw/workspace/SOUL.md
openshell sandbox upload "${{SANDBOX_NAME}}" \\
  "${{SCRIPT_DIR}}/workspace/IDENTITY.md" /sandbox/.openclaw/workspace/IDENTITY.md

echo "${{SANDBOX_NAME}} deployed successfully!"
echo "  Connect: nemoclaw ${{SANDBOX_NAME}} connect"
"""

    deploy_path = output_dir / "deploy.sh"
    deploy_path.write_text(script, encoding="utf-8")
    deploy_path.chmod(deploy_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# README.md
# ---------------------------------------------------------------------------


def _slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _write_readme(ir: AgentIR, output_dir: Path) -> None:
    slug = _slug(ir.name)

    lines: list[str] = [
        f"# {ir.name} — NVIDIA NemoClaw Agent",
        "",
        ir.description,
        "",
        "> **Converted from OpenClaw by [AgentShift](https://agentshift.sh)**",
        "",
        "## Generated Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        "| `workspace/SKILL.md` | Agent skill definition (OpenClaw format) |",
        "| `workspace/SOUL.md` | Agent persona and boundaries |",
        "| `workspace/IDENTITY.md` | Agent identity card |",
        "| `nemoclaw-config.yaml` | Sandbox configuration |",
        "| `network-policy.yaml` | Deny-by-default egress rules |",
        "| `deploy.sh` | One-command deployment script |",
        "| `README.md` | This file |",
        "",
        "## Prerequisites",
        "",
        "1. NVIDIA NemoClaw CLI installed:",
        "",
        "```bash",
        "curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash",
        "```",
        "",
        "2. OpenShell gateway running:",
        "",
        "```bash",
        "openshell gateway start",
        "```",
        "",
        "3. (Optional) Configure inference provider in `nemoclaw-config.yaml`.",
        "",
        "## Deploy",
        "",
        "```bash",
        "chmod +x deploy.sh",
        "./deploy.sh",
        "```",
        "",
        "## Connect",
        "",
        "```bash",
        f"nemoclaw {slug} connect",
        "```",
        "",
        "## Network Policy",
        "",
        "NemoClaw uses **deny-by-default** egress. Review `network-policy.yaml`",
        "and add any endpoints your agent needs. Policies marked with `# TODO`",
        "require manual configuration.",
        "",
    ]

    if ir.tools:
        lines += [
            "## Tools",
            "",
        ]
        for tool in ir.tools:
            lines.append(f"- **{tool.name}** ({tool.kind}): {tool.description}")
        lines.append("")

    lines += [
        "## About",
        "",
        "This agent was automatically converted using AgentShift.",
        "",
        "- **Source format:** OpenClaw SKILL.md",
        "- **Target format:** NVIDIA NemoClaw (OpenClaw + OpenShell sandbox)",
        "- **Converter:** [AgentShift](https://agentshift.sh)",
        "",
        "To convert other OpenClaw skills:",
        "```bash",
        f"agentshift convert ~/.openclaw/skills/{slug} --from openclaw --to nemoclaw --output /tmp/nemoclaw-output",
        "```",
    ]

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
