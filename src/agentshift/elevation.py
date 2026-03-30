"""Permission elevation engine — promotes L2/L3 governance to L1 instructions.

When a target platform lacks native support for a governance artifact
(e.g., Copilot has no deny-list), the artifact is "elevated" to a prompt-level
instruction (L1) in the emitted output.

This module tracks what was elevated and why, enabling governance audit reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agentshift.ir import AgentIR, Governance, Guardrail, PlatformAnnotation, ToolPermission


@dataclass
class ElevatedArtifact:
    """Record of a governance artifact that was elevated from L2/L3 to L1."""

    source_layer: str  # "L2" or "L3"
    artifact_id: str
    artifact_type: str  # e.g. "deny_pattern", "rate_limit", "disabled_tool", "content_filter"
    original_text: str
    elevated_instruction: str
    target_platform: str
    reason: str


@dataclass
class ElevationResult:
    """Result of the elevation process for a single target platform."""

    target: str
    elevated_artifacts: list[ElevatedArtifact] = field(default_factory=list)
    l1_preserved: list[Guardrail] = field(default_factory=list)
    l2_preserved: list[ToolPermission] = field(default_factory=list)
    l2_elevated: list[ToolPermission] = field(default_factory=list)
    l3_preserved: list[PlatformAnnotation] = field(default_factory=list)
    l3_elevated: list[PlatformAnnotation] = field(default_factory=list)
    l3_dropped: list[PlatformAnnotation] = field(default_factory=list)
    extra_instructions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Platform capability matrix — what each platform supports natively
# ---------------------------------------------------------------------------

PLATFORM_L2_CAPABILITIES: dict[str, set[str]] = {
    "claude-code": {"allow_list", "deny_list", "deny_patterns", "disabled_tool"},
    "copilot": set(),  # No native permission model
    "bedrock": {"disabled_tool"},
    "vertex": {"disabled_tool"},
    "m365": set(),
    "langgraph": {"disabled_tool"},
}

PLATFORM_L3_CAPABILITIES: dict[str, set[str]] = {
    "claude-code": set(),  # No native content filters
    "copilot": set(),
    "bedrock": {"content_filter", "pii_detection", "denied_topics", "grounding_check"},
    "vertex": {"content_filter", "pii_detection"},
    "m365": set(),
    "langgraph": set(),
}


def elevate_governance(ir: AgentIR, target: str) -> ElevationResult:
    """Analyze governance and determine what gets preserved vs elevated for a target platform.

    Returns an ElevationResult with:
    - l1_preserved: All L1 guardrails (always preserved as prompt text)
    - l2_preserved/l2_elevated: L2 permissions that map vs need elevation
    - l3_preserved/l3_elevated/l3_dropped: L3 annotations fate
    - extra_instructions: New L1 instructions generated from elevated L2/L3
    - elevated_artifacts: Full audit trail
    """
    gov = ir.governance
    result = ElevationResult(target=target)

    # L1 guardrails — always preserved (they're already prompt-level)
    result.l1_preserved = list(gov.guardrails)

    # L2 tool permissions
    l2_caps = PLATFORM_L2_CAPABILITIES.get(target, set())
    for perm in gov.tool_permissions:
        elevated = False
        artifacts: list[ElevatedArtifact] = []

        # Disabled tool
        if not perm.enabled:
            if "disabled_tool" in l2_caps:
                pass  # Platform can express this natively
            else:
                instruction = f"Do NOT use the {perm.tool_name} tool. It is disabled."
                artifacts.append(ElevatedArtifact(
                    source_layer="L2",
                    artifact_id=f"L2-{perm.tool_name}-disabled",
                    artifact_type="disabled_tool",
                    original_text=f"{perm.tool_name}: DISABLED",
                    elevated_instruction=instruction,
                    target_platform=target,
                    reason=f"{target} has no native tool disable mechanism",
                ))
                result.extra_instructions.append(instruction)
                elevated = True

        # Deny patterns
        if perm.deny_patterns:
            if "deny_patterns" in l2_caps:
                pass  # Platform supports deny patterns
            else:
                for pattern in perm.deny_patterns:
                    instruction = (
                        f"When using {perm.tool_name}, NEVER access paths matching: {pattern}"
                    )
                    artifacts.append(ElevatedArtifact(
                        source_layer="L2",
                        artifact_id=f"L2-{perm.tool_name}-deny-{pattern}",
                        artifact_type="deny_pattern",
                        original_text=f"{perm.tool_name} deny: {pattern}",
                        elevated_instruction=instruction,
                        target_platform=target,
                        reason=f"{target} has no deny-pattern support",
                    ))
                    result.extra_instructions.append(instruction)
                    elevated = True

        # Read-only access
        if perm.access == "read-only" and perm.enabled:
            if "deny_list" in l2_caps:
                pass  # Can express as deny write
            else:
                instruction = (
                    f"The {perm.tool_name} tool is READ-ONLY. "
                    f"Do NOT use it to write, modify, or delete any data."
                )
                artifacts.append(ElevatedArtifact(
                    source_layer="L2",
                    artifact_id=f"L2-{perm.tool_name}-readonly",
                    artifact_type="access_restriction",
                    original_text=f"{perm.tool_name}: read-only",
                    elevated_instruction=instruction,
                    target_platform=target,
                    reason=f"{target} cannot enforce read-only access natively",
                ))
                result.extra_instructions.append(instruction)
                elevated = True

        # Rate limits
        if perm.rate_limit:
            instruction = (
                f"Rate limit for {perm.tool_name}: do not exceed {perm.rate_limit}."
            )
            artifacts.append(ElevatedArtifact(
                source_layer="L2",
                artifact_id=f"L2-{perm.tool_name}-ratelimit",
                artifact_type="rate_limit",
                original_text=f"{perm.tool_name} rate_limit: {perm.rate_limit}",
                elevated_instruction=instruction,
                target_platform=target,
                reason="No platform supports native rate limiting for tool calls",
            ))
            result.extra_instructions.append(instruction)
            elevated = True

        # Max value constraints
        if perm.max_value:
            instruction = (
                f"Maximum value constraint for {perm.tool_name}: {perm.max_value}."
            )
            artifacts.append(ElevatedArtifact(
                source_layer="L2",
                artifact_id=f"L2-{perm.tool_name}-maxvalue",
                artifact_type="max_value",
                original_text=f"{perm.tool_name} max_value: {perm.max_value}",
                elevated_instruction=instruction,
                target_platform=target,
                reason="No platform supports native max-value constraints for tools",
            ))
            result.extra_instructions.append(instruction)
            elevated = True

        # Allow patterns (directory restrictions)
        if perm.allow_patterns:
            if "allow_list" not in l2_caps:
                for pattern in perm.allow_patterns:
                    instruction = (
                        f"The {perm.tool_name} tool may ONLY be used for paths matching: {pattern}"
                    )
                    artifacts.append(ElevatedArtifact(
                        source_layer="L2",
                        artifact_id=f"L2-{perm.tool_name}-allow-{pattern}",
                        artifact_type="allow_pattern",
                        original_text=f"{perm.tool_name} allow: {pattern}",
                        elevated_instruction=instruction,
                        target_platform=target,
                        reason=f"{target} has no allow-pattern support",
                    ))
                    result.extra_instructions.append(instruction)
                    elevated = True

        if elevated:
            result.l2_elevated.append(perm)
            result.elevated_artifacts.extend(artifacts)
        else:
            result.l2_preserved.append(perm)

    # L3 platform annotations
    l3_caps = PLATFORM_L3_CAPABILITIES.get(target, set())
    for ann in gov.platform_annotations:
        if ann.kind in l3_caps:
            result.l3_preserved.append(ann)
        else:
            # Try to elevate to L1
            instruction = _elevate_l3_annotation(ann)
            if instruction:
                result.l3_elevated.append(ann)
                result.extra_instructions.append(instruction)
                result.elevated_artifacts.append(ElevatedArtifact(
                    source_layer="L3",
                    artifact_id=ann.id,
                    artifact_type=ann.kind,
                    original_text=ann.description,
                    elevated_instruction=instruction,
                    target_platform=target,
                    reason=f"{target} does not support {ann.kind} natively",
                ))
            else:
                result.l3_dropped.append(ann)

    return result


def _elevate_l3_annotation(ann: PlatformAnnotation) -> str | None:
    """Convert a L3 annotation to a L1 instruction string, or None if not possible."""
    if ann.kind == "content_filter":
        return f"CONTENT POLICY: {ann.description}"
    if ann.kind == "pii_detection":
        return f"PII PROTECTION: {ann.description}"
    if ann.kind == "denied_topics":
        return f"DENIED TOPIC: {ann.description}"
    if ann.kind == "grounding_check":
        return f"GROUNDING REQUIREMENT: {ann.description}"
    return None
