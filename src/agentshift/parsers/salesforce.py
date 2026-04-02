"""Salesforce Agentforce → IR parser.

Reads Salesforce Agentforce agent artifacts and produces an AgentIR.

Supported input formats:
  1. Directory containing:
     - *.bot-meta.xml       — Bot metadata (label, description, systemMessage)
     - *.genAiPlanner-meta.xml — Planner metadata (topics, actions, instructions)
  2. JSON file matching the AgentCreateResponse format from the Salesforce API.

IR mapping:
  - name:        from bot label or agentDefinition (slugified)
  - description: from bot/planner description or agentDescription
  - system_prompt: concatenation of all topic instructions with topic headers
  - tools[]:    from plannerActions or agentDefinition actions
  - knowledge[]: from contextVariables (kind="database")
  - metadata.source_platform: "salesforce"
  - metadata.platform_extensions.salesforce: agentType, plannerType, etc.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from agentshift.ir import (
    AgentIR,
    Governance,
    KnowledgeSource,
    Metadata,
    Persona,
    Tool,
)
from agentshift.parsers.utils import (
    extract_guardrails_from_text,
    slugify,
)

# Salesforce metadata XML namespace
_SF_NS = "http://soap.sforce.com/2006/04/metadata"
_NS = {"sf": _SF_NS}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_agent_dir(path: Path) -> AgentIR:
    """Parse Salesforce Agentforce artifacts into an AgentIR.

    Accepts either:
      - A directory containing .bot-meta.xml (and optionally .genAiPlanner-meta.xml)
      - A JSON file matching the AgentCreateResponse format

    Raises:
        FileNotFoundError: if path does not exist or no recognized files found.
        ValueError: if files cannot be parsed.
    """
    if not path.exists():
        raise FileNotFoundError(f"Salesforce input path not found: {path}")

    # Case 1: JSON file
    if path.is_file() and path.suffix == ".json":
        return _parse_json_file(path)

    # Case 2: Directory — look for JSON first, then XML
    if path.is_dir():
        # Check for JSON AgentCreateResponse
        json_files = list(path.glob("*.json"))
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "agentDefinition" in data:
                    return _parse_agent_create_response(data, source_file=str(jf))
            except (json.JSONDecodeError, OSError):
                continue

        # Look for XML files
        bot_files = list(path.glob("*.bot-meta.xml"))
        planner_files = list(path.glob("*.genAiPlanner-meta.xml"))

        if not bot_files and not planner_files:
            raise FileNotFoundError(
                f"No Salesforce Agentforce artifacts found in {path}. "
                "Expected .bot-meta.xml, .genAiPlanner-meta.xml, or AgentCreateResponse JSON."
            )

        return _parse_xml_directory(path, bot_files, planner_files)

    raise FileNotFoundError(f"Expected a directory or JSON file, got: {path}")


# ---------------------------------------------------------------------------
# JSON format (AgentCreateResponse)
# ---------------------------------------------------------------------------


def _parse_json_file(path: Path) -> AgentIR:
    """Parse a single JSON file as AgentCreateResponse."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e

    if not isinstance(data, dict) or "agentDefinition" not in data:
        raise ValueError(
            f"JSON file {path} does not match AgentCreateResponse format "
            "(missing 'agentDefinition' key)."
        )

    return _parse_agent_create_response(data, source_file=str(path))


def _parse_agent_create_response(data: dict, source_file: str = "") -> AgentIR:
    """Parse AgentCreateResponse JSON into AgentIR."""
    agent_def = data.get("agentDefinition", {})

    # Identity
    description = agent_def.get("agentDescription", "")
    # Derive name from description or source file
    name = slugify(description[:60]) if description else "salesforce-agent"

    # Topics → system_prompt + tools
    topics = agent_def.get("topics", [])
    system_prompt = _build_system_prompt_from_topics(topics)

    tools: list[Tool] = []
    for topic in topics:
        topic_actions = topic.get("actions", [])
        for action in topic_actions:
            tool = _parse_json_action(action)
            if tool:
                tools.append(tool)

    # Sample utterances → personality_notes
    sample_utterances = agent_def.get("sampleUtterances", [])
    personality_notes = None
    if sample_utterances:
        personality_notes = "Sample utterances:\n" + "\n".join(f"- {u}" for u in sample_utterances)

    # Guardrails from topic instructions
    guardrails = extract_guardrails_from_text(system_prompt) if system_prompt else []

    # Platform extensions
    extensions: dict[str, Any] = {}
    if sample_utterances:
        extensions["sample_utterances"] = sample_utterances

    metadata = Metadata(
        source_platform="salesforce",
        source_file=source_file or None,
        platform_extensions={"salesforce": extensions} if extensions else {},
    )

    return AgentIR(
        name=name,
        description=description or "Salesforce Agentforce agent",
        persona=Persona(
            system_prompt=system_prompt or None,
            personality_notes=personality_notes,
        ),
        tools=tools,
        governance=Governance(guardrails=guardrails),
        metadata=metadata,
    )


