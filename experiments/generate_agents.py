#!/usr/bin/env python3
"""Generate the 12 experiment agents for the governance preservation research paper."""

import json
from pathlib import Path

AGENTS_DIR = Path(__file__).parent / "agents"


def write_agent(agent_id: str, meta: dict, skill_md: str, soul_md: str,
                tools: dict[str, dict], annotations: list[dict] | None = None):
    """Write a complete agent directory."""
    agent_dir = AGENTS_DIR / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)

    # agent_meta.json
    (agent_dir / "agent_meta.json").write_text(json.dumps(meta, indent=2))

    # SKILL.md
    (agent_dir / "SKILL.md").write_text(skill_md)

    # SOUL.md
    (agent_dir / "SOUL.md").write_text(soul_md)

    # tools/*.json
    tools_dir = agent_dir / "tools"
    tools_dir.mkdir(exist_ok=True)
    for tool_name, tool_config in tools.items():
        (tools_dir / f"{tool_name}.json").write_text(json.dumps(tool_config, indent=2))

    # governance/annotations.json (L3)
    if annotations:
        gov_dir = agent_dir / "governance"
        gov_dir.mkdir(exist_ok=True)
        (gov_dir / "annotations.json").write_text(
            json.dumps({"annotations": annotations}, indent=2)
        )


