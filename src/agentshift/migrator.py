"""OpenClaw → NemoClaw full-installation migrator.

Scans an entire OpenClaw install directory (~/.openclaw), parses every skill,
emits NemoClaw artifacts, merges network policies, migrates cron jobs, and
generates cloud deploy files.
"""

from __future__ import annotations

import json
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agentshift.emitters.nemoclaw import emit as nemoclaw_emit
from agentshift.ir import AgentIR
from agentshift.parsers.openclaw import parse_skill_dir


@dataclass
class MigrationResult:
    skills_total: int = 0
    skills_migrated: int = 0
    skills_skipped: list[str] = field(default_factory=list)
    cron_jobs_total: int = 0
    cron_jobs_migrated: int = 0
    credentials_required: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def migrate_openclaw_to_nemoclaw(
    source: Path,
    output: Path,
    cloud: str = "docker",
) -> MigrationResult:
    """Migrate an entire OpenClaw installation to NemoClaw."""
    result = MigrationResult()
    output.mkdir(parents=True, exist_ok=True)

    # 1. Scan and migrate skills
    skills_dir = source / "skills"
    irs: list[AgentIR] = []

    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            result.skills_total += 1

            try:
                ir = parse_skill_dir(skill_dir)
            except Exception as e:
                result.errors.append(f"Failed to parse {skill_dir.name}: {e}")
                continue

            # Skip macOS-only skills
            if ir.constraints.supported_os == ["darwin"]:
                result.skills_skipped.append(f"{ir.name} (macOS-only)")
                continue

            skill_output = output / "workspace" / "skills" / ir.name
            try:
                nemoclaw_emit(ir, skill_output)
                irs.append(ir)
                result.skills_migrated += 1
            except Exception as e:
                result.errors.append(f"Failed to emit {ir.name}: {e}")

    # 2. Merge network policies (deduplicated)
    _write_merged_network_policy(irs, output)

    # 3. Migrate cron jobs
    _migrate_cron_jobs(source, output, result)

    # 4. Workspace files
    _write_workspace_files(source, output, irs)

    # 5. Config scan for credentials
    _scan_credentials(source, result)

    # 6. Cloud deploy files
    _write_cloud_deploy(cloud, output, irs)

    # 7. Main nemoclaw-config.yaml
    _write_main_config(irs, output)

    # 8. MIGRATION_REPORT.md
    _write_migration_report(result, cloud, output)

    return result


# ---------------------------------------------------------------------------
# Merged network policy
# ---------------------------------------------------------------------------


def _write_merged_network_policy(irs: list[AgentIR], output: Path) -> None:
    """Collect all tool-based egress rules from all skills, deduplicate."""
    seen_names: set[str] = set()
    policies: list[dict] = [
        {
            "name": "claude_code",
            "endpoints": ["api.anthropic.com:443"],
            "binaries": ["/usr/local/bin/claude"],
        },
        {
            "name": "nvidia",
            "endpoints": [
                "integrate.api.nvidia.com:443",
                "inference-api.nvidia.com:443",
            ],
            "binaries": ["/usr/local/bin/openclaw"],
        },
    ]
    seen_names.update(["claude_code", "nvidia"])
    comments: list[str] = []

    for ir in irs:
        for tool in ir.tools:
            if tool.kind == "shell":
                if tool.name in ("gh", "git") and "github" not in seen_names:
                    policies.append(
                        {
                            "name": "github",
                            "endpoints": ["api.github.com:443", "github.com:443"],
                            "binaries": [f"/usr/local/bin/{tool.name}"],
                        }
                    )
                    seen_names.add("github")
                elif tool.name in ("curl", "wget") and f"custom_{tool.name}" not in seen_names:
                    comments.append(
                        f"# TODO: Add network policy for {tool.name}\n"
                        f"# - name: custom_{tool.name}\n"
                        f"#   endpoints: [your-api.example.com:443]\n"
                        f"#   binaries: [/usr/local/bin/{tool.name}]"
                    )
                    seen_names.add(f"custom_{tool.name}")
                elif tool.name in ("npm", "node") and "npm_registry" not in seen_names:
                    policies.append(
                        {
                            "name": "npm_registry",
                            "endpoints": ["registry.npmjs.org:443"],
                            "binaries": [f"/usr/local/bin/{tool.name}"],
                        }
                    )
                    seen_names.add("npm_registry")
            elif tool.kind == "mcp" and f"mcp_{tool.name}" not in seen_names:
                comments.append(
                    f"# TODO: Add network policy for MCP tool '{tool.name}'\n"
                    f"# - name: mcp_{tool.name}\n"
                    f"#   endpoints: [your-mcp-endpoint.example.com:443]\n"
                    f"#   binaries: [/usr/local/bin/openclaw]"
                )
                seen_names.add(f"mcp_{tool.name}")

    header = (
        "# Merged Network Policy — generated by AgentShift migrate\n"
        "# NemoClaw uses deny-by-default. Add endpoints your agents need.\n\n"
    )

    data = {"policies": policies}
    content = header + yaml.dump(data, default_flow_style=False, sort_keys=False)

    if comments:
        content += "\n" + "\n\n".join(comments) + "\n"

    (output / "network-policy.yaml").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Cron jobs