def _build_system_prompt_from_topics(topics: list[dict]) -> str:
    """Build a structured system_prompt from Agentforce topics."""
    sections: list[str] = []

    for topic in topics:
        topic_name = topic.get("topic", "")
        scope = topic.get("scope", "")
        instructions = topic.get("instructions", [])

        if not topic_name:
            continue

        parts: list[str] = [f"## {topic_name}"]
        if scope:
            parts.append(f"Scope: {scope}")
        parts.append("")  # blank line

        if isinstance(instructions, list):
            for instr in instructions:
                parts.append(f"- {instr}")
        elif isinstance(instructions, str):
            parts.append(instructions)

        sections.append("\n".join(parts))

    return "\n\n".join(sections)


def _parse_json_action(action: dict) -> Tool | None:
    """Parse a JSON action definition into a Tool."""
    action_name = action.get("actionName", "")
    if not action_name:
        return None

    description = action.get("actionDescription", "")
    example_output = action.get("exampleOutput", "")

    # Build parameters from inputs
    parameters: dict[str, Any] | None = None
    inputs = action.get("inputs", [])
    if inputs:
        props: dict[str, Any] = {}
        required: list[str] = []
        for inp in inputs:
            inp_name = inp.get("inputName", "")
            if not inp_name:
                continue
            inp_type = _sf_type_to_json_type(inp.get("inputDataType", "String"))
            inp_desc = inp.get("inputDescription", "")
            props[inp_name] = {"type": inp_type}
            if inp_desc:
                props[inp_name]["description"] = inp_desc
            required.append(inp_name)
        parameters = {
            "type": "object",
            "properties": props,
            "required": required,
        }

    full_desc = description
    if example_output:
        full_desc = (
            f"{description}\n\nExample output: {example_output}"
            if description
            else f"Example output: {example_output}"
        )

    return Tool(
        name=_camel_to_kebab(action_name),
        description=full_desc or f"Salesforce action: {action_name}",
        kind="function",
        parameters=parameters,
    )


# ---------------------------------------------------------------------------
# XML format (Bot + GenAiPlanner metadata)
# ---------------------------------------------------------------------------


