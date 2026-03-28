"""AWS Bedrock emitter — converts AgentShift IR into Bedrock agent artifacts.

Produces:
  instruction.txt      — system prompt (≤ 4,000 chars)
  instruction-full.txt — untruncated prompt (only when truncated)
  openapi.json         — OpenAPI 3.0 action group schema
  cloudformation.yaml  — CloudFormation template for the Bedrock agent
  README.md            — setup and deploy instructions
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from agentshift.ir import AgentIR

_MAX_INSTRUCTION_CHARS = 4000
_TRUNCATION_SAFE_LIMIT = 3900
_FOUNDATION_MODEL_DEFAULT = "anthropic.claude-3-5-sonnet-20241022-v2:0"


def emit(ir: AgentIR, output_dir: Path) -> None:
    """Write Bedrock agent artifacts from an AgentIR."""
    output_dir.mkdir(parents=True, exist_ok=True)

    instruction, truncated = _build_instruction(ir)
    guardrail_config = _build_guardrail_config(ir)
    _write_instruction(ir, output_dir, instruction, truncated)
    if guardrail_config:
        _write_guardrail_config(output_dir, guardrail_config)
    _write_openapi_json(ir, output_dir)
    _write_cloudformation(ir, output_dir, instruction, truncated, guardrail_config)
    _write_readme(ir, output_dir)


# ---------------------------------------------------------------------------
# Instruction helpers
# ---------------------------------------------------------------------------


def _build_instruction(ir: AgentIR) -> tuple[str, bool]:
    """Return (instruction_text, was_truncated).

    When persona.sections is present, assembles instruction from structured sections
    per spec §5.1: overview + behavior + tools + knowledge + persona (style note).
    Guardrails are routed to guardrailConfiguration separately.
    Falls back to system_prompt when sections is absent.
    """
    sections = ir.persona.sections

    if sections:
        # Assemble instruction from sections in canonical order (excluding guardrails)
        instruction_section_order = ["overview", "behavior", "tools", "knowledge"]
        parts: list[str] = []
        for key in instruction_section_order:
            val = sections.get(key)
            if val:
                heading = key.replace("-", " ").title()
                parts.append(f"## {heading}\n{val}")

        # Append persona/style note
        persona_section = sections.get("persona")
        if persona_section:
            parts.append(f"Tone and style: {persona_section}")

        # Add any remaining sections not already handled (excluding guardrails, examples)
        handled = set(instruction_section_order) | {"guardrails", "persona", "examples", "preamble"}
        for key, val in sections.items():
            if key not in handled and val:
                heading = key.replace("-", " ").title()
                parts.append(f"## {heading}\n{val}")

        raw = "\n\n".join(parts).strip()
        if not raw:
            raw = (ir.persona.system_prompt or "").strip() or ir.description
    else:
        raw = (ir.persona.system_prompt or "").strip()
        if not raw:
            raw = ir.description

    if len(raw) <= _MAX_INSTRUCTION_CHARS:
        return raw, False

    # Build the notice first (its length depends on original len, which is fixed)
    notice = (
        f"\n\n[AGENTSHIFT: Full instructions truncated to 4,000 char Bedrock limit. "
        f"Original: {len(raw)} chars. See instruction-full.txt for complete text.]"
    )
    # Reserve space for the notice so total stays within the 4000-char limit
    max_body = _MAX_INSTRUCTION_CHARS - len(notice)

    # Truncate at last sentence boundary within max_body
    candidate = raw[:max_body]
    match = re.search(r"[.!?][^.!?]*$", candidate)
    if match:
        candidate = candidate[: match.start() + 1]
    else:
        ws = candidate.rfind(" ")
        if ws > 0:
            candidate = candidate[:ws]

    truncated_text = candidate + notice
    return truncated_text, True


def _build_guardrail_config(ir: AgentIR) -> dict | None:
    """Build Bedrock guardrailConfiguration from persona.sections['guardrails'].

    Returns None when sections is absent or has no guardrails key.
    """
    sections = ir.persona.sections
    if not sections:
        return None
    guardrails_text = sections.get("guardrails")
    if not guardrails_text:
        return None

    # Parse sentences/lines as individual restrictions
    sentences = re.split(r"[.!?\n]+", guardrails_text)
    topics: list[dict] = []
    seen_names: set[str] = set()

    for sentence in sentences:
        sentence = sentence.strip().strip("-").strip("*").strip()
        if not sentence:
            continue
        # Build a slug topic name from first few words
        words = re.findall(r"[a-z]+", sentence.lower())[:4]
        if not words:
            continue
        name = "-".join(words)
        if name in seen_names:
            continue
        seen_names.add(name)
        topics.append(
            {
                "name": name,
                "definition": sentence[:200],
                "type": "DENY",
            }
        )

    if not topics:
        return None

    return {
        "topicPolicyConfig": {
            "topicsConfig": topics,
        }
    }


def _write_instruction(ir: AgentIR, output_dir: Path, instruction: str, truncated: bool) -> None:
    (output_dir / "instruction.txt").write_text(instruction, encoding="utf-8")
    if truncated:
        raw = (ir.persona.system_prompt or "").strip() or ir.description
        (output_dir / "instruction-full.txt").write_text(raw, encoding="utf-8")


def _write_guardrail_config(output_dir: Path, guardrail_config: dict) -> None:
    """Write guardrail-config.json when persona.sections['guardrails'] is present."""
    (output_dir / "guardrail-config.json").write_text(
        json.dumps(guardrail_config, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# OpenAPI JSON
# ---------------------------------------------------------------------------


def _write_openapi_json(ir: AgentIR, output_dir: Path) -> None:
    paths: dict = {}

    for tool in ir.tools:
        if tool.kind == "shell":
            path_key = f"/{tool.name}/run"
            paths[path_key] = {
                "post": {
                    "operationId": f"{tool.name}_run",
                    "description": tool.description or f"Run the {tool.name} shell tool.",
                    "x-agentshift-stub": True,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "command": {
                                            "type": "string",
                                            "description": f"The {tool.name} command to run.",
                                        },
                                        "args": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Arguments passed to the command.",
                                        },
                                    },
                                    "required": ["command"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Command output",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "stdout": {"type": "string"},
                                            "stderr": {"type": "string"},
                                            "exit_code": {"type": "integer"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }

        elif tool.kind == "mcp":
            path_key = f"/{tool.name}/action"
            paths[path_key] = {
                "post": {
                    "operationId": f"{tool.name}_action",
                    "description": tool.description or f"Invoke action on {tool.name} MCP tool.",
                    "x-agentshift-stub": True,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "action": {
                                            "type": "string",
                                            "description": f"The {tool.name} action to invoke.",
                                        },
                                        "params": {
                                            "type": "object",
                                            "description": "Parameters for the action.",
                                        },
                                    },
                                    "required": ["action"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Action result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "result": {"type": "object"},
                                            "status": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }

    schema = {
        "openapi": "3.0.0",
        "info": {
            "title": f"{ir.name} Actions",
            "description": f"Action group schema for the {ir.name} Bedrock agent.",
            "version": "1.0.0",
        },
        "paths": paths,
    }

    (output_dir / "openapi.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# CloudFormation YAML
# ---------------------------------------------------------------------------


def _slug(name: str) -> str:
    """Convert agent name to a CF-safe slug."""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _cf_logical_id(name: str) -> str:
    """Pascal-case a slug for use as a CF logical ID."""
    return "".join(part.capitalize() for part in re.split(r"[-_]", name) if part)


def _escape_yaml_scalar(text: str) -> str:
    """Escape a string for use as a YAML double-quoted scalar."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _write_cloudformation(
    ir: AgentIR,
    output_dir: Path,
    instruction: str,
    truncated: bool,
    guardrail_config: dict | None = None,
) -> None:
    slug = _slug(ir.name)
    logical = _cf_logical_id(slug)
    agent_logical = f"{logical}Agent"
    alias_logical = f"{logical}AgentAlias"

    # Foundation model — allow override from platform_extensions
    foundation_model = ir.metadata.platform_extensions.get("bedrock", {}).get(
        "foundation_model", _FOUNDATION_MODEL_DEFAULT
    )

    # Description truncated to 200 chars
    description = (ir.description or "")[:200]

    # Inline instruction (single-line escaped for YAML double-quoted scalar)
    escaped_instruction = _escape_yaml_scalar(instruction)

    lines: list[str] = []

    lines.append('AWSTemplateFormatVersion: "2010-09-09"')
    lines.append(f"Description: AgentShift-generated Bedrock agent — {ir.name}")
    lines.append("")

    # Parameters
    lines.append("Parameters:")
    lines.append("  AgentName:")
    lines.append("    Type: String")
    lines.append(f"    Default: {slug}")
    lines.append(f'    Description: "Name for the Bedrock agent (default: {slug})"')
    lines.append("  Environment:")
    lines.append("    Type: String")
    lines.append("    Default: prod")
    lines.append('    Description: "Deployment environment (e.g. prod, staging)"')
    lines.append("  AgentRoleArn:")
    lines.append("    Type: String")
    lines.append('    Description: "IAM Role ARN with bedrock:InvokeModel permissions (required)"')
    lines.append("")

    # Resources
    lines.append("Resources:")

    # BedrockAgent
    lines.append(f"  {agent_logical}:")
    lines.append("    Type: AWS::Bedrock::Agent")
    lines.append("    Properties:")
    lines.append('      AgentName: !Sub "${AgentName}-${Environment}"')
    lines.append("      AgentResourceRoleArn: !Ref AgentRoleArn")
    if description:
        lines.append(f'      Description: "{_escape_yaml_scalar(description)}"')
    if truncated:
        lines.append("      # WARNING: Instruction truncated to 4000 chars (Bedrock limit).")
        lines.append("      # See instruction-full.txt for the complete system prompt.")
    lines.append(f'      Instruction: "{escaped_instruction}"')
    lines.append(f"      FoundationModel: {foundation_model}")
    lines.append("      IdleSessionTTLInSeconds: 1800")
    lines.append("      AutoPrepare: true")
    if guardrail_config:
        lines.append("      # Guardrail config generated from persona.sections['guardrails']")
        lines.append("      # See guardrail-config.json for the full guardrailConfiguration payload.")
        lines.append("      # TODO [agentshift]: Create a Bedrock Guardrail resource and reference it here.")
        lines.append("      # GuardrailConfiguration:")
        lines.append("      #   GuardrailIdentifier: !Ref GuardrailPlaceholder")

    # ActionGroups — one per shell or mcp tool
    action_tools = [t for t in ir.tools if t.kind in ("shell", "mcp")]
    if action_tools:
        lines.append("      ActionGroups:")
        for tool in action_tools:
            ag_name = f"{slug}-{_slug(tool.name)}"
            lines.append(f"        - ActionGroupName: {ag_name}")
            lines.append("          Description: >-")
            tool_desc = (tool.description or f"Action group for {tool.name}").replace("\n", " ")
            lines.append(f"            {tool_desc}")
            lines.append("          ActionGroupExecutor:")
            lines.append(
                f"            Lambda: arn:aws:lambda:us-east-1:123456789012:function:{ag_name}-handler"
                f"  # TODO [agentshift]: Replace with real Lambda ARN for tool '{tool.name}'"
            )
            lines.append("          ActionGroupState: ENABLED")
            if tool.kind == "shell":
                lines.append(
                    f"          # TODO [agentshift]: Shell tool '{tool.name}' has no native Bedrock equivalent."
                )
                lines.append(
                    "          # Implement this tool's logic in the action group Lambda above."
                )
            elif tool.kind == "mcp":
                lines.append(
                    f"          # TODO [agentshift]: MCP tool '{tool.name}' has no Bedrock equivalent."
                )
                lines.append(
                    "          # Implement this functionality in the action group Lambda or remove it."
                )
                lines.append(
                    f"          # Original IR tool: name={tool.name}, kind=mcp, description={tool.description!r}"
                )
            if tool.auth and tool.auth.type != "none":
                auth_type = tool.auth.type
                env_var = tool.auth.env_var or f"{tool.name.upper().replace('-', '_')}_API_KEY"
                lines.append(
                    f"          # TODO [agentshift]: Auth setup required for '{tool.name}': {auth_type}."
                )
                lines.append(
                    f"          # Set environment variable '{env_var}' in Lambda function configuration."
                )
                if tool.auth.notes:
                    lines.append(f"          # Auth notes: {tool.auth.notes}")

    # KnowledgeBases
    if ir.knowledge:
        lines.append("      KnowledgeBases:")
        for ks in ir.knowledge:
            kb_desc = (ks.description or ks.name).replace("\n", " ")[:200]
            lines.append("        - KnowledgeBaseId: kb-PLACEHOLDER-TODO")
            lines.append(
                f"          # TODO [agentshift]: Replace kb-PLACEHOLDER-TODO with the real Knowledge Base ID for '{ks.name}'"
            )
            lines.append("          KnowledgeBaseState: ENABLED")
            lines.append("          Description: >-")
            lines.append(f"            {kb_desc}")

    lines.append("")

    # AgentAlias
    lines.append(f"  {alias_logical}:")
    lines.append("    Type: AWS::Bedrock::AgentAlias")
    lines.append("    Properties:")
    lines.append(f"      AgentId: !GetAtt {agent_logical}.AgentId")
    lines.append("      AgentAliasName: live")
    lines.append('      Description: "Production alias (managed by AgentShift)"')
    lines.append("")

    # Outputs
    lines.append("Outputs:")
    lines.append("  AgentId:")
    lines.append(f"    Value: !GetAtt {agent_logical}.AgentId")
    lines.append('    Description: "The Bedrock Agent ID"')
    lines.append("  AgentArn:")
    lines.append(f"    Value: !GetAtt {agent_logical}.AgentArn")
    lines.append('    Description: "The Bedrock Agent ARN"')
    lines.append("  AliasId:")
    lines.append(f"    Value: !GetAtt {alias_logical}.AgentAliasId")
    lines.append('    Description: "The Bedrock Agent Alias ID"')
    lines.append("")

    (output_dir / "cloudformation.yaml").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


