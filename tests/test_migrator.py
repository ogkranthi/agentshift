"""Tests for the OpenClaw → NemoClaw migrator."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest
import yaml

from agentshift.migrator import MigrationResult, migrate_openclaw_to_nemoclaw

# ---------------------------------------------------------------------------
# Fixture: fake OpenClaw install directory
# ---------------------------------------------------------------------------


@pytest.fixture()
def openclaw_source(tmp_path: Path) -> Path:
    """Create a fake ~/.openclaw directory with 3 skills, cron jobs, and config."""
    source = tmp_path / "openclaw"
    source.mkdir()

    # Skill 1: normal skill
    skill1 = source / "skills" / "weather"
    skill1.mkdir(parents=True)
    (skill1 / "SKILL.md").write_text(
        "---\nname: weather\ndescription: Weather forecasting skill\nos: [linux, darwin]\n---\n\n"
        "You are a weather forecasting agent.\n\n"
        "```bash\ncurl https://api.weather.com/forecast\n```\n",
        encoding="utf-8",
    )

    # Skill 2: normal skill with tools
    skill2 = source / "skills" / "github-helper"
    skill2.mkdir(parents=True)
    (skill2 / "SKILL.md").write_text(
        "---\nname: github-helper\ndescription: GitHub assistant\nos: [linux, darwin]\n---\n\n"
        "You help with GitHub repos.\n\n"
        "```bash\ngh pr list\ngit status\n```\n",
        encoding="utf-8",
    )

    # Skill 3: macOS-only (should be skipped)
    skill3 = source / "skills" / "macos-only"
    skill3.mkdir(parents=True)
    (skill3 / "SKILL.md").write_text(
        "---\nname: macos-only\ndescription: macOS-only skill\nos: [darwin]\n---\n\n"
        "You are a macOS-only agent.\n",
        encoding="utf-8",
    )

    # Cron jobs
    cron_dir = source / "cron"
    cron_dir.mkdir()
    (cron_dir / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": "job-1",
                        "agentId": "weather",
                        "enabled": True,
                        "schedule": {"expr": "0 8 * * *"},
                        "payload": {"message": "Daily weather report"},
                        "sessionTarget": "isolated",
                        "delivery": {
                            "channel": "telegram",
                            "to": "user123",
                            "mode": "announce",
                        },
                    },
                    {
                        "id": "job-2",
                        "agentId": "github-helper",
                        "enabled": True,
                        "schedule": {"expr": "0 9 * * 1"},
                        "payload": {"message": "Weekly PR summary"},
                        "sessionTarget": "main",
                        "delivery": {"channel": "slack", "to": "#team"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    # Config with credentials
    config_dir = source / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "channels": {"telegram": "bot-token-xxx", "slack": "xoxb-xxx"},
                "api": {"github": "ghp_xxx"},
            }
        ),
        encoding="utf-8",
    )

    # SOUL.md at root
    (source / "SOUL.md").write_text("# SOUL.md\n\nBe helpful.\n", encoding="utf-8")

    # MEMORY.md at root
    (source / "MEMORY.md").write_text(
        "# Memory\n\n- User likes concise answers\n", encoding="utf-8"
    )

    return source


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------


class TestMigratorOutputStructure:
    def test_creates_output_directory(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert out.is_dir()

    def test_creates_workspace_directory(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert (out / "workspace").is_dir()

    def test_creates_network_policy(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert (out / "network-policy.yaml").exists()

    def test_creates_nemoclaw_config(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert (out / "nemoclaw-config.yaml").exists()

    def test_creates_migration_report(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert (out / "MIGRATION_REPORT.md").exists()


# ---------------------------------------------------------------------------
# Skill migration
# ---------------------------------------------------------------------------


class TestMigratorSkills:
    def test_scans_all_skills(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert result.skills_total == 3

    def test_migrates_normal_skills(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert result.skills_migrated == 2

    def test_skips_macos_only_skill(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert len(result.skills_skipped) == 1
        assert "macOS-only" in result.skills_skipped[0]

    def test_skill_output_directories_created(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert (out / "workspace" / "skills" / "weather").is_dir()
        assert (out / "workspace" / "skills" / "github-helper").is_dir()

    def test_macos_only_skill_not_in_output(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert not (out / "workspace" / "skills" / "macos-only").exists()

    def test_skills_migrated_count_correct(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert result.skills_migrated == result.skills_total - len(result.skills_skipped)


# ---------------------------------------------------------------------------
# Cron job migration
# ---------------------------------------------------------------------------


class TestMigratorCronJobs:
    def test_cron_jobs_read_from_jobs_json(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert result.cron_jobs_total == 2

    def test_cron_migration_sh_generated(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert (out / "cron-migration.sh").exists()

    def test_cron_migration_sh_executable(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        st = os.stat(out / "cron-migration.sh")
        assert st.st_mode & stat.S_IXUSR

    def test_cron_migration_sh_contains_openshell(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        content = (out / "cron-migration.sh").read_text()
        assert "openshell policy cron add" in content

    def test_cron_jobs_migrated_count(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert result.cron_jobs_migrated == 2

    def test_no_cron_dir_handled_gracefully(self, tmp_path):
        source = tmp_path / "empty-openclaw"
        source.mkdir()
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(source, out)
        assert result.cron_jobs_total == 0
        assert result.cron_jobs_migrated == 0


# ---------------------------------------------------------------------------
# Network policy
# ---------------------------------------------------------------------------


class TestMigratorNetworkPolicy:
    def test_network_policy_is_valid_yaml(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        data = yaml.safe_load((out / "network-policy.yaml").read_text())
        assert isinstance(data, dict)
        assert "policies" in data

    def test_network_policy_deduplicates(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        data = yaml.safe_load((out / "network-policy.yaml").read_text())
        names = [p["name"] for p in data["policies"]]
        # github should appear only once even though both gh and git tools exist
        assert names.count("github") == 1


# ---------------------------------------------------------------------------
# Workspace files
# ---------------------------------------------------------------------------


class TestMigratorWorkspaceFiles:
    def test_soul_md_created(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert (out / "workspace" / "SOUL.md").exists()

    def test_soul_md_copied_from_source(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        content = (out / "workspace" / "SOUL.md").read_text()
        assert "Be helpful" in content

    def test_memory_md_copied_with_warning(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        content = (out / "workspace" / "MEMORY.md").read_text()
        assert "WARNING" in content
        assert "User likes concise answers" in content

    def test_identity_md_created(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert (out / "workspace" / "IDENTITY.md").exists()


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


class TestMigratorCredentials:
    def test_credentials_required_populated(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert len(result.credentials_required) > 0

    def test_credentials_include_channel_keys(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        cred_str = " ".join(result.credentials_required)
        assert "channels.telegram" in cred_str
        assert "channels.slack" in cred_str
        assert "api.github" in cred_str


# ---------------------------------------------------------------------------
# Cloud deploy files
# ---------------------------------------------------------------------------


class TestMigratorCloudDeploy:
    def test_deploy_aws_created(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out, cloud="aws")
        assert (out / "deploy" / "aws" / "userdata.sh").exists()
        assert (out / "deploy" / "aws" / "README.md").exists()

    def test_deploy_docker_created(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out, cloud="docker")
        assert (out / "deploy" / "docker" / "docker-compose.yml").exists()
        assert (out / "deploy" / "docker" / "README.md").exists()

    def test_deploy_gcp_created(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out, cloud="gcp")
        assert (out / "deploy" / "gcp" / "startup-script.sh").exists()
        assert (out / "deploy" / "gcp" / "README.md").exists()

    def test_deploy_azure_created(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out, cloud="azure")
        assert (out / "deploy" / "azure" / "cloud-init.yaml").exists()
        assert (out / "deploy" / "azure" / "README.md").exists()

    def test_deploy_bare_metal_created(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out, cloud="bare-metal")
        assert (out / "deploy" / "bare-metal" / "deploy.sh").exists()
        assert (out / "deploy" / "bare-metal" / "README.md").exists()

    def test_docker_compose_valid_yaml(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out, cloud="docker")
        data = yaml.safe_load((out / "deploy" / "docker" / "docker-compose.yml").read_text())
        assert "services" in data
        assert "nemoclaw" in data["services"]


# ---------------------------------------------------------------------------
# Migration report
# ---------------------------------------------------------------------------


class TestMigratorReport:
    def test_report_contains_summary(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        content = (out / "MIGRATION_REPORT.md").read_text()
        assert "Summary" in content
        assert "Skills found" in content

    def test_report_mentions_skipped(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        content = (out / "MIGRATION_REPORT.md").read_text()
        assert "Skipped" in content

    def test_report_has_credential_checklist(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        content = (out / "MIGRATION_REPORT.md").read_text()
        assert "Credential Checklist" in content

    def test_report_has_next_steps(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        migrate_openclaw_to_nemoclaw(openclaw_source, out)
        content = (out / "MIGRATION_REPORT.md").read_text()
        assert "Next Steps" in content


# ---------------------------------------------------------------------------
# MigrationResult dataclass
# ---------------------------------------------------------------------------


class TestMigrationResult:
    def test_dataclass_defaults(self):
        r = MigrationResult()
        assert r.skills_total == 0
        assert r.skills_migrated == 0
        assert r.skills_skipped == []
        assert r.cron_jobs_total == 0
        assert r.cron_jobs_migrated == 0
        assert r.credentials_required == []
        assert r.warnings == []
        assert r.errors == []

    def test_dataclass_has_correct_counts(self, openclaw_source, tmp_path):
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(openclaw_source, out)
        assert result.skills_total == 3
        assert result.skills_migrated == 2
        assert result.cron_jobs_total == 2
        assert result.cron_jobs_migrated == 2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestMigratorEdgeCases:
    def test_empty_source_dir(self, tmp_path):
        source = tmp_path / "empty"
        source.mkdir()
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(source, out)
        assert result.skills_total == 0
        assert result.skills_migrated == 0
        assert out.is_dir()

    def test_source_with_no_cron_jobs_json(self, tmp_path):
        source = tmp_path / "no-cron"
        (source / "skills" / "basic").mkdir(parents=True)
        (source / "skills" / "basic" / "SKILL.md").write_text(
            "---\nname: basic\ndescription: Basic skill\n---\n\nHello.\n",
            encoding="utf-8",
        )
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(source, out)
        assert result.cron_jobs_total == 0
        assert result.skills_migrated == 1

    def test_no_memory_md_still_works(self, tmp_path):
        source = tmp_path / "no-memory"
        source.mkdir()
        out = tmp_path / "migration-out"
        result = migrate_openclaw_to_nemoclaw(source, out)
        assert not (out / "workspace" / "MEMORY.md").exists()
        assert result.errors == []


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestMigratorCLI:
    def test_cli_migrate_exits_0(self, openclaw_source, tmp_path):
        from typer.testing import CliRunner

        from agentshift.cli import app

        runner = CliRunner()
        out = tmp_path / "cli-out"
        result = runner.invoke(
            app,
            [
                "migrate",
                "--source",
                str(openclaw_source),
                "--from",
                "openclaw",
                "--to",
                "nemoclaw",
                "--cloud",
                "docker",
                "--output",
                str(out),
            ],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Real ~/.openclaw (skipped if not installed)
# ---------------------------------------------------------------------------


class TestMigratorRealOpenClaw:
    _OPENCLAW_DIR = Path.home() / ".openclaw"

    def test_full_migration_real_openclaw(self, tmp_path):
        if not self._OPENCLAW_DIR.exists():
            pytest.skip("~/.openclaw not installed")
        out = tmp_path / "real-migration"
        result = migrate_openclaw_to_nemoclaw(self._OPENCLAW_DIR, out, cloud="docker")
        assert out.is_dir()
        assert (out / "MIGRATION_REPORT.md").exists()
        assert result.skills_total >= 0
