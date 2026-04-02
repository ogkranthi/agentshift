"""AWS Bedrock → IR parser.

Reads Bedrock agent artifacts from a directory and produces an AgentIR.

Supported input files (any combination; at least one of the primary inputs must exist):
  bedrock-agent.json   — AgentShift-generated Bedrock metadata blob
  cloudformation.yaml  — CloudFormation template (primary source for agent config)
  instruction.txt      — Plain-text instruction (emitted by AgentShift bedrock emitter)
  openapi.json         — Action-group OpenAPI schema (tools)
  guardrail-config.json — Bedrock guardrail topic/content filter config

Precedence (highest wins for each field):
  bedrock-agent.json > cloudformation.yaml > instruction.txt
  Tools come from openapi.json if present, otherwise cloudformation.yaml ActionGroups.
  Guardrails from guardrail-config.json, supplemented by heuristic scan of instruction.
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

# Marker inserted by the AgentShift Bedrock emitter when instruction was truncated
_TRUNCATION_NOTICE_RE = re.compile(
    r"\s*\[AGENTSHIFT:\s*Full instructions truncated[^\]]*\]\s*$",
    re.IGNORECASE | re.DOTALL,
)

# Instruction length limit for Bedrock
_MAX_INSTRUCTION_CHARS = 4000


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse(input_dir: Path) -> AgentIR:
    """Parse Bedrock agent artifacts from a directory into an AgentIR.

    Reads any combination of:
      - bedrock-agent.json   (AgentShift metadata blob — highest precedence)
      - cloudformation.yaml  (CFN template — primary config source)
      - instruction.txt      (plain-text instruction)
      - openapi.json         (action group OpenAPI → tools)
      - guardrail-config.json (Bedrock guardrail config → L3 + L1 guardrails)

    Raises:
        FileNotFoundError: if input_dir does not exist or no recognised files are found.
        ValueError: if parsing fails for an unexpected reason.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Bedrock input directory not found: {input_dir}")
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Expected a directory, got: {input_dir}")

    # Load available input files
    agent_json = _load_json(input_dir / "bedrock-agent.json")
    cfn_yaml = _load_yaml(input_dir / "cloudformation.yaml")
    instruction_txt = _load_text(input_dir / "instruction.txt")
    openapi_json = _load_json(input_dir / "openapi.json")
    guardrail_json = _load_json(input_dir / "guardrail-config.json")

    # At least one primary input must exist
    if agent_json is None and cfn_yaml is None and instruction_txt is None:
        raise FileNotFoundError(
            f"No recognised Bedrock artifact files found in {input_dir}. "
            "Expected at least one of: bedrock-agent.json, cloudformation.yaml, instruction.txt"
        )

    # --- Resolve core fields via precedence ---
    name, description, foundation_model, agent_id, alias_id = _resolve_identity(
        agent_json, cfn_yaml
    )
    instruction = _resolve_instruction(agent_json, cfn_yaml, instruction_txt)

    # Strip truncation notice if present
    instruction, _was_truncated = _strip_truncation_notice(instruction)

    # Build persona
    sections = extract_sections(instruction) if instruction else None
    persona = Persona(
        system_prompt=instruction or None,
        sections=sections if sections else None,
        language="en",
    )

    # --- Tools from OpenAPI ---
    tools = _extract_tools_from_openapi(openapi_json)
    if not tools and cfn_yaml:
        tools = _extract_tools_from_cfn(cfn_yaml)

    # --- Knowledge from CFN ---
    knowledge = _extract_knowledge_from_cfn(cfn_yaml)

    # --- Guardrails ---
    governance = _build_governance(guardrail_json, instruction)

    # --- Platform extensions ---
    bedrock_ext: dict[str, Any] = {}
    if agent_id:
        bedrock_ext["agent_id"] = agent_id
    if alias_id:
        bedrock_ext["alias_id"] = alias_id
    if foundation_model:
        bedrock_ext["foundation_model"] = foundation_model

    metadata = Metadata(
        source_platform="bedrock",
        platform_extensions={"bedrock": bedrock_ext} if bedrock_ext else {},
    )

    # Derive description if still empty
    if not description and instruction:
        first_sentence = re.split(r"[.!?\n]", instruction)[0].strip()
        description = first_sentence[:200]

    return AgentIR(
        name=name or "unnamed-bedrock-agent",
        description=description or f"Bedrock agent imported from {input_dir.name}",
        persona=persona,
        tools=tools,
        knowledge=knowledge,
        governance=governance,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------


def _resolve_identity(
    agent_json: dict | None,
    cfn_yaml: dict | None,
) -> tuple[str, str, str, str, str]:
    """Return (name, description, foundation_model, agent_id, alias_id)."""
    name = ""
    description = ""
    foundation_model = ""
    agent_id = ""
    alias_id = ""

    # From CloudFormation — extract Properties of the first AWS::Bedrock::Agent resource
    if cfn_yaml:
        resources = cfn_yaml.get("Resources", {})
        for _logical_id, res in resources.items():
            if res.get("Type") == "AWS::Bedrock::Agent":
                props = res.get("Properties", {})
                if not name:
                    raw_name = props.get("AgentName", "")
                    # Strip CFN intrinsics like !Sub "${AgentName}-${Environment}"
                    raw_name = _strip_cfn_intrinsic(raw_name)
                    name = slugify(raw_name) if raw_name else ""
                if not description:
                    description = _strip_cfn_intrinsic(props.get("Description", ""))
                if not foundation_model:
                    foundation_model = props.get("FoundationModel", "")
                break

        # Agent alias ID from outputs
        outputs = cfn_yaml.get("Outputs", {})
        for key, _val in outputs.items():
            if "AgentId" in key and not agent_id:
                # Usually a !GetAtt reference — can't resolve statically
                pass
            if "AliasId" in key and not alias_id:
                pass

    # From bedrock-agent.json — highest precedence
    if agent_json:
        if agent_json.get("agentName"):
            name = slugify(agent_json["agentName"])
        if agent_json.get("description"):
            description = agent_json["description"]
        if agent_json.get("foundationModel"):
            foundation_model = agent_json["foundationModel"]
        if agent_json.get("agentId"):
            agent_id = agent_json["agentId"]
        if agent_json.get("agentAliasId"):
            alias_id = agent_json["agentAliasId"]

    return name, description, foundation_model, agent_id, alias_id


def _strip_cfn_intrinsic(value: Any) -> str:
    """Best-effort extraction of a string value from a CFN intrinsic or plain string."""
    if isinstance(value, str):
        # Strip !Sub "${AgentName}-${Environment}" patterns
        # Remove ${...} placeholder tokens
        cleaned = re.sub(r"\$\{[^}]+\}", "", value).strip(" -_")
        return cleaned
    if isinstance(value, dict):
        # e.g. {"Sub": "${AgentName}-${Environment}"} — just return empty
        return ""
    return ""


# ---------------------------------------------------------------------------
# Instruction resolution
# ---------------------------------------------------------------------------


def _resolve_instruction(
    agent_json: dict | None,
    cfn_yaml: dict | None,
    instruction_txt: str | None,
) -> str:
    """Resolve the instruction text, with bedrock-agent.json taking precedence."""
    # Precedence: bedrock-agent.json > cloudformation.yaml > instruction.txt
    if agent_json and agent_json.get("instruction"):
        return agent_json["instruction"]

    # From CloudFormation Instruction property
    if cfn_yaml:
        resources = cfn_yaml.get("Resources", {})
        for _logical_id, res in resources.items():
            if res.get("Type") == "AWS::Bedrock::Agent":
                props = res.get("Properties", {})
                instruction = props.get("Instruction", "")
                if isinstance(instruction, str) and instruction.strip():
                    return instruction.strip()
                break

    # instruction.txt is the final fallback
    if instruction_txt:
        return instruction_txt.strip()

    return ""


def _strip_truncation_notice(instruction: str) -> tuple[str, bool]:
    """Remove the AgentShift truncation notice from the instruction.

    Returns (cleaned_instruction, was_truncated).
    """
    if not instruction:
        return instruction, False
    match = _TRUNCATION_NOTICE_RE.search(instruction)
    if match:
        cleaned = instruction[: match.start()].rstrip()
        return cleaned, True
    return instruction, False


# ---------------------------------------------------------------------------
# Tool extraction
# ---------------------------------------------------------------------------


def _extract_tools_from_openapi(openapi: dict | None) -> list[Tool]:
    """Extract IR tools from an OpenAPI 3.0 action-group schema."""
    if not openapi:
        return []

    tools: list[Tool] = []
    paths = openapi.get("paths", {})

    for path, path_item in paths.items():
        for _method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue

            op_id = operation.get("operationId", "")
            description = operation.get("description", "")
            is_stub = operation.get("x-agentshift-stub", False)

            # Derive name from operationId or path
            name = op_id or path.strip("/").replace("/", "_")
            if not name:
                continue

            # Infer kind from stub marker and naming conventions
            kind = _infer_tool_kind_from_operation(name, operation, is_stub)

            # Extract parameters schema from requestBody
            parameters = None
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                json_schema = content.get("application/json", {}).get("schema")
                if json_schema:
                    parameters = json_schema

            # Auth — look for security definitions (basic inference)
            auth = _infer_auth_from_openapi(openapi, operation)

            tools.append(
                Tool(
                    name=name,
                    description=description,
                    kind=kind,
                    parameters=parameters,
                    auth=auth if auth and auth.type != "none" else None,
                )
            )

    return tools


def _infer_tool_kind_from_operation(name: str, operation: dict, is_stub: bool) -> str:
    """Infer IR tool kind from an OpenAPI operation."""
    if is_stub:
        # Stub tools: check naming convention
        if name.endswith("_action"):
            return "mcp"
        if name.endswith("_run"):
            return "shell"
    # Default for Bedrock action group operations
    return "function"


def _infer_auth_from_openapi(openapi: dict, operation: dict) -> ToolAuth:
    """Best-effort auth inference from OpenAPI security schemes."""
    security_schemes = openapi.get("components", {}).get("securitySchemes", {})
    security_refs = operation.get("security", openapi.get("security", []))

    for sec_req in security_refs:
        for scheme_name in sec_req:
            scheme = security_schemes.get(scheme_name, {})
            scheme_type = scheme.get("type", "").lower()
            if scheme_type == "apikey":
                env_var = scheme.get("name", scheme_name).upper().replace("-", "_")
                return ToolAuth(type="api_key", env_var=env_var)
            if scheme_type == "http":
                scheme_scheme = scheme.get("scheme", "").lower()
                if scheme_scheme == "bearer":
                    return ToolAuth(type="bearer")
                if scheme_scheme == "basic":
                    return ToolAuth(type="basic")
            if scheme_type == "oauth2":
                scopes = list(
                    scheme.get("flows", {}).get("clientCredentials", {}).get("scopes", {}).keys()
                )
                return ToolAuth(type="oauth2", scopes=scopes)

    return ToolAuth(type="none")


def _extract_tools_from_cfn(cfn_yaml: dict) -> list[Tool]:
    """Extract tools from CloudFormation ActionGroups as a fallback."""
    tools: list[Tool] = []
    resources = cfn_yaml.get("Resources", {})

    for _logical_id, res in resources.items():
        if res.get("Type") != "AWS::Bedrock::Agent":
            continue
        props = res.get("Properties", {})
        action_groups = props.get("ActionGroups", [])

        for ag in action_groups:
            ag_name = ag.get("ActionGroupName", "")
            if not ag_name:
                continue

            description = ag.get("Description", f"Action group: {ag_name}")
            if isinstance(description, dict):
                description = str(description)

            # Try to extract tools from inline ApiSchema Payload
            api_schema = ag.get("ApiSchema", {})
            payload = api_schema.get("Payload")
            if payload:
                try:
                    schema = json.loads(payload) if isinstance(payload, str) else payload
                    sub_tools = _extract_tools_from_openapi(schema)
                    tools.extend(sub_tools)
                    continue
                except (json.JSONDecodeError, TypeError):
                    pass

            # Fallback: one tool per action group
            name = slugify(ag_name)
            tools.append(
                Tool(
                    name=name,
                    description=str(description),
                    kind="function",
                )
            )
        break  # Only process the first Bedrock::Agent resource

    return tools


# ---------------------------------------------------------------------------
# Knowledge extraction
# ---------------------------------------------------------------------------


def _extract_knowledge_from_cfn(cfn_yaml: dict | None) -> list[KnowledgeSource]:
    """Extract knowledge sources from CloudFormation KnowledgeBases references."""
    if not cfn_yaml:
        return []

    knowledge: list[KnowledgeSource] = []
    resources = cfn_yaml.get("Resources", {})

    # Look for AWS::Bedrock::KnowledgeBase resources
    for logical_id, res in resources.items():
        if res.get("Type") != "AWS::Bedrock::KnowledgeBase":
            continue
        props = res.get("Properties", {})
        name = slugify(props.get("Name", logical_id))
        description = props.get("Description", f"Bedrock knowledge base: {name}")
        if isinstance(description, dict):
            description = str(description)

        # Infer storage kind
        storage_type = props.get("StorageConfiguration", {}).get("Type", "").lower()
        kind: str
        if "opensearch" in storage_type or "vector" in storage_type:
            kind = "vector_store"
        elif "s3" in storage_type:
            kind = "s3"
        else:
            kind = "vector_store"

        knowledge.append(
            KnowledgeSource(
                name=name,
                kind=kind,  # type: ignore[arg-type]
                description=str(description),
                load_mode="indexed",
                format="unknown",
            )
        )

    # Also look for KnowledgeBases references in the agent itself (they have IDs)
    for _logical_id, res in resources.items():
        if res.get("Type") != "AWS::Bedrock::Agent":
            continue
        props = res.get("Properties", {})
        for kb_ref in props.get("KnowledgeBases", []):
            kb_id = kb_ref.get("KnowledgeBaseId", "")
            if isinstance(kb_id, str) and not kb_id.startswith("kb-PLACEHOLDER"):
                kb_name = slugify(kb_id)
                desc = kb_ref.get("Description", f"Knowledge base: {kb_id}")
                if not any(k.name == kb_name for k in knowledge):
                    knowledge.append(
                        KnowledgeSource(
                            name=kb_name,
                            kind="vector_store",
                            description=str(desc),
                            load_mode="indexed",
                            format="unknown",
                        )
                    )
        break

    return knowledge


# ---------------------------------------------------------------------------
# Guardrail / governance building
# ---------------------------------------------------------------------------


def _build_governance(
    guardrail_json: dict | None,
    instruction: str,
) -> Governance:
    """Build Governance from guardrail-config.json and heuristic scan of instruction."""
    guardrails: list[Guardrail] = []

    # L1: heuristic scan of the instruction text
    if instruction:
        guardrails.extend(extract_guardrails_from_text(instruction, id_prefix="G"))

    # L1: from guardrail-config.json topic policy
    if guardrail_json:
        topic_policy = guardrail_json.get("topicPolicyConfig", {})
        topics = topic_policy.get("topicsConfig", [])
        existing_texts = {g.text.lower() for g in guardrails}

        for topic in topics:
            definition = topic.get("definition", "").strip()
            if not definition:
                definition = topic.get("name", "").replace("-", " ")
            if definition.lower() in existing_texts:
                continue
            idx = len(guardrails) + 1
            from agentshift.parsers.utils import (
                infer_guardrail_category,
                infer_guardrail_severity,
            )

            guardrails.append(
                Guardrail(
                    id=f"G{idx:03d}",
                    text=definition,
                    category=infer_guardrail_category(definition),
                    severity=infer_guardrail_severity(definition),
                )
            )

    return Governance(guardrails=guardrails)


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None if absent or invalid."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _load_yaml(path: Path) -> dict | None:
    """Load a YAML file, returning None if absent or invalid."""
    if not path.exists():
        return None
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def _load_text(path: Path) -> str | None:
    """Load a plain-text file, returning None if absent."""
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