def _write_readme(ir: AgentIR, output_dir: Path) -> None:
    slug = _slug(ir.name)
    action_tools = [t for t in ir.tools if t.kind in ("shell", "mcp")]

    lines: list[str] = [
        f"# {ir.name} — AWS Bedrock Agent",
        "",
        ir.description,
        "",
        "> **Converted from OpenClaw by [AgentShift](https://agentshift.sh)**",
        "",
        "## Generated Files",
        "",
        "| File | Description |",
        "|------|-------------|",
        "| `instruction.txt` | Agent system prompt (≤ 4,000 chars, Bedrock limit) |",
        "| `openapi.json` | OpenAPI 3.0 action group schema for all tools |",
        "| `cloudformation.yaml` | CloudFormation template to provision the Bedrock agent |",
        "| `README.md` | This file — setup and deploy instructions |",
        "",
    ]

    # Mention instruction-full.txt if it exists (user may have it)
    lines += [
        "> **Note:** If your agent's system prompt exceeds 4,000 characters, an",
        "> `instruction-full.txt` is also written with the complete untruncated text.",
        "",
    ]

    lines += [
        "## Prerequisites",
        "",
        "Before deploying, complete these steps:",
        "",
        "### 1. IAM Role",
        "",
        "Create an IAM role with the `AmazonBedrockAgentResourcePolicy` managed policy",
        "and `bedrock:InvokeModel` permissions. Pass its ARN as the `AgentRoleArn` parameter.",
        "",
        "```bash",
        "aws iam create-role --role-name agentshift-bedrock-role \\",
        "  --assume-role-policy-document '{",
        '    "Version": "2012-10-17",',
        '    "Statement": [{',
        '      "Effect": "Allow",',
        '      "Principal": {"Service": "bedrock.amazonaws.com"},',
        '      "Action": "sts:AssumeRole"',
        "    }]",
        "  }'",
        "```",
        "",
    ]

    if action_tools:
        lines += [
            "### 2. Lambda Functions (Action Groups)",
            "",
            "Each tool in your agent requires a Lambda function to handle invocations.",
            "The CloudFormation template references placeholder ARNs marked with `# TODO`.",
            "",
            "Create a Lambda function for each action group below:",
            "",
        ]
        for tool in action_tools:
            ag_name = f"{slug}-{_slug(tool.name)}"
            lines.append(f"- **{ag_name}** — implements `{tool.name}` ({tool.kind} tool)")
        lines.append("")
        lines += [
            "The Lambda handler contract (Bedrock → Lambda request/response format) is",
            "documented in the [Bedrock Developer Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-lambda.html).",
            "",
        ]

    if ir.knowledge:
        lines += [
            "### 3. Knowledge Bases",
            "",
            "Your agent uses knowledge sources. Each requires a Bedrock Knowledge Base",
            "backed by an S3 bucket and a vector store (OpenSearch Serverless or similar).",
            "",
            "Knowledge bases referenced in `cloudformation.yaml` (replace `kb-PLACEHOLDER-TODO`):",
            "",
        ]
        for ks in ir.knowledge:
            lines.append(f"- **{ks.name}** ({ks.kind}) — {ks.description or 'no description'}")
        lines += [
            "",
            "See the [Bedrock Knowledge Bases guide](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html) for setup instructions.",
            "",
        ]

    lines += [
        "## Deploy",
        "",
        "```bash",
        "aws cloudformation deploy \\",
        "  --template-file cloudformation.yaml \\",
        f"  --stack-name agentshift-{slug} \\",
        "  --parameter-overrides AgentRoleArn=<YOUR_ROLE_ARN> \\",
        "  --capabilities CAPABILITY_IAM",
        "```",
        "",
        "After deployment, retrieve the agent and alias IDs:",
        "",
        "```bash",
        f"aws cloudformation describe-stacks --stack-name agentshift-{slug} \\",
        "  --query 'Stacks[0].Outputs'",
        "```",
        "",
        "## Invoke the Agent",
        "",
        "```bash",
        "aws bedrock-agent-runtime invoke-agent \\",
        "  --agent-id <AgentId> \\",
        "  --agent-alias-id <AliasId> \\",
        "  --session-id session-$(date +%s) \\",
        "  --input-text 'Hello!'",
        "```",
        "",
        "## About",
        "",
        "This agent was automatically converted using AgentShift.",
        "",
        "- **Source format:** OpenClaw SKILL.md",
        "- **Target format:** AWS Bedrock Agent (CloudFormation)",
        "- **Converter:** [AgentShift](https://agentshift.sh)",
        "",
        "To convert other OpenClaw skills:",
        "```bash",
        "agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to bedrock --output /tmp/bedrock-output",
        "```",
    ]

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
