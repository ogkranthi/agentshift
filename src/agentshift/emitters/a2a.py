"""A2A Agent Card emitter — converts AgentShift IR into agent-card.json.

Generates an A2A (Agent-to-Agent) Agent Card JSON document per the A2A protocol
specification (v1.0.0). The Agent Card describes an agent's identity, capabilities,
skills, and authentication requirements for inter-agent discovery.

Spec: specs/a2a-agent-card-spec.md (A16)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentshift.ir import AgentIR


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write an A2A Agent Card JSON from an AgentIR.

    Outputs:
    - agent-card.json (the Agent Card)
    - README.md (deployment instructions)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    card = _build_agent_card(ir)

    (output_dir / "agent-card.json").write_text(
        json.dumps(card, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_readme(ir, output_dir)


# ---------------------------------------------------------------------------
# Agent Card builder
# ---------------------------------------------------------------------------


def _build_agent_card(ir: AgentIR) -> dict[str, Any]:
    """Build the full Agent Card dict from an IR."""
    card: dict[str, Any] = {
        "name": ir.name,
        "description": _build_description(ir),
        "version": ir.version or "1.0.0",
        "supportedInterfaces": [
            {
                "url": "https://TODO.example.com/a2a/v1",
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            }
        ],
    }

    # Provider
    provider = _build_provider(ir)
    if provider:
        card["provider"] = provider

    # Documentation URL
    if ir.homepage:
        card["documentationUrl"] = ir.homepage

    # Capabilities
    card["capabilities"] = _build_capabilities(ir)

    # Default modes
    input_modes = ["text/plain"]
    if ir.knowledge:
        for ks in ir.knowledge:
            if ks.format == "json":
                input_modes.append("application/json")
                break
    card["defaultInputModes"] = input_modes
    card["defaultOutputModes"] = ["text/plain"]

    # Skills
    card["skills"] = _build_skills(ir)

    # Security schemes
    security_schemes = _build_security_schemes(ir)
    if security_schemes:
        card["securitySchemes"] = security_schemes
        card["securityRequirements"] = [
            {name: []} for name in security_schemes
        ]

    return card


# ---------------------------------------------------------------------------
# Description enrichment
# ---------------------------------------------------------------------------


def _build_description(ir: AgentIR) -> str:
    """Build enriched description from IR fields."""
    desc = ir.description
    if ir.persona and ir.persona.personality_notes:
        desc = f"{desc}\n\n{ir.persona.personality_notes}"
    return desc


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


def _build_provider(ir: AgentIR) -> dict[str, str] | None:
    """Build provider dict from IR author/homepage."""
    if not ir.author and not ir.homepage:
        return None
    return {
        "organization": ir.author or "Unknown",
        "url": ir.homepage or "https://example.com",
    }


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


def _build_capabilities(ir: AgentIR) -> dict[str, Any]:
    """Build capabilities including streaming, push notifications, and governance extension."""
    streaming = False
    push_notifications = False

    for trigger in ir.triggers:
        if trigger.kind in ("webhook", "event"):
            push_notifications = True
            streaming = True
        elif trigger.kind != "cron":
            streaming = True

    caps: dict[str, Any] = {
        "streaming": streaming,
        "pushNotifications": push_notifications,
    }

    # Governance extension
    gov = ir.governance
    has_governance = (
        gov.guardrails or gov.tool_permissions or gov.platform_annotations
    )
    if has_governance:
        categories = sorted(
            {g.category for g in gov.guardrails if g.category != "general"}
        )
        caps["extensions"] = [
            {
                "uri": "https://agentshift.sh/extensions/governance/v1",
                "description": "Agent governance constraints (guardrails, tool permissions, platform annotations)",
                "required": False,
                "params": {
                    "guardrail_count": len(gov.guardrails),
                    "tool_permission_count": len(gov.tool_permissions),
                    "platform_annotation_count": len(gov.platform_annotations),
                    "guardrail_categories": categories,
                    "summary": (
                        f"This agent has {' and '.join(categories) if categories else 'general'} guardrails. "
                        "Use 'agentshift audit' for full governance details."
                    ),
                },
            }
        ]

    return caps


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


def _build_skills(ir: AgentIR) -> list[dict[str, Any]]:
    """Map IR tools to A2A skills."""
    if not ir.tools:
        # At least one skill required — use the agent itself
        tags = list(ir.metadata.tags) if ir.metadata.tags else [ir.name]
        return [
            {
                "id": ir.name,
                "name": ir.name.replace("-", " ").replace("_", " ").title(),
                "description": ir.description,
                "tags": tags,
            }
        ]

    skills = []
    base_tags = list(ir.metadata.tags) if ir.metadata.tags else []

    for tool in ir.tools:
        skill_tags = list(base_tags)
        if tool.kind and tool.kind not in skill_tags:
            skill_tags.append(tool.kind)
        if not skill_tags:
            skill_tags = [tool.name]

        skills.append(
            {
                "id": tool.name,
                "name": tool.name.replace("_", " ").title(),
                "description": tool.description,
                "tags": skill_tags,
            }
        )

    return skills


# ---------------------------------------------------------------------------
# Security schemes
# ---------------------------------------------------------------------------


def _build_security_schemes(ir: AgentIR) -> dict[str, Any]:
    """Build securitySchemes from IR tool auth."""
    schemes: dict[str, Any] = {}

    for tool in ir.tools:
        if not tool.auth or tool.auth.type in ("none", "config_key"):
            continue

        if tool.auth.type == "api_key":
            schemes[f"{tool.name}_api_key"] = {
                "apiKeySecurityScheme": {
                    "location": "header",
                    "name": tool.auth.env_var or "Authorization",
                }
            }
        elif tool.auth.type == "bearer":
            schemes[f"{tool.name}_bearer"] = {
                "httpAuthSecurityScheme": {
                    "scheme": "Bearer",
                }
            }
        elif tool.auth.type == "oauth2":
            schemes[f"{tool.name}_oauth2"] = {
                "oauth2SecurityScheme": {
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "https://TODO.example.com/oauth/token",
                            "scopes": {
                                s: s for s in (tool.auth.scopes or [])
                            },
                        }
                    }
                }
            }
        elif tool.auth.type == "basic":
            schemes[f"{tool.name}_basic"] = {
                "httpAuthSecurityScheme": {
                    "scheme": "Basic",
                }
            }

    return schemes


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


def _write_readme(ir: AgentIR, output_dir: Path) -> None:
    """Write deployment instructions README."""
    lines = [
        f"# {ir.name} — A2A Agent Card",
        "",
        ir.description,
        "",
        "> **Generated by [AgentShift](https://agentshift.sh)**",
        "",
        "## What is this?",
        "",
        "This directory contains an [A2A Agent Card](https://a2a-protocol.org) — a JSON",
        "document that describes this agent's identity, capabilities, and skills for",
        "inter-agent discovery per the A2A protocol (v1.0.0).",
        "",
        "## Deployment",
        "",
        "1. **Serve the Agent Card** at your agent's well-known URL:",
        "   ```",
        "   https://your-domain.com/.well-known/agent-card.json",
        "   ```",
        "",
        "2. **Update the `supportedInterfaces` URL** in `agent-card.json` to point to",
        "   your actual A2A endpoint (replace `https://TODO.example.com/a2a/v1`).",
        "",
        "3. **Configure security** if your agent requires authentication — update the",
        "   `securitySchemes` and `securityRequirements` fields as needed.",
        "",
        "## Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        "| `agent-card.json` | A2A Agent Card (serve at `/.well-known/agent-card.json`) |",
        "| `README.md` | This file — deployment instructions |",
        "",
        "## Converting from other formats",
        "",
        "```bash",
        "# From OpenClaw",
        "agentshift convert ~/.openclaw/skills/<skill> --from openclaw --to a2a",
        "",
        "# From Copilot",
        "agentshift convert ./copilot-agent/ --from copilot --to a2a",
        "```",
    ]

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