# ---------------------------------------------------------------------------


def _migrate_cron_jobs(source: Path, output: Path, result: MigrationResult) -> None:
    """Read cron/jobs.json and generate cron-migration.sh."""
    jobs_path = source / "cron" / "jobs.json"
    if not jobs_path.exists():
        return

    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        result.warnings.append("Could not parse cron/jobs.json")
        return

    jobs = data.get("jobs", [])
    result.cron_jobs_total = len(jobs)

    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "# Cron job migration — generated by AgentShift migrate",
        "# NOTE: Delivery channel configs (Telegram bot tokens, etc.) are NOT migrated for security.",
        "",
    ]

    for job in jobs:
        if not job.get("enabled", True):
            continue
        agent_id = job.get("agentId", "unknown")
        cron_expr = job.get("schedule", {}).get("expr", "* * * * *")
        message = job.get("payload", {}).get("message", "")
        session_target = job.get("sessionTarget", "isolated")

        lines.append(f"# Agent: {agent_id}")
        lines.append(
            f'openshell policy cron add --agent "{agent_id}" '
            f'--schedule "{cron_expr}" '
            f'--message "{message}" '
            f'--session-target "{session_target}"'
        )
        lines.append("")
        result.cron_jobs_migrated += 1

    script_path = output / "cron-migration.sh"
    script_path.write_text("\n".join(lines), encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# ---------------------------------------------------------------------------
# Workspace files (SOUL.md, MEMORY.md, IDENTITY.md)
# ---------------------------------------------------------------------------


def _write_workspace_files(source: Path, output: Path, irs: list[AgentIR]) -> None:
    ws = output / "workspace"
    ws.mkdir(parents=True, exist_ok=True)

    # SOUL.md — copy from source if exists, else generate
    source_soul = source / "SOUL.md"
    if source_soul.exists():
        shutil.copy2(source_soul, ws / "SOUL.md")
    else:
        # Generate from skills
        lines = ["# SOUL.md - Agent Persona", "", "## Core Identity"]
        if irs:
            lines.append(f"Multi-skill agent with {len(irs)} skills.")
        else:
            lines.append("Be helpful, accurate, and concise.")
        lines += ["", "## Boundaries", "- Follow user instructions within safe boundaries.", ""]
        (ws / "SOUL.md").write_text("\n".join(lines), encoding="utf-8")

    # MEMORY.md — copy with warning header
    source_memory = source / "MEMORY.md"
    if source_memory.exists():
        original = source_memory.read_text(encoding="utf-8")
        warning = (
            "> **WARNING:** This MEMORY.md was copied from your OpenClaw installation.\n"
            "> Review all entries before migrating to NemoClaw — remove any stale or sensitive data.\n\n"
        )
        (ws / "MEMORY.md").write_text(warning + original, encoding="utf-8")

    # IDENTITY.md — generate
    lines = [
        "# IDENTITY.md",
        "",
        "- **Name:** NemoClaw Agent",
        "- **Creature:** AI agent",
        "- **Vibe:** Helpful and focused",
        "",
    ]
    (ws / "IDENTITY.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Credential scanning
# ---------------------------------------------------------------------------


def _scan_credentials(source: Path, result: MigrationResult) -> None:
    """Extract credential key names (not values) from config.json."""
    config_path = source / "config" / "config.json"
    if not config_path.exists():
        config_path = source / "config.json"
    if not config_path.exists():
        return

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        result.warnings.append("Could not parse config.json")
        return

    _extract_keys(data, "", result.credentials_required)


def _extract_keys(data: dict, prefix: str, keys: list[str]) -> None:
    """Recursively extract dotted key paths from config dict."""
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            _extract_keys(value, full_key, keys)
        else:
            keys.append(full_key)


# ---------------------------------------------------------------------------
# Cloud deploy files
# ---------------------------------------------------------------------------

_AWS_USERDATA = """\
#!/usr/bin/env bash
set -euo pipefail
# AWS EC2 User Data — NemoClaw deployment
# Generated by AgentShift migrate

# Install NemoClaw
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash

SANDBOX_NAME="{name}"

# Create sandbox
nemoclaw sandbox create "${{SANDBOX_NAME}}" \\
  --config /opt/nemoclaw/nemoclaw-config.yaml \\
  --network-policy /opt/nemoclaw/network-policy.yaml

# Upload workspace files
for f in /opt/nemoclaw/workspace/skills/*/workspace/*.md; do
  skill_name=$(basename "$(dirname "$(dirname "$f")")")
  openshell sandbox upload "${{SANDBOX_NAME}}" "$f" "/sandbox/.openclaw/workspace/${{skill_name}}/$(basename "$f")"
done

echo "NemoClaw agent deployed. Connect: nemoclaw ${{SANDBOX_NAME}} connect"
"""

_DOCKER_COMPOSE = """\
version: "3.9"
services:
  nemoclaw:
    image: ghcr.io/nvidia/nemoclaw-sandbox:latest
    container_name: {name}
    volumes:
      - ./workspace:/sandbox/.openclaw/workspace:ro
    environment:
      - NEMOCLAW_POSTURE=balanced
    restart: unless-stopped
    ports:
      - "8080:8080"
"""

_GCP_STARTUP = """\
#!/usr/bin/env bash
set -euo pipefail
# GCP Compute Engine startup script — NemoClaw deployment
# Generated by AgentShift migrate

# Install NemoClaw
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash

SANDBOX_NAME="{name}"

# Create sandbox
nemoclaw sandbox create "${{SANDBOX_NAME}}" \\
  --config /opt/nemoclaw/nemoclaw-config.yaml \\
  --network-policy /opt/nemoclaw/network-policy.yaml

# Upload workspace files
for f in /opt/nemoclaw/workspace/skills/*/workspace/*.md; do
  skill_name=$(basename "$(dirname "$(dirname "$f")")")
  openshell sandbox upload "${{SANDBOX_NAME}}" "$f" "/sandbox/.openclaw/workspace/${{skill_name}}/$(basename "$f")"
done

echo "NemoClaw agent deployed. Connect: nemoclaw ${{SANDBOX_NAME}} connect"
"""

_AZURE_CLOUD_INIT = """\
#cloud-config
# Azure VM cloud-init — NemoClaw deployment
# Generated by AgentShift migrate

runcmd:
  - curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
  - nemoclaw sandbox create "{name}" --config /opt/nemoclaw/nemoclaw-config.yaml --network-policy /opt/nemoclaw/network-policy.yaml
  - echo "NemoClaw agent deployed"
"""

_BARE_METAL_DEPLOY = """\
#!/usr/bin/env bash
set -euo pipefail
# Bare-metal deployment — NemoClaw
# Generated by AgentShift migrate

SANDBOX_NAME="{name}"
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

echo "Deploying ${{SANDBOX_NAME}} to NemoClaw..."

# Check nemoclaw is installed
if ! command -v nemoclaw &> /dev/null; then
  echo "nemoclaw CLI not found. Install: curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash"
  exit 1
fi

# Check openshell is running
if ! openshell gateway status &> /dev/null; then
  echo "OpenShell gateway not running. Start: openshell gateway start"
  exit 1
fi

# Create sandbox
nemoclaw sandbox create "${{SANDBOX_NAME}}" \\
  --config "${{SCRIPT_DIR}}/../nemoclaw-config.yaml" \\
  --network-policy "${{SCRIPT_DIR}}/../network-policy.yaml"

# Upload workspace files
for f in "${{SCRIPT_DIR}}/../workspace/skills"/*/workspace/*.md; do
  skill_name=$(basename "$(dirname "$(dirname "$f")")")
  openshell sandbox upload "${{SANDBOX_NAME}}" "$f" "/sandbox/.openclaw/workspace/${{skill_name}}/$(basename "$f")"
done

echo "${{SANDBOX_NAME}} deployed successfully!"
echo "  Connect: nemoclaw ${{SANDBOX_NAME}} connect"
"""

_DEPLOY_README = {
    "aws": (
        "# AWS Deployment\n\n"
        "1. Launch an EC2 instance with `userdata.sh` as user data\n"
        "2. Upload workspace files to `/opt/nemoclaw/`\n"
        "3. Connect: `nemoclaw <sandbox-name> connect`\n"
    ),
    "gcp": (
        "# GCP Deployment\n\n"
        "1. Create a Compute Engine instance with `startup-script.sh` as startup metadata\n"
        "2. Upload workspace files to `/opt/nemoclaw/`\n"
        "3. Connect: `nemoclaw <sandbox-name> connect`\n"
    ),
    "azure": (
        "# Azure Deployment\n\n"
        "1. Create a VM with `cloud-init.yaml` as custom data\n"
        "2. Upload workspace files to `/opt/nemoclaw/`\n"
        "3. Connect: `nemoclaw <sandbox-name> connect`\n"
    ),
    "docker": (
        "# Docker Deployment\n\n"
        "1. Place workspace files in `./workspace/`\n"
        "2. Run: `docker compose up -d`\n"
        "3. Access on port 8080\n"
    ),
    "bare-metal": (
        "# Bare Metal Deployment\n\n"
        "1. Install NemoClaw: `curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash`\n"
        "2. Start OpenShell: `openshell gateway start`\n"
        "3. Run: `./deploy.sh`\n"
    ),
}


def _write_cloud_deploy(cloud: str, output: Path, irs: list[AgentIR]) -> None:
    deploy_dir = output / "deploy" / cloud
    deploy_dir.mkdir(parents=True, exist_ok=True)

    name = irs[0].name if irs else "nemoclaw-agent"

    if cloud == "aws":
        path = deploy_dir / "userdata.sh"
        path.write_text(_AWS_USERDATA.format(name=name), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    elif cloud == "gcp":
        path = deploy_dir / "startup-script.sh"
        path.write_text(_GCP_STARTUP.format(name=name), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    elif cloud == "azure":
        (deploy_dir / "cloud-init.yaml").write_text(
            _AZURE_CLOUD_INIT.format(name=name), encoding="utf-8"
        )
    elif cloud == "docker":
        (deploy_dir / "docker-compose.yml").write_text(
            _DOCKER_COMPOSE.format(name=name), encoding="utf-8"
        )
    elif cloud == "bare-metal":
        path = deploy_dir / "deploy.sh"
        path.write_text(_BARE_METAL_DEPLOY.format(name=name), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    readme_text = _DEPLOY_README.get(cloud, f"# {cloud} Deployment\n\nSee generated files.\n")
    (deploy_dir / "README.md").write_text(readme_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main nemoclaw-config.yaml
# ---------------------------------------------------------------------------


def _write_main_config(irs: list[AgentIR], output: Path) -> None:
    skill_names = [ir.name for ir in irs]

    config = {
        "sandbox": {
            "name": skill_names[0] if skill_names else "nemoclaw-agent",
            "skills": skill_names,
        },
        "inference": {
            "provider": "nvidia",
        },
        "workspace": {
            "upload_on_deploy": True,
        },
        "security": {
            "posture": "balanced",
            "operator_approval": True,
        },
    }

    header = (
        "# NemoClaw Configuration — merged from all migrated skills\n"
        "# Generated by AgentShift migrate\n\n"
    )

    content = header + yaml.dump(config, default_flow_style=False, sort_keys=False)
    (output / "nemoclaw-config.yaml").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# MIGRATION_REPORT.md
# ---------------------------------------------------------------------------


def _write_migration_report(result: MigrationResult, cloud: str, output: Path) -> None:
    lines = [
        "# Migration Report: OpenClaw → NemoClaw",
        "",
        "Generated by AgentShift `migrate` command.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Skills found | {result.skills_total} |",
        f"| Skills migrated | {result.skills_migrated} |",
        f"| Skills skipped | {len(result.skills_skipped)} |",
        f"| Cron jobs found | {result.cron_jobs_total} |",
        f"| Cron jobs migrated | {result.cron_jobs_migrated} |",
        f"| Credentials to re-enter | {len(result.credentials_required)} |",
        f"| Warnings | {len(result.warnings)} |",
        f"| Errors | {len(result.errors)} |",
        f"| Cloud target | {cloud} |",
        "",
    ]

    # Migrated skills
    migrated_count = result.skills_migrated
    if migrated_count > 0:
        lines += [
            "## Migrated Skills",
            "",
        ]
        lines.append(f"{migrated_count} skill(s) migrated successfully.")
        lines.append("")

    # Skipped skills
    if result.skills_skipped:
        lines += [
            "## Skipped Skills",
            "",
        ]
        for s in result.skills_skipped:
            lines.append(f"- {s}")
        lines.append("")

    # Manual steps
    if result.credentials_required:
        lines += [
            "## Credential Checklist",
            "",
            "The following credentials must be re-entered during NemoClaw onboarding:",
            "",
        ]
        for cred in result.credentials_required:
            lines.append(f"- [ ] `{cred}`")
        lines.append("")

    # Warnings
    if result.warnings:
        lines += [
            "## Warnings",
            "",
        ]
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # Errors
    if result.errors:
        lines += [
            "## Errors",
            "",
        ]
        for e in result.errors:
            lines.append(f"- {e}")
        lines.append("")

    # Steps
    lines += [
        "## Next Steps",
        "",
        f"1. Review generated files in `{output}/`",
        "2. Review `workspace/MEMORY.md` and remove stale data",
        "3. Re-enter credentials listed above",
        f"4. Deploy using `deploy/{cloud}/` instructions",
        "5. Run `cron-migration.sh` to restore scheduled jobs",
        "",
    ]

    (output / "MIGRATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