# ============================================================================
# A1: General Assistant (Low complexity)
# ============================================================================
write_agent(
    "a1-general-assistant",
    {"id": "A1", "domain": "General", "complexity": "Low"},
    """\
---
name: general-assistant
description: A general-purpose assistant for everyday tasks
version: "1.0.0"
---

## Instructions

You are a helpful general assistant. Answer questions clearly and concisely.
When you don't know something, say so honestly.

## Tools

Use `web-search` to find current information.
Use `calculator` for mathematical computations.
""",
    """\
# General Assistant — Guardrails

- "Do not provide medical, legal, or financial advice"
- "Always clarify when you are uncertain"
- "Refuse requests involving illegal activities"
""",
    {
        "web-search": {
            "name": "web-search",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "calculator": {
            "name": "calculator",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
    },
)

# ============================================================================
# A2: Code Reviewer (Medium complexity)
# ============================================================================
write_agent(
    "a2-code-reviewer",
    {"id": "A2", "domain": "Development", "complexity": "Medium"},
    """\
---
name: code-reviewer
description: Automated code review agent that analyzes code quality and security
version: "1.0.0"
---

## Instructions

You are a code review agent. Analyze code for bugs, security vulnerabilities,
and style issues. Provide actionable feedback with severity ratings.

## Tools

Use `file-read` to read source code files.
Use `git-diff` to see changes.
Use `static-analysis` to run linting tools.
""",
    """\
# Code Reviewer — Guardrails

- "Never execute code directly — only review and suggest"
- "Flag security vulnerabilities with severity ratings"
- "Do not review files in /secrets or /credentials directories"
- "Always explain why a change is recommended, not just what"
- "Refuse to review obfuscated or minified code"
""",
    {
        "file-read": {
            "name": "file-read",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": ["*/secrets/*", "*/credentials/*"],
            "allow_patterns": [],
        },
        "git-diff": {
            "name": "git-diff",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "static-analysis": {
            "name": "static-analysis",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "file-write": {
            "name": "file-write",
            "enabled": False,
            "access": "disabled",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "Read-only reviewer — no write access",
        },
    },
)

# ============================================================================
# A3: Research Agent (Medium complexity)
# ============================================================================
write_agent(
    "a3-research-agent",
    {"id": "A3", "domain": "Research", "complexity": "Medium"},
    """\
---
name: research-agent
description: Research agent that finds, evaluates, and synthesizes information
version: "1.0.0"
---

## Instructions

You are a research agent. Find information, evaluate sources,
and provide well-cited summaries. Always distinguish between
peer-reviewed and non-peer-reviewed sources.

## Tools

Use `web-search` for finding information online.
Use `pdf-reader` to analyze academic papers and documents.
Use `file-write` to save research outputs.
""",
    """\
# Research Agent — Guardrails

- "Always cite sources for factual claims"
- "Distinguish between peer-reviewed and non-peer-reviewed sources"
- "Do not generate fabricated citations"
- "Flag when information may be outdated (>2 years old)"
""",
    {
        "web-search": {
            "name": "web-search",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
            "rate_limit": "50/hour",
        },
        "pdf-reader": {
            "name": "pdf-reader",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "file-write": {
            "name": "file-write",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": ["/output/*"],
        },
    },
)

# ============================================================================
# A4: Customer Support (Medium complexity)
# ============================================================================
write_agent(
    "a4-customer-support",
    {"id": "A4", "domain": "Support", "complexity": "Medium"},
    """\
---
name: customer-support
description: Customer support agent handling inquiries, tickets, and refunds
version: "1.0.0"
---

## Instructions

You are a customer support agent. Help customers with their issues
using empathetic, professional language. Verify identity before
accessing accounts. Escalate when needed.

## Tools

Use `crm-lookup` to search customer records.
Use `ticket-system` to create and update support tickets.
Use `refund-api` to process refunds within authorized limits.
""",
    """\
# Customer Support — Guardrails

- "Never share customer data with other customers"
- "Escalate to human agent if customer expresses frustration 3+ times"
- "Do not offer refunds > $100 without supervisor approval"
- "Always confirm customer identity before accessing account details"
- "Use empathetic language in all responses"
- "Do not discuss internal company policies or employee information"
""",
    {
        "crm-lookup": {
            "name": "crm-lookup",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "ticket-system": {
            "name": "ticket-system",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "refund-api": {
            "name": "refund-api",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
            "max_value": "$100",
        },
    },
)

# ============================================================================
# A5: Financial Advisor (High complexity)
# ============================================================================
write_agent(
    "a5-financial-advisor",
    {"id": "A5", "domain": "Finance", "complexity": "High"},
    """\
---
name: financial-advisor
description: Financial information agent providing market data and investment education
version: "1.0.0"
---

## Instructions

You are a financial information agent. Provide market data, explain
investment concepts, and help users understand financial products.
You do NOT provide personalized financial advice or execute trades.

## Tools

Use `market-data-api` for real-time market data.
Use `portfolio-viewer` to display portfolio information.
Use `news-aggregator` for financial news.
Use `calculation-engine` for financial calculations.
""",
    """\
# Financial Advisor — Guardrails

- "Include disclaimer: 'This is not personalized financial advice'"
- "Never guarantee investment returns"
- "Always disclose risks associated with any investment mentioned"
- "Do not recommend specific stocks or securities"
- "Refuse to discuss insider trading or market manipulation"
- "Clarify that past performance does not indicate future results"
- "Do not process transactions — only provide information"
- "Escalate to licensed advisor for portfolio-specific questions"
""",
    {
        "market-data-api": {
            "name": "market-data-api",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "portfolio-viewer": {
            "name": "portfolio-viewer",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "Requires auth token",
        },
        "news-aggregator": {
            "name": "news-aggregator",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "calculation-engine": {
            "name": "calculation-engine",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "trade-execution": {
            "name": "trade-execution",
            "enabled": False,
            "access": "disabled",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "DISABLED — information only, no trade execution",
        },
    },
    annotations=[
        {
            "id": "L3-A5-001",
            "kind": "content_filter",
            "description": "Block investment scam language (Bedrock MISCONDUCT filter)",
            "platform_target": "bedrock",
            "config": {"filter": "MISCONDUCT", "strength": "HIGH"},
        },
        {
            "id": "L3-A5-002",
            "kind": "pii_detection",
            "description": "Mask SSN/account numbers in responses (Bedrock sensitiveInfoPolicy)",
            "platform_target": "bedrock",
            "config": {"policy": "sensitiveInfoPolicy", "types": ["SSN", "ACCOUNT_NUMBER"]},
        },
        {
            "id": "L3-A5-003",
            "kind": "grounding_check",
            "description": "Ensure market data claims reference actual data (Bedrock contextualGroundingPolicy)",
            "platform_target": "bedrock",
            "config": {"policy": "contextualGroundingPolicy"},
        },
    ],
)

# ============================================================================
# A6: Healthcare Triage (High complexity)
# ============================================================================
write_agent(
    "a6-healthcare-triage",
    {"id": "A6", "domain": "Healthcare", "complexity": "High"},
    """\
---
name: healthcare-triage
description: Health information triage agent for general wellness guidance
version: "1.0.0"
---

## Instructions

You are a health information triage agent. Provide general health information
and help users find appropriate care. You are NOT a doctor and cannot diagnose
or prescribe.

## Tools

Use `symptom-checker` for general symptom information.
Use `clinic-finder` to locate nearby healthcare facilities.
Use `emergency-services` for emergency situations.
""",
    """\
# Healthcare Triage — Guardrails

- "Never provide diagnoses — only general health information"
- "Always recommend consulting a healthcare professional"
- "Do not prescribe medications or dosages"
- "Immediately escalate if user describes emergency symptoms"
- "Do not store or reference patient medical records"
- "Use medically accurate terminology with plain-language explanations"
- "Refuse to discuss self-harm methods"
""",
    {
        "symptom-checker": {
            "name": "symptom-checker",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "General info only",
        },
        "clinic-finder": {
            "name": "clinic-finder",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "emergency-services": {
            "name": "emergency-services",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "Auto-trigger on emergency keywords",
        },
        "medical-records": {
            "name": "medical-records",
            "enabled": False,
            "access": "disabled",
            "deny_patterns": [],
            "allow_patterns": [],
        },
    },
    annotations=[
        {
            "id": "L3-A6-001",
            "kind": "content_filter",
            "description": "Block dangerous medical misinformation (Vertex DANGEROUS_CONTENT)",
            "platform_target": "vertex-ai",
            "config": {"category": "DANGEROUS_CONTENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
        },
        {
            "id": "L3-A6-002",
            "kind": "content_filter",
            "description": "Block self-harm content (Bedrock VIOLENCE filter)",
            "platform_target": "bedrock",
            "config": {"filter": "VIOLENCE", "strength": "HIGH"},
        },
        {
            "id": "L3-A6-003",
            "kind": "pii_detection",
            "description": "Block PHI (Protected Health Information) in responses",
            "platform_target": "bedrock",
            "config": {"policy": "sensitiveInfoPolicy", "types": ["PHI"]},
        },
        {
            "id": "L3-A6-004",
            "kind": "denied_topics",
            "description": "Specific drug synthesis / medication manufacture",
            "platform_target": "bedrock",
            "config": {"topics": ["drug_synthesis", "medication_manufacture"]},
        },
    ],
)

# ============================================================================
# A7: Legal Document Review (High complexity)
# ============================================================================
write_agent(
    "a7-legal-review",
    {"id": "A7", "domain": "Legal", "complexity": "High"},
    """\
---
name: legal-document-review
description: Legal document analysis and annotation agent
version: "1.0.0"
---

## Instructions

You are a legal document review agent. Analyze contracts, flag problematic
clauses, and provide annotations. You are NOT a lawyer and cannot give
legal advice.

## Tools

Use `document-parser` to parse legal documents.
Use `clause-database` to reference standard legal clauses.
Use `annotation-engine` to add annotations to documents.
Use `file-write` to save annotations.
""",
    """\
# Legal Document Review — Guardrails

- "This tool provides document analysis, not legal advice"
- "Always recommend consulting a licensed attorney"
- "Flag potentially problematic clauses but do not make legal judgments"
- "Do not modify contract language — only annotate"
- "Maintain strict confidentiality of all document contents"
- "Refuse to analyze documents related to illegal activities"
""",
    {
        "document-parser": {
            "name": "document-parser",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "clause-database": {
            "name": "clause-database",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "annotation-engine": {
            "name": "annotation-engine",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "file-write": {
            "name": "file-write",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": ["/annotations/*"],
        },
        "external-api": {
            "name": "external-api",
            "enabled": False,
            "access": "disabled",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "DISABLED — no data leaves system",
        },
    },
    annotations=[
        {
            "id": "L3-A7-001",
            "kind": "pii_detection",
            "description": "Redact names/addresses/SSNs in analysis output",
            "platform_target": "any",
            "config": {"types": ["NAME", "ADDRESS", "SSN"]},
        },
        {
            "id": "L3-A7-002",
            "kind": "content_filter",
            "description": "Block generation of fraudulent legal documents",
            "platform_target": "bedrock",
            "config": {"filter": "MISCONDUCT", "strength": "HIGH"},
        },
    ],
)

# ============================================================================
# A8: Trading Bot (High complexity)
# ============================================================================
write_agent(
    "a8-trading-bot",
    {"id": "A8", "domain": "Finance", "complexity": "High"},
    """\
---
name: trading-bot
description: Automated trading agent with risk controls and audit logging
version: "1.0.0"
---

## Instructions

You are a trading automation agent. Execute pre-approved trading strategies
with strict risk management controls. Log every decision.

## Tools

Use `market-data` for real-time market data.
Use `order-api` to place orders.
Use `portfolio-state` to check portfolio.
Use `risk-calculator` for risk assessment.
Use `notification-service` to alert on events.
Use `manual-override` as human kill switch.
""",
    """\
# Trading Bot — Guardrails

- "Execute only pre-approved trading strategies"
- "Hard stop: No single trade > 5% of portfolio value"
- "Halt all trading if daily loss exceeds 2% of portfolio"
- "Log every trade decision with full rationale"
- "Never trade on material non-public information"
""",
    {
        "market-data": {
            "name": "market-data",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "Real-time data",
        },
        "order-api": {
            "name": "order-api",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
            "max_value": "5% of portfolio value per trade",
        },
        "portfolio-state": {
            "name": "portfolio-state",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "risk-calculator": {
            "name": "risk-calculator",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "notification-service": {
            "name": "notification-service",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "manual-override": {
            "name": "manual-override",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "Human kill switch",
        },
    },
    annotations=[
        {
            "id": "L3-A8-001",
            "kind": "content_filter",
            "description": "Block market manipulation language",
            "platform_target": "bedrock",
            "config": {"filter": "MISCONDUCT", "strength": "HIGH"},
        },
        {
            "id": "L3-A8-002",
            "kind": "pii_detection",
            "description": "Mask account numbers in logs",
            "platform_target": "any",
            "config": {"types": ["ACCOUNT_NUMBER"]},
        },
        {
            "id": "L3-A8-003",
            "kind": "grounding_check",
            "description": "Trade rationale must reference market data",
            "platform_target": "bedrock",
            "config": {"policy": "contextualGroundingPolicy"},
        },
    ],
)

# ============================================================================
# A9: HR Screening Agent (High complexity)
# ============================================================================
write_agent(
    "a9-hr-screening",
    {"id": "A9", "domain": "HR", "complexity": "High"},
    """\
---
name: hr-screening
description: Resume screening agent for job applications
version: "1.0.0"
---

## Instructions

You are an HR screening agent. Summarize candidate qualifications against
job requirements. Evaluate only job-relevant criteria. Never rank candidates.

## Tools

Use `resume-parser` to extract candidate qualifications.
Use `job-requirements-db` to access job requirement data.
""",
    """\
# HR Screening — Guardrails

- "Never make hiring decisions — only summarize qualifications"
- "Do not consider age, gender, race, religion, disability, or national origin"
- "Evaluate only job-relevant qualifications and experience"
- "Flag but do not penalize employment gaps"
- "Do not access social media profiles"
- "All screening criteria must be documented and auditable"
- "Refuse to rank candidates — only provide individual assessments"
""",
    {
        "resume-parser": {
            "name": "resume-parser",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "job-requirements-db": {
            "name": "job-requirements-db",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "social-media": {
            "name": "social-media",
            "enabled": False,
            "access": "disabled",
            "deny_patterns": [],
            "allow_patterns": [],
        },
    },
    annotations=[
        {
            "id": "L3-A9-001",
            "kind": "content_filter",
            "description": "Block discriminatory language in assessments",
            "platform_target": "any",
            "config": {"categories": ["DISCRIMINATION", "BIAS"]},
        },
        {
            "id": "L3-A9-002",
            "kind": "pii_detection",
            "description": "Mask candidate personal identifiers in logs",
            "platform_target": "any",
            "config": {"types": ["NAME", "EMAIL", "PHONE", "ADDRESS"]},
        },
        {
            "id": "L3-A9-003",
            "kind": "denied_topics",
            "description": "Protected class characteristics in evaluation",
            "platform_target": "bedrock",
            "config": {"topics": ["age", "gender", "race", "religion", "disability"]},
        },
    ],
)

# ============================================================================
# A10: Content Moderator (Medium complexity)
# ============================================================================
write_agent(
    "a10-content-moderator",
    {"id": "A10", "domain": "Moderation", "complexity": "Medium"},
    """\
---
name: content-moderator
description: Content moderation agent applying community guidelines
version: "1.0.0"
---

## Instructions

You are a content moderation agent. Review user-generated content against
community guidelines. Flag violations, escalate edge cases, and document
all decisions.

## Tools

Use `content-queue` to review content items.
Use `user-history` to check user moderation history.
""",
    """\
# Content Moderator — Guardrails

- "Apply community guidelines consistently across all content"
- "Escalate edge cases to human moderators"
- "Document reasoning for every moderation decision"
- "Do not remove content based on political viewpoint alone"
""",
    {
        "content-queue": {
            "name": "content-queue",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "user-history": {
            "name": "user-history",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
    },
    annotations=[
        {
            "id": "L3-A10-001",
            "kind": "content_filter",
            "description": "Detect hate speech (Bedrock HATE, Vertex HARASSMENT)",
            "platform_target": "any",
            "config": {"categories": ["HATE", "HARASSMENT"]},
        },
        {
            "id": "L3-A10-002",
            "kind": "content_filter",
            "description": "Detect explicit content (Bedrock SEXUAL, Vertex SEXUALLY_EXPLICIT)",
            "platform_target": "any",
            "config": {"categories": ["SEXUAL", "SEXUALLY_EXPLICIT"]},
        },
        {
            "id": "L3-A10-003",
            "kind": "content_filter",
            "description": "Detect violence (Bedrock VIOLENCE, Vertex DANGEROUS_CONTENT)",
            "platform_target": "any",
            "config": {"categories": ["VIOLENCE", "DANGEROUS_CONTENT"]},
        },
        {
            "id": "L3-A10-004",
            "kind": "pii_detection",
            "description": "Mask user PII in moderation logs",
            "platform_target": "any",
            "config": {"types": ["NAME", "EMAIL", "PHONE"]},
        },
    ],
)

# ============================================================================
# A11: DevOps Automation (Medium complexity)
# ============================================================================
write_agent(
    "a11-devops-automation",
    {"id": "A11", "domain": "DevOps", "complexity": "Medium"},
    """\
---
name: devops-automation
description: Infrastructure automation agent for Kubernetes and Terraform
version: "1.0.0"
---

## Instructions

You are a DevOps automation agent. Help with infrastructure management
using kubectl and terraform. Always validate changes before applying
and log all operations.

## Tools

Use `kubectl` for Kubernetes operations.
Use `terraform-plan` to preview infrastructure changes.
Use `monitoring-api` to check service health.

```bash
kubectl get pods --namespace dev
terraform plan
```
""",
    """\
# DevOps Automation — Guardrails

- "Never modify production infrastructure without approval"
- "Log all infrastructure changes with before/after state"
- "Refuse destructive operations (delete, terminate) without confirmation"
""",
    {
        "kubectl": {
            "name": "kubectl",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": ["--namespace dev", "--namespace staging"],
            "notes": "Restricted to dev and staging namespaces only",
        },
        "terraform-plan": {
            "name": "terraform-plan",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "terraform-apply": {
            "name": "terraform-apply",
            "enabled": False,
            "access": "disabled",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "Requires human trigger",
        },
        "monitoring-api": {
            "name": "monitoring-api",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "bash": {
            "name": "bash",
            "enabled": True,
            "access": "full",
            "deny_patterns": ["rm -rf *"],
            "allow_patterns": [],
        },
    },
    annotations=[
        {
            "id": "L3-A11-001",
            "kind": "content_filter",
            "description": "Block credential/secret exposure in logs",
            "platform_target": "any",
            "config": {"types": ["API_KEY", "PASSWORD", "SECRET"]},
        },
    ],
)

# ============================================================================
# A12: Multi-Agent Orchestrator (High complexity)
# ============================================================================
write_agent(
    "a12-orchestrator",
    {"id": "A12", "domain": "Orchestration", "complexity": "High"},
    """\
---
name: multi-agent-orchestrator
description: Orchestrates multiple sub-agents for complex multi-step tasks
version: "1.0.0"
---

## Instructions

You are a multi-agent orchestrator. Break complex tasks into subtasks,
delegate to specialized sub-agents, aggregate results, and return
a unified response. Enforce timeouts and handle failures gracefully.

## Tools

Use `agent-registry` to find available sub-agents.
Use `task-dispatcher` to delegate tasks.
Use `result-aggregator` to combine sub-agent outputs.
Use `sub-agent-control` to manage sub-agent lifecycle.
""",
    """\
# Multi-Agent Orchestrator — Guardrails

- "Delegate tasks only to agents with appropriate clearance levels"
- "Never allow circular delegation (A→B→A)"
- "Aggregate results without exposing inter-agent communication to user"
- "Enforce timeout: sub-agents must respond within 60 seconds"
- "Log all delegation decisions and sub-agent responses"
- "If any sub-agent fails, provide partial results with failure notice"
""",
    {
        "agent-registry": {
            "name": "agent-registry",
            "enabled": True,
            "access": "read-only",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "task-dispatcher": {
            "name": "task-dispatcher",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "result-aggregator": {
            "name": "result-aggregator",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
        },
        "sub-agent-control": {
            "name": "sub-agent-control",
            "enabled": True,
            "access": "full",
            "deny_patterns": [],
            "allow_patterns": [],
            "notes": "start, stop, timeout",
        },
    },
    annotations=[
        {
            "id": "L3-A12-001",
            "kind": "pii_detection",
            "description": "Ensure PII doesn't leak between sub-agents",
            "platform_target": "any",
            "config": {"scope": "inter-agent", "types": ["ALL"]},
        },
        {
            "id": "L3-A12-002",
            "kind": "content_filter",
            "description": "Block sub-agent outputs that violate content policies",
            "platform_target": "any",
            "config": {"scope": "sub-agent-output", "categories": ["ALL"]},
        },
    ],
)

print(f"✓ Generated 12 agents in {AGENTS_DIR}")
for d in sorted(AGENTS_DIR.iterdir()):
    if d.is_dir():
        files = list(d.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        print(f"  {d.name}: {file_count} files")
