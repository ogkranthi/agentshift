"""Stubs generator for auth/trigger/data binding configuration.

Provides generate_stubs(platform, ir) -> dict that returns platform-specific
auth/trigger/data binding templates for emitter README output.
"""

from __future__ import annotations

import re
from typing import Any

from agentshift.ir import AgentIR


def generate_stubs(platform: str, ir: AgentIR) -> dict[str, Any]:
    """Generate platform-specific auth/trigger/data binding stubs.

    Args:
        platform: Target platform (bedrock, copilot, m365, vertex).
        ir: AgentIR instance to generate stubs for.

    Returns:
        dict with keys: auth (dict), triggers (list), data_bindings (list).
    """
    _generators: dict[str, Any] = {
        "bedrock": _bedrock_stubs,
        "copilot": _copilot_stubs,
        "m365": _m365_stubs,
        "vertex": _vertex_stubs,
    }
    fn = _generators.get(platform)
    if fn is None:
        return {"auth": {}, "triggers": [], "data_bindings": []}
    return fn(ir)


def render_manual_config_section(platform: str, ir: AgentIR) -> list[str]:
    """Render a '## Manual Configuration Required' README section.

    Args:
        platform: Target platform identifier.
        ir: AgentIR instance.

    Returns:
        List of markdown lines for the section.
    """
    stubs = generate_stubs(platform, ir)
    lines: list[str] = [
        "## Manual Configuration Required",
        "",
        "The following resources require manual setup before the agent is fully operational.",
        "",
    ]

    auth = stubs.get("auth", {})
    if auth:
        auth_type = auth.get("type", "Auth")
        lines += [f"### Auth — {auth_type}", ""]
        _append_stub_fields(lines, auth)
        lines.append("")

    triggers = stubs.get("triggers", [])
    if triggers:
        lines += ["### Triggers", ""]
        for t in triggers:
            t_type = t.get("type", "Trigger")
            lines.append(f"**{t_type}**")
            _append_stub_fields(lines, t)
            lines.append("")

    data_bindings = stubs.get("data_bindings", [])
    if data_bindings:
        lines += ["### Data Bindings", ""]
        for db in data_bindings:
            db_type = db.get("type", "Data Binding")
            db_source = db.get("source", "")
            header = f"**{db_type}** — `{db_source}`" if db_source else f"**{db_type}**"
            lines.append(header)
            _append_stub_fields(lines, db)
            lines.append("")

    return lines


def _append_stub_fields(lines: list[str], d: dict[str, Any]) -> None:
    """Append non-type, non-source dict entries as bullet points."""
    for k, v in d.items():
        if k in ("type", "source"):
            continue
        if isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    for ik, iv in item.items():
                        lines.append(f"- **{ik}:** `{iv}`")
                else:
                    lines.append(f"- `{item}`")
        elif isinstance(v, dict):
            for ik, iv in v.items():
                lines.append(f"- **{ik}:** `{iv}`")
        else:
            lines.append(f"- **{k}:** `{v}`")


def _slug(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _bedrock_stubs(ir: AgentIR) -> dict[str, Any]:
    return {
        "auth": {
            "type": "IAM Role",
            "role_name": "agentshift-bedrock-role",
            "managed_policy": "arn:aws:iam::aws:policy/AmazonBedrockAgentResourcePolicy",
            "required_action": "bedrock:InvokeModel",
            "TODO": "Replace AgentRoleArn placeholder in cloudformation.yaml with the real IAM role ARN",
        },
        "triggers": [
            {
                "type": "EventBridge",
                "rule_name": f"{_slug(ir.name)}-schedule",
                "schedule_expression": t.cron_expr or "rate(1 day)",
                "TODO": "Set EventBridge target to invoke your Bedrock agent Lambda handler",
            }
            for t in ir.triggers
            if t.kind == "cron"
        ],
        "data_bindings": [
            {
                "type": "S3",
                "source": ks.name,
                "bucket": f"agentshift-{_slug(ir.name)}-knowledge",
                "TODO": f"Create S3 bucket and sync knowledge source '{ks.name}' before deploying",
            }
            for ks in ir.knowledge
        ],
    }


def _copilot_stubs(ir: AgentIR) -> dict[str, Any]:
    return {
        "auth": {
            "type": "GitHub Token",
            "scopes": ["copilot"],
            "TODO": "Ensure your GitHub account has an active GitHub Copilot subscription",
        },
        "triggers": [],
        "data_bindings": [],
    }


def _m365_stubs(ir: AgentIR) -> dict[str, Any]:
    return {
        "auth": {
            "type": "Entra ID (Azure AD)",
            "app_name": f"{ir.name} Agent",
            "required_permissions": ["User.Read", "Chat.Read"],
            "TODO": "Register app in Azure portal (portal.azure.com) and grant admin consent",
        },
        "triggers": [
            {
                "type": "Power Automate",
                "flow_name": f"{ir.name} Trigger",
                "connector": "Microsoft Teams",
                "TODO": "Create a Power Automate flow to invoke the agent on schedule or event",
            }
            for t in ir.triggers
            if t.kind in ("cron", "event", "webhook")
        ],
        "data_bindings": [
            {
                "type": "SharePoint/OneDrive",
                "source": ks.name,
                "site": "TODO: Set SharePoint site URL",
                "library": "TODO: Set document library name",
                "TODO": f"Upload knowledge source '{ks.name}' to SharePoint or OneDrive",
            }
            for ks in ir.knowledge
        ],
    }


def _vertex_stubs(ir: AgentIR) -> dict[str, Any]:
    svc_account = f"{_slug(ir.name)}@YOUR_PROJECT.iam.gserviceaccount.com"
    return {
        "auth": {
            "type": "GCP Service Account",
            "service_account": svc_account,
            "required_roles": ["roles/aiplatform.user", "roles/dialogflow.client"],
            "TODO": "Create service account and grant required roles in GCP IAM console",
        },
        "triggers": [
            {
                "type": "Cloud Scheduler",
                "job_name": f"{_slug(ir.name)}-schedule",
                "schedule": t.cron_expr or "0 9 * * *",
                "TODO": "Set Cloud Scheduler HTTP target to your Vertex AI agent endpoint",
            }
            for t in ir.triggers
            if t.kind == "cron"
        ],
        "data_bindings": [
            {
                "type": "Vertex AI Search",
                "source": ks.name,
                "data_store": f"{_slug(ir.name)}-datastore",
                "TODO": f"Create Vertex AI Search data store for knowledge source '{ks.name}'",
            }
            for ks in ir.knowledge
        ],
    }