def _parse_xml_directory(
    input_dir: Path,
    bot_files: list[Path],
    planner_files: list[Path],
) -> AgentIR:
    """Parse XML metadata files from a Salesforce project directory."""
    # Parse bot metadata
    bot_data: dict[str, Any] = {}
    if bot_files:
        bot_data = _parse_bot_xml(bot_files[0])

    # Parse planner metadata
    planner_data: dict[str, Any] = {}
    if planner_files:
        planner_data = _parse_planner_xml(planner_files[0])

    # Identity
    name = slugify(
        bot_data.get("label", "") or planner_data.get("masterLabel", "") or input_dir.name
    )
    description = bot_data.get("description", "") or planner_data.get("description", "")

    # System prompt
    system_message = bot_data.get("system_message", "")
    planner_topics = planner_data.get("topics", [])

    topic_prompt = _build_system_prompt_from_planner_topics(planner_topics)

    # Combine: system message first, then topic instructions
    prompt_parts: list[str] = []
    if system_message:
        prompt_parts.append(system_message)
    if topic_prompt:
        prompt_parts.append(topic_prompt)
    system_prompt = "\n\n".join(prompt_parts)

    # Tools from planner actions
    tools: list[Tool] = []
    for topic in planner_topics:
        for action in topic.get("actions", []):
            action_name = action.get("action", "")
            action_type = action.get("actionType", "")
            if action_name:
                tools.append(
                    Tool(
                        name=_camel_to_kebab(action_name),
                        description=f"Salesforce {action_type or 'action'}: {action_name}",
                        kind="function",
                    )
                )

    # Knowledge from contextVariables
    knowledge: list[KnowledgeSource] = []
    for ctx_var in bot_data.get("context_variables", []):
        var_name = ctx_var.get("name", "")
        var_type = ctx_var.get("dataType", "")
        if var_name:
            knowledge.append(
                KnowledgeSource(
                    name=slugify(var_name),
                    kind="database",
                    description=f"Salesforce context variable: {var_name} ({var_type})",
                    format="unknown",
                    load_mode="on_demand",
                )
            )

    # Guardrails
    guardrails = extract_guardrails_from_text(system_prompt) if system_prompt else []

    # Platform extensions
    extensions: dict[str, Any] = {}
    if bot_data.get("agent_type"):
        extensions["agentType"] = bot_data["agent_type"]
    if bot_data.get("type"):
        extensions["botType"] = bot_data["type"]
    if planner_data.get("planner_type"):
        extensions["plannerType"] = planner_data["planner_type"]

    metadata = Metadata(
        source_platform="salesforce",
        source_file=(
            str(bot_files[0]) if bot_files else str(planner_files[0]) if planner_files else None
        ),
        platform_extensions={"salesforce": extensions} if extensions else {},
    )

    return AgentIR(
        name=name,
        description=description or f"Salesforce Agentforce agent: {name}",
        persona=Persona(system_prompt=system_prompt or None),
        tools=tools,
        knowledge=knowledge,
        governance=Governance(guardrails=guardrails),
        metadata=metadata,
    )


def _parse_bot_xml(path: Path) -> dict[str, Any]:
    """Parse a .bot-meta.xml file and return structured data."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in {path}: {e}") from e

    root = tree.getroot()
    result: dict[str, Any] = {}

    # Label
    label_el = root.find("sf:label", _NS)
    if label_el is not None and label_el.text:
        result["label"] = label_el.text.strip()

    # Also check botMlDomain/label as fallback
    ml_label = root.find("sf:botMlDomain/sf:label", _NS)
    if ml_label is not None and ml_label.text and "label" not in result:
        result["label"] = ml_label.text.strip()

    # Description
    desc_el = root.find("sf:description", _NS)
    if desc_el is not None and desc_el.text:
        result["description"] = desc_el.text.strip()

    # Agent type
    agent_type_el = root.find("sf:agentType", _NS)
    if agent_type_el is not None and agent_type_el.text:
        result["agent_type"] = agent_type_el.text.strip()

    # Bot type
    type_el = root.find("sf:type", _NS)
    if type_el is not None and type_el.text:
        result["type"] = type_el.text.strip()

    # System message from botDialogs
    system_msg = _extract_system_message(root)
    if system_msg:
        result["system_message"] = system_msg

    # Context variables
    ctx_vars = _extract_context_variables(root)
    if ctx_vars:
        result["context_variables"] = ctx_vars

    return result


def _extract_system_message(root: ET.Element) -> str:
    """Extract system message from Bot → botVersions → botDialogs → botSteps."""
    for step in root.iter(f"{{{_SF_NS}}}botSteps"):
        step_type = step.find(f"{{{_SF_NS}}}stepType")
        sys_msg = step.find(f"{{{_SF_NS}}}systemMessage")
        if (
            step_type is not None
            and step_type.text == "SystemMessage"
            and sys_msg is not None
            and sys_msg.text
        ):
            return sys_msg.text.strip()
    return ""


def _extract_context_variables(root: ET.Element) -> list[dict[str, str]]:
    """Extract context variables from Bot metadata."""
    variables: list[dict[str, str]] = []
    for ctx_var in root.iter(f"{{{_SF_NS}}}contextVariables"):
        name_el = ctx_var.find(f"{{{_SF_NS}}}contextVariableName")
        type_el = ctx_var.find(f"{{{_SF_NS}}}dataType")
        if name_el is not None and name_el.text:
            variables.append(
                {
                    "name": name_el.text.strip(),
                    "dataType": (
                        type_el.text.strip() if type_el is not None and type_el.text else "Text"
                    ),
                }
            )
    return variables


def _parse_planner_xml(path: Path) -> dict[str, Any]:
    """Parse a .genAiPlanner-meta.xml file and return structured data."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in {path}: {e}") from e

    root = tree.getroot()
    result: dict[str, Any] = {}

    # Planner type
    planner_type_el = root.find("sf:plannerType", _NS)
    if planner_type_el is not None and planner_type_el.text:
        result["planner_type"] = planner_type_el.text.strip()

    # Master label
    label_el = root.find("sf:masterLabel", _NS)
    if label_el is not None and label_el.text:
        result["masterLabel"] = label_el.text.strip()

    # Description
    desc_el = root.find("sf:description", _NS)
    if desc_el is not None and desc_el.text:
        result["description"] = desc_el.text.strip()

    # Topics
    topics: list[dict[str, Any]] = []
    for topic_el in root.findall("sf:plannerTopics/sf:plannerTopic", _NS):
        topic = _parse_planner_topic(topic_el)
        if topic:
            topics.append(topic)
    result["topics"] = topics

    return result


