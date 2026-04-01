"""AgentShift platform constraints — instruction length limits and validation."""

from __future__ import annotations

import warnings

from agentshift.ir import AgentIR

# ---------------------------------------------------------------------------
# Platform instruction length limits
# ---------------------------------------------------------------------------

INSTRUCTION_LIMIT_BEDROCK: int = 4000
INSTRUCTION_LIMIT_VERTEX: int = 8000
INSTRUCTION_LIMIT_COPILOT: int = 8000

INSTRUCTION_LIMITS: dict[str, int] = {
    "bedrock": INSTRUCTION_LIMIT_BEDROCK,
    "vertex-ai": INSTRUCTION_LIMIT_VERTEX,
    "copilot": INSTRUCTION_LIMIT_COPILOT,
    "claude-code": 100_000,  # no practical limit
    "openclaw": 100_000,
}

# Description length limits per platform
DESCRIPTION_LIMITS: dict[str, int] = {
    "bedrock": 200,
    "vertex-ai": 500,
    "copilot": 8000,
    "claude-code": 100_000,
    "openclaw": 100_000,
}


# ---------------------------------------------------------------------------
# Constraint result types
# ---------------------------------------------------------------------------


class ConstraintWarning:
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message

    def __repr__(self) -> str:
        return f"ConstraintWarning(field={self.field!r}, message={self.message!r})"


class ConstraintError:
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message

    def __repr__(self) -> str:
        return f"ConstraintError(field={self.field!r}, message={self.message!r})"


class ConstraintResult:
    def __init__(
        self,
        warnings: list[ConstraintWarning] | None = None,
        errors: list[ConstraintError] | None = None,
    ) -> None:
        self.warnings: list[ConstraintWarning] = warnings or []
        self.errors: list[ConstraintError] = errors or []

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def __repr__(self) -> str:
        return f"ConstraintResult(warnings={self.warnings!r}, errors={self.errors!r})"


# ---------------------------------------------------------------------------
# Core check function
# ---------------------------------------------------------------------------


def check_constraints(ir_agent: AgentIR, platform: str) -> ConstraintResult:
    """Check IR agent against platform constraints.

    Returns a ConstraintResult with any warnings or errors found.
    Does not modify the IR.
    """
    result = ConstraintResult()
    platform = platform.lower()

    # --- Instruction length ---
    instr_limit = INSTRUCTION_LIMITS.get(platform, 100_000)
    if ir_agent.persona and ir_agent.persona.system_prompt:
        prompt = ir_agent.persona.system_prompt
        if len(prompt) > instr_limit:
            result.warnings.append(
                ConstraintWarning(
                    field="persona.system_prompt",
                    message=(
                        f"Instruction length {len(prompt)} exceeds {platform} limit of "
                        f"{instr_limit} chars. Will be truncated."
                    ),
                )
            )

    # --- Description length ---
    desc_limit = DESCRIPTION_LIMITS.get(platform, 100_000)
    if ir_agent.description and len(ir_agent.description) > desc_limit:
        result.warnings.append(
            ConstraintWarning(
                field="description",
                message=(
                    f"Description length {len(ir_agent.description)} exceeds {platform} "
                    f"limit of {desc_limit} chars. Will be truncated."
                ),
            )
        )

    # --- Platform-specific tool checks ---
    if platform == "bedrock":
        _check_bedrock_constraints(ir_agent, result)
    elif platform == "vertex-ai":
        _check_vertex_constraints(ir_agent, result)

    return result


def _check_bedrock_constraints(ir_agent: AgentIR, result: ConstraintResult) -> None:
    """Bedrock-specific constraint checks."""
    # Action group limits: max 11 action groups, max 11 actions per group
    func_tools = [t for t in ir_agent.tools if t.kind in ("function", "openapi", "mcp")]
    if len(func_tools) > 11:
        result.warnings.append(
            ConstraintWarning(
                field="tools",
                message=(
                    f"Bedrock allows max 11 actions per action group; "
                    f"{len(func_tools)} tools found. Consider splitting into multiple action groups."
                ),
            )
        )

    # Unsupported tool kinds
    for tool in ir_agent.tools:
        if tool.kind in ("mcp", "shell", "builtin"):
            result.warnings.append(
                ConstraintWarning(
                    field=f"tools[{tool.name}]",
                    message=(
                        f"Tool '{tool.name}' (kind={tool.kind}) has no native Bedrock equivalent. "
                        f"A TODO stub will be emitted."
                    ),
                )
            )


def _check_vertex_constraints(ir_agent: AgentIR, result: ConstraintResult) -> None:
    """Vertex AI-specific constraint checks."""
    if len(ir_agent.tools) > 128:
        result.warnings.append(
            ConstraintWarning(
                field="tools",
                message=(
                    f"Vertex AI allows max 128 tools; {len(ir_agent.tools)} tools found."
                ),
            )
        )

    for tool in ir_agent.tools:
        if tool.kind in ("mcp", "shell", "builtin"):
            result.warnings.append(
                ConstraintWarning(
                    field=f"tools[{tool.name}]",
                    message=(
                        f"Tool '{tool.name}' (kind={tool.kind}) has no native Vertex AI equivalent. "
                        f"A TODO stub will be emitted."
                    ),
                )
            )


# ---------------------------------------------------------------------------
# Truncation helpers
# ---------------------------------------------------------------------------


def truncate_instruction(text: str, limit: int) -> str:
    """Truncate instruction text to at most *limit* characters.

    Attempts to truncate at the last sentence boundary (period/newline)
    before the limit. Appends a truncation notice.
    """
    if len(text) <= limit:
        return text

    # Reserve space for the truncation notice
    notice = "\n[... truncated — original in ir.json persona.system_prompt]"
    available = limit - len(notice)

    # Find last sentence boundary
    truncated = text[:available]
    last_period = max(truncated.rfind(". "), truncated.rfind(".\n"))
    if last_period > available // 2:
        truncated = truncated[: last_period + 1]

    warnings.warn(
        f"Instruction truncated from {len(text)} to {len(truncated) + len(notice)} chars "
        f"(limit={limit})",
        stacklevel=3,
    )
    return truncated + notice


def truncate_description(text: str, limit: int) -> str:
    """Truncate description to at most *limit* characters."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
