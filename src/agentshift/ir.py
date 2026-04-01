"""AgentShift Intermediate Representation (IR) — Pydantic v2 models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Governance models (L1 / L2 / L3)
# ---------------------------------------------------------------------------


class Guardrail(BaseModel):
    """Layer 1 — prompt-level governance rule (lives in SOUL.md / instructions)."""

    model_config = {"extra": "forbid"}

    id: str
    text: str
    category: Literal[
        "safety", "privacy", "compliance", "ethical", "operational", "scope", "general"
    ] = "general"
    severity: Literal["critical", "high", "medium", "low"] = "medium"


class ToolPermission(BaseModel):
    """Layer 2 — tool-level permission/restriction."""

    model_config = {"extra": "forbid"}

    tool_name: str
    enabled: bool = True
    access: Literal["full", "read-only", "disabled"] = "full"
    deny_patterns: list[str] = Field(default_factory=list)
    allow_patterns: list[str] = Field(default_factory=list)
    rate_limit: str | None = None
    max_value: str | None = None
    notes: str | None = None


class PlatformAnnotation(BaseModel):
    """Layer 3 — platform-native governance (Bedrock guardrails, Vertex safety, etc.)."""

    model_config = {"extra": "forbid"}

    id: str
    kind: Literal["content_filter", "pii_detection", "denied_topics", "grounding_check"] = (
        "content_filter"
    )
    description: str
    platform_target: Literal["bedrock", "vertex-ai", "m365", "any"] = "any"
    config: dict[str, Any] = Field(default_factory=dict)


class Governance(BaseModel):
    """Unified governance container for all three layers."""

    model_config = {"extra": "forbid"}

    guardrails: list[Guardrail] = Field(default_factory=list)
    tool_permissions: list[ToolPermission] = Field(default_factory=list)
    platform_annotations: list[PlatformAnnotation] = Field(default_factory=list)


class ToolAuth(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["none", "api_key", "oauth2", "bearer", "basic", "config_key"] = "none"
    env_var: str | None = None
    config_key: str | None = None
    scopes: list[str] = Field(default_factory=list)
    notes: str | None = None


class Tool(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    description: str
    kind: Literal["mcp", "openapi", "shell", "builtin", "function", "unknown"] = "unknown"
    parameters: dict[str, Any] | None = None
    auth: ToolAuth | None = None
    endpoint: str | None = None
    platform_availability: list[
        Literal["openclaw", "claude-code", "copilot", "bedrock", "vertex-ai"]
    ] = Field(default_factory=list)


class KnowledgeSource(BaseModel):
    model_config = {"extra": "forbid"}

    name: str
    kind: Literal["file", "directory", "url", "vector_store", "database", "s3"]
    path: str | None = None
    description: str | None = None
    format: Literal["markdown", "json", "yaml", "text", "pdf", "html", "unknown"] = "unknown"
    load_mode: Literal["always", "on_demand", "indexed"] = "on_demand"


class TriggerDelivery(BaseModel):
    model_config = {"extra": "forbid"}

    mode: Literal["announce", "silent", "reply"] = "announce"
    channel: Literal["telegram", "slack", "discord", "email", "webhook", "stdout"] | None = None
    to: str | None = None
    account_id: str | None = None


class Trigger(BaseModel):
    model_config = {"extra": "forbid"}

    kind: Literal["cron", "webhook", "message", "event", "manual"]
    id: str | None = None
    cron_expr: str | None = None
    every: str | None = None
    message: str | None = None
    webhook_path: str | None = None
    event_name: str | None = None
    delivery: TriggerDelivery | None = None
    session_target: Literal["isolated", "main", "thread"] = "isolated"
    enabled: bool = True


class Constraints(BaseModel):
    model_config = {"extra": "forbid"}

    max_instruction_chars: int | None = None
    supported_os: list[Literal["darwin", "linux", "windows"]] = Field(default_factory=list)
    required_bins: list[str] = Field(default_factory=list)
    any_required_bins: list[str] = Field(default_factory=list)
    required_config_keys: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    topic_restrictions: list[str] = Field(default_factory=list)


class InstallStep(BaseModel):
    model_config = {"extra": "forbid"}

    id: str
    kind: Literal["brew", "apt", "go", "npm", "pip", "cargo", "script", "manual"]
    formula: str | None = None
    package: str | None = None
    module: str | None = None
    script_url: str | None = None
    bins: list[str] = Field(default_factory=list)
    label: str | None = None


class Persona(BaseModel):
    model_config = {"extra": "forbid"}

    system_prompt: str | None = None
    personality_notes: str | None = None
    language: str = "en"
    sections: dict[str, str] | None = None


class Metadata(BaseModel):
    model_config = {"extra": "forbid"}

    source_platform: (
        Literal["openclaw", "claude-code", "copilot", "bedrock", "vertex-ai", "unknown"] | None
    ) = None
    target_platforms: list[
        Literal["openclaw", "claude-code", "copilot", "bedrock", "vertex-ai"]
    ] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    source_file: str | None = None
    emoji: str | None = None
    tags: list[str] = Field(default_factory=list)
    platform_extensions: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AgentIR(BaseModel):
    model_config = {"extra": "forbid"}

    ir_version: Literal["1.0"] = "1.0"
    name: str
    description: str
    version: str = "1.0.0"
    author: str | None = None
    homepage: str | None = None
    persona: Persona = Field(default_factory=Persona)
    tools: list[Tool] = Field(default_factory=list)
    knowledge: list[KnowledgeSource] = Field(default_factory=list)
    triggers: list[Trigger] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    governance: Governance = Field(default_factory=Governance)
    install: list[InstallStep] = Field(default_factory=list)
    metadata: Metadata = Field(default_factory=Metadata)
