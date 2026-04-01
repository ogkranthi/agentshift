"""Shared parser utilities for AgentShift cloud parsers (Bedrock, Vertex AI)."""

from __future__ import annotations

import re

from agentshift.ir import Guardrail

# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------


def slugify(name: str) -> str:
    """Convert a display name to a URL-safe slug.

    Examples:
        'Pregnancy Companion' → 'pregnancy-companion'
        'My Agent 2' → 'my-agent-2'
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "unnamed"
    return slug


# Alias for clarity
title_case_to_slug = slugify


def is_todo_placeholder(value: str) -> bool:
    """Return True if value is a TODO/placeholder string emitted by an AgentShift emitter."""
    return bool(value) and ("TODO" in value or "PLACEHOLDER" in value)


# ---------------------------------------------------------------------------
# Guardrail inference
# ---------------------------------------------------------------------------

_GUARDRAIL_TRIGGER_PATTERNS: list[str] = [
    r"\bnever\b",
    r"\bdo not\b",
    r"\bdo n't\b",
    r"\balways\b",
    r"\bmust not\b",
    r"\bavoid\b",
    r"\bprohibited\b",
    r"\brefuse\b",
    r"\bdo not\b",
    r"\bnot allowed\b",
    r"\bforbidden\b",
]

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "safety": [
        "harm",
        "dangerous",
        "emergency",
        "self-harm",
        "violence",
        "injury",
        "medical",
        "diagnosis",
        "prescri",
        "suicide",
        "weapon",
    ],
    "privacy": [
        "pii",
        "personal",
        "confidential",
        "data",
        "privacy",
        "hipaa",
        "phi",
        "private",
        "sensitive",
        "identity",
        "password",
        "secret",
    ],
    "compliance": [
        "legal",
        "regulatory",
        "disclaimer",
        "licensed",
        "compliance",
        "warranty",
        "liability",
        "regulation",
    ],
    "ethical": [
        "bias",
        "discriminat",
        "fair",
        "race",
        "gender",
        "religion",
        "political",
        "offensive",
        "hate",
        "harassment",
    ],
    "operational": [
        "escalat",
        "timeout",
        "halt",
        "stop",
        "limit",
        "approval",
        "rate",
        "quota",
        "throttle",
    ],
    "scope": [
        "do not",
        "never",
        "refuse",
        "only",
        "restrict",
        "out of scope",
        "not support",
        "cannot",
        "won't",
    ],
}

_SEVERITY_HIGH_WORDS: list[str] = [
    "never",
    "immediately",
    "hard stop",
    "halt",
    "emergency",
    "critical",
    "absolutely",
    "strictly",
    "must never",
]
_SEVERITY_MEDIUM_HIGH_WORDS: list[str] = [
    "always",
    "must",
    "require",
    "do not",
    "prohibited",
]
_SEVERITY_LOW_WORDS: list[str] = [
    "should",
    "recommend",
    "prefer",
    "avoid when possible",
]


def infer_guardrail_category(text: str) -> str:
    """Infer a Guardrail category from keywords in the rule text."""
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "general"


def infer_guardrail_severity(text: str) -> str:
    """Infer a Guardrail severity from language patterns in the rule text."""
    lower = text.lower()
    if any(w in lower for w in _SEVERITY_HIGH_WORDS):
        return "critical"
    if any(w in lower for w in _SEVERITY_MEDIUM_HIGH_WORDS):
        return "high"
    if any(w in lower for w in _SEVERITY_LOW_WORDS):
        return "low"
    return "medium"


def _is_guardrail_sentence(sentence: str) -> bool:
    """Return True if the sentence looks like a guardrail rule."""
    lower = sentence.lower().strip()
    return any(re.search(pat, lower) for pat in _GUARDRAIL_TRIGGER_PATTERNS)


def extract_guardrails_from_text(
    text: str,
    id_prefix: str = "G",
    start_index: int = 1,
) -> list[Guardrail]:
    """Scan text for guardrail-like sentences and return Guardrail objects.

    Splits on sentence boundaries (`.`, `!`, `?`, newlines) and filters for
    lines that contain guardrail-indicator keywords.
    """
    guardrails: list[Guardrail] = []
    seen: set[str] = set()
    idx = start_index

    # Split on sentence/line boundaries
    sentences = re.split(r"[.!?\n]+", text)
    for sentence in sentences:
        cleaned = sentence.strip().strip("-").strip("*").strip()
        if not cleaned or len(cleaned) < 8:
            continue
        lower = cleaned.lower()
        if lower in seen:
            continue
        if _is_guardrail_sentence(cleaned):
            seen.add(lower)
            guardrails.append(
                Guardrail(
                    id=f"{id_prefix}{idx:03d}",
                    text=cleaned,
                    category=infer_guardrail_category(cleaned),
                    severity=infer_guardrail_severity(cleaned),
                )
            )
            idx += 1

    return guardrails