def _parse_planner_topic(topic_el: ET.Element) -> dict[str, Any]:
    """Parse a single plannerTopic element."""
    topic: dict[str, Any] = {}

    label_el = topic_el.find(f"{{{_SF_NS}}}masterLabel")
    if label_el is not None and label_el.text:
        topic["masterLabel"] = label_el.text.strip()

    desc_el = topic_el.find(f"{{{_SF_NS}}}description")
    if desc_el is not None and desc_el.text:
        topic["description"] = desc_el.text.strip()

    scope_el = topic_el.find(f"{{{_SF_NS}}}scope")
    if scope_el is not None and scope_el.text:
        topic["scope"] = scope_el.text.strip()

    instr_el = topic_el.find(f"{{{_SF_NS}}}instructions")
    if instr_el is not None and instr_el.text:
        topic["instructions"] = instr_el.text.strip()

    # Actions
    actions: list[dict[str, str]] = []
    for action_el in topic_el.findall(f"{{{_SF_NS}}}plannerActions/{{{_SF_NS}}}plannerAction"):
        action_name_el = action_el.find(f"{{{_SF_NS}}}action")
        action_type_el = action_el.find(f"{{{_SF_NS}}}actionType")
        if action_name_el is not None and action_name_el.text:
            actions.append(
                {
                    "action": action_name_el.text.strip(),
                    "actionType": (
                        action_type_el.text.strip()
                        if action_type_el is not None and action_type_el.text
                        else ""
                    ),
                }
            )
    topic["actions"] = actions

    return topic


def _build_system_prompt_from_planner_topics(topics: list[dict]) -> str:
    """Build structured system_prompt from planner topics."""
    sections: list[str] = []

    for topic in topics:
        topic_name = topic.get("masterLabel", "")
        if not topic_name:
            continue

        parts: list[str] = [f"## {topic_name}"]

        description = topic.get("description", "")
        if description:
            parts.append(description)

        scope = topic.get("scope", "")
        if scope:
            parts.append(f"Scope: {scope}")

        parts.append("")  # blank line

        instructions = topic.get("instructions", "")
        if instructions:
            # Split instructions on sentence boundaries for bullet formatting
            for line in instructions.split(". "):
                line = line.strip().rstrip(".")
                if line:
                    parts.append(f"- {line}")

        sections.append("\n".join(parts))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _camel_to_kebab(name: str) -> str:
    """Convert CamelCase or camelCase to kebab-case.

    Examples:
        'GetLeadScore' → 'get-lead-score'
        'DraftEmail' → 'draft-email'
    """
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s)
    return s.lower()


def _sf_type_to_json_type(sf_type: str) -> str:
    """Map Salesforce data types to JSON Schema types."""
    mapping = {
        "String": "string",
        "Text": "string",
        "Integer": "integer",
        "Number": "number",
        "Boolean": "boolean",
        "Date": "string",
        "DateTime": "string",
        "Id": "string",
    }
    return mapping.get(sf_type, "string")
