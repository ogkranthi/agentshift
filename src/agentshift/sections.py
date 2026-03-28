"""Section extraction utilities for persona.sections (IR v0.2).

Implements the algorithm from spec A11 (persona-sections-schema.md §3.1).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alias map — canonical slug names for well-known section aliases
# ---------------------------------------------------------------------------

ALIAS_MAP: dict[str, str] = {
    "about": "overview",
    "description": "overview",
    "intro": "overview",
    "introduction": "overview",
    "instructions": "behavior",
    "rules": "behavior",
    "guidelines": "behavior",
    "how-i-work": "behavior",
    "how-to-use": "behavior",
    "safety": "guardrails",
    "restrictions": "guardrails",
    "limits": "guardrails",
    "do-not": "guardrails",
    "constraints": "guardrails",
    "capabilities": "tools",
    "integrations": "tools",
    "tool-use": "tools",
    "available-tools": "tools",
    "context": "knowledge",
    "background": "knowledge",
    "data": "knowledge",
    "knowledge-base": "knowledge",
    "personality": "persona",
    "tone": "persona",
    "voice": "persona",
    "character": "persona",
    "style": "persona",
    "sample-interactions": "examples",
    "usage-examples": "examples",
    "demos": "examples",
    "when-to-use": "triggers",
    "activation": "triggers",
    "use-cases": "triggers",
    "format": "output-format",
    "output": "output-format",
    "response-format": "output-format",
    "authentication": "auth",
    "credentials": "auth",
    "setup": "auth",
}


def normalize_slug(heading: str) -> str:
    """Normalize a markdown heading text to a canonical section slug.

    Steps:
    1. Strip leading '#' chars and trim whitespace.
    2. Lowercase the result.
    3. Replace all runs of non-alphanumeric chars (except '-') with '-'.
    4. Trim leading/trailing '-' chars.
    5. Apply alias map to canonical name.
    """
    slug = re.sub(r"^#+", "", heading).strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return ALIAS_MAP.get(slug, slug)


def extract_sections(
    text: str,
    *,
    normalize_aliases: bool = True,
    include_preamble: bool = False,
) -> dict[str, str]:
    """Extract H2 (or H3 fallback) sections from markdown text.

    Returns a dict mapping canonical section slugs to their body text.
    system_prompt must be set separately — this function only builds the sections map.

    Algorithm (per spec §3.1):
    1. Scan for H2 (##) headings. If none found, scan for H3 (###) headings.
    2. For each heading, normalize to slug and apply alias map.
    3. Collect content between headings as section body.
    4. Strip leading/trailing whitespace from each body.
    5. If duplicate canonical slugs, merge bodies with '\\n\\n' separator + warn.
    6. Content before first heading preserved only in system_prompt (not here),
       unless include_preamble=True → stored under 'preamble' key.
    """
    if not text or not text.strip():
        return {}

    lines = text.splitlines()

    # Determine heading level to use: H2 first, then H3 fallback
    h2_pattern = re.compile(r"^##\s+(.+)$")
    h3_pattern = re.compile(r"^###\s+(.+)$")

    has_h2 = any(h2_pattern.match(line) for line in lines)
    if has_h2:
        heading_pattern = h2_pattern
    else:
        has_h3 = any(h3_pattern.match(line) for line in lines)
        if not has_h3:
            return {}
        heading_pattern = h3_pattern

    # Parse sections
    sections_raw: list[tuple[str, list[str]]] = []  # (raw_heading_text, body_lines)
    preamble_lines: list[str] = []
    current_heading: str | None = None
    current_body: list[str] = []

    for line in lines:
        m = heading_pattern.match(line)
        if m:
            if current_heading is not None:
                sections_raw.append((current_heading, current_body))
            elif include_preamble and preamble_lines:
                sections_raw.append(("__preamble__", preamble_lines))
            current_heading = m.group(1)
            current_body = []
        else:
            if current_heading is None:
                preamble_lines.append(line)
            else:
                current_body.append(line)

    # Flush last section
    if current_heading is not None:
        sections_raw.append((current_heading, current_body))
    elif include_preamble and preamble_lines:
        sections_raw.append(("__preamble__", preamble_lines))

    if not sections_raw:
        return {}

    # Build result dict with normalization
    result: dict[str, str] = {}
    for raw_heading, body_lines in sections_raw:
        body_text = "\n".join(body_lines).strip()

        if raw_heading == "__preamble__":
            slug = "preamble"
        elif normalize_aliases:
            slug = normalize_slug(raw_heading)
        else:
            # Still normalize format but skip alias map
            slug = re.sub(r"^#+", "", raw_heading).strip().lower()
            slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")

        if slug in result:
            # Duplicate canonical mapping — merge with warning
            logger.debug(
                "Duplicate section slug '%s' (from heading '%s') — merging bodies.", slug, raw_heading
            )
            result[slug] = result[slug] + "\n\n" + body_text
        else:
            result[slug] = body_text

    return result
