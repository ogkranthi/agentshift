"""T19 — Registry + drift detection tests.

Tests for agentshift.registry:
- register() → creates registry file, entry persisted
- list_agents() → returns registered agents
- get() → returns entry by name or None
- remove() → removes entry, persists
- diff() → DriftReport with no drift when unchanged
- diff() → DriftReport with drift when IR content changes
- diff() → unregistered agent has registered=False
- export() → valid JSON with all agents
- Registry isolation via tmp_path
"""

from __future__ import annotations

import json
from pathlib import Path

from agentshift.ir import AgentIR, Persona, Tool
from agentshift.registry import DriftChange, DriftReport, Registry, RegistryEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ir_dict(**kwargs) -> dict:
    """Build a minimal IR dict suitable for registry storage."""
    ir = AgentIR(
        name=kwargs.pop("name", "test-agent"),
        description=kwargs.pop("description", "A test agent."),
        persona=Persona(system_prompt=kwargs.pop("system_prompt", "You are a test agent.")),
        **kwargs,
    )
    return ir.model_dump()


def _make_registry(tmp_path: Path) -> Registry:
    """Build a Registry backed by a temp directory."""
    return Registry(registry_dir=tmp_path / "registry")


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for Registry.register()."""

    def test_register_creates_registry_file(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("my-agent", "/path/to/agent", "openclaw", _make_ir_dict())
        assert reg.registry_file.exists()

    def test_register_creates_registry_dir(self, tmp_path):
        reg_dir = tmp_path / "new-registry-dir"
        reg = Registry(registry_dir=reg_dir)
        reg.register("my-agent", "/path/to/agent", "openclaw", _make_ir_dict())
        assert reg_dir.exists()

    def test_register_returns_entry(self, tmp_path):
        reg = _make_registry(tmp_path)
        entry = reg.register("my-agent", "/path/to/agent", "openclaw", _make_ir_dict())
        assert isinstance(entry, RegistryEntry)

    def test_register_entry_has_name(self, tmp_path):
        reg = _make_registry(tmp_path)
        entry = reg.register("test-agent", "/path", "openclaw", _make_ir_dict())
        assert entry.name == "test-agent"

    def test_register_entry_has_source_path(self, tmp_path):
        reg = _make_registry(tmp_path)
        entry = reg.register("my-agent", "/some/path", "openclaw", _make_ir_dict())
        assert entry.source_path == "/some/path"

    def test_register_entry_has_platform(self, tmp_path):
        reg = _make_registry(tmp_path)
        entry = reg.register("my-agent", "/path", "copilot", _make_ir_dict())
        assert entry.platform == "copilot"

    def test_register_entry_has_content_hash(self, tmp_path):
        reg = _make_registry(tmp_path)
        entry = reg.register("my-agent", "/path", "openclaw", _make_ir_dict())
        assert entry.content_hash
        assert len(entry.content_hash) > 0

    def test_register_entry_has_registered_at(self, tmp_path):
        reg = _make_registry(tmp_path)
        entry = reg.register("my-agent", "/path", "openclaw", _make_ir_dict())
        assert entry.registered_at
        # Should be ISO 8601 format
        assert "T" in entry.registered_at

    def test_register_entry_has_ir_snapshot(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(name="snapshot-agent")
        entry = reg.register("snapshot-agent", "/path", "openclaw", ir_dict)
        assert entry.ir_snapshot is not None
        assert entry.ir_snapshot["name"] == "snapshot-agent"

    def test_register_persists_to_json_file(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("persisted-agent", "/path", "openclaw", _make_ir_dict())

        # Read raw file and verify
        raw = json.loads(reg.registry_file.read_text())
        assert "agents" in raw
        assert "persisted-agent" in raw["agents"]

    def test_register_updates_existing_agent(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("dup-agent", "/path", "openclaw", _make_ir_dict(name="dup-agent"))
        updated_dict = _make_ir_dict(name="dup-agent", description="Updated description.")
        reg.register("dup-agent", "/path", "openclaw", updated_dict)

        entry = reg.get("dup-agent")
        assert entry.ir_snapshot["description"] == "Updated description."

    def test_register_multiple_agents(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("agent-a", "/a", "openclaw", _make_ir_dict(name="agent-a"))
        reg.register("agent-b", "/b", "copilot", _make_ir_dict(name="agent-b"))

        assert reg.get("agent-a") is not None
        assert reg.get("agent-b") is not None


# ---------------------------------------------------------------------------
# List agents
# ---------------------------------------------------------------------------


class TestListAgents:
    """Tests for Registry.list_agents()."""

    def test_empty_registry_returns_empty_list(self, tmp_path):
        reg = _make_registry(tmp_path)
        assert reg.list_agents() == []

    def test_list_returns_registered_agents(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("agent-1", "/p1", "openclaw", _make_ir_dict(name="agent-1"))
        reg.register("agent-2", "/p2", "openclaw", _make_ir_dict(name="agent-2"))

        agents = reg.list_agents()
        assert len(agents) == 2

    def test_list_returns_registry_entries(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("my-agent", "/p", "openclaw", _make_ir_dict())

        agents = reg.list_agents()
        assert all(isinstance(a, RegistryEntry) for a in agents)

    def test_list_contains_correct_names(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("alpha", "/a", "openclaw", _make_ir_dict(name="alpha"))
        reg.register("beta", "/b", "copilot", _make_ir_dict(name="beta"))

        names = {a.name for a in reg.list_agents()}
        assert "alpha" in names
        assert "beta" in names

    def test_list_persists_across_registry_instances(self, tmp_path):
        """Registry loaded from same dir should see previously registered agents."""
        reg_dir = tmp_path / "shared-registry"
        reg1 = Registry(registry_dir=reg_dir)
        reg1.register("agent-x", "/x", "openclaw", _make_ir_dict(name="agent-x"))

        # New instance reads the same file
        reg2 = Registry(registry_dir=reg_dir)
        agents = reg2.list_agents()
        names = {a.name for a in agents}
        assert "agent-x" in names


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


class TestGet:
    """Tests for Registry.get()."""

    def test_get_registered_agent(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("fetch-me", "/path", "openclaw", _make_ir_dict(name="fetch-me"))
        entry = reg.get("fetch-me")
        assert entry is not None
        assert entry.name == "fetch-me"

    def test_get_unregistered_agent_returns_none(self, tmp_path):
        reg = _make_registry(tmp_path)
        assert reg.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


class TestRemove:
    """Tests for Registry.remove()."""

    def test_remove_registered_agent_returns_true(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("rm-me", "/path", "openclaw", _make_ir_dict())
        result = reg.remove("rm-me")
        assert result is True

    def test_remove_unregistered_returns_false(self, tmp_path):
        reg = _make_registry(tmp_path)
        assert reg.remove("ghost") is False

    def test_remove_deletes_entry(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("delete-me", "/path", "openclaw", _make_ir_dict())
        reg.remove("delete-me")
        assert reg.get("delete-me") is None

    def test_remove_persists(self, tmp_path):
        reg_dir = tmp_path / "reg"
        reg = Registry(registry_dir=reg_dir)
        reg.register("remove-persist", "/p", "openclaw", _make_ir_dict(name="remove-persist"))
        reg.remove("remove-persist")

        reg2 = Registry(registry_dir=reg_dir)
        assert reg2.get("remove-persist") is None


# ---------------------------------------------------------------------------
# Diff (no drift)
# ---------------------------------------------------------------------------


class TestDiffNoDrift:
    """Tests for Registry.diff() when nothing has changed."""

    def test_no_drift_when_unchanged(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(name="stable-agent")
        reg.register("stable-agent", "/path", "openclaw", ir_dict)

        report = reg.diff("stable-agent", ir_dict)
        assert isinstance(report, DriftReport)
        assert report.has_drift is False

    def test_no_drift_report_has_empty_changes(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict()
        reg.register("stable", "/path", "openclaw", ir_dict)

        report = reg.diff("stable", ir_dict)
        assert report.changes == []

    def test_no_drift_registered_is_true(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict()
        reg.register("stable", "/path", "openclaw", ir_dict)

        report = reg.diff("stable", ir_dict)
        assert report.registered is True

    def test_diff_ignores_metadata_changes(self, tmp_path):
        """Metadata fields are volatile; changing them should not trigger drift."""
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(name="meta-stable")
        reg.register("meta-stable", "/path", "openclaw", ir_dict)

        # Create a copy with modified metadata (source_file changed)
        from agentshift.ir import AgentIR, Persona

        ir = AgentIR(
            name="meta-stable",
            description="A test agent.",
            persona=Persona(system_prompt="You are a test agent."),
        )
        ir_dict2 = ir.model_dump()
        ir_dict2["metadata"]["source_file"] = "different-file.md"

        report = reg.diff("meta-stable", ir_dict2)
        # Metadata is excluded from hash — should show no drift
        assert report.has_drift is False


# ---------------------------------------------------------------------------
# Diff (drift detected)
# ---------------------------------------------------------------------------


class TestDiffWithDrift:
    """Tests for Registry.diff() when content has changed."""

    def test_drift_detected_on_description_change(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(name="drifter", description="Original description.")
        reg.register("drifter", "/path", "openclaw", ir_dict)

        changed_dict = _make_ir_dict(name="drifter", description="Changed description.")
        report = reg.diff("drifter", changed_dict)
        assert report.has_drift is True

    def test_drift_detected_on_system_prompt_change(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(system_prompt="You are assistant A.")
        reg.register("prompt-drifter", "/path", "openclaw", ir_dict)

        changed = _make_ir_dict(system_prompt="You are assistant B.")
        report = reg.diff("prompt-drifter", changed)
        assert report.has_drift is True

    def test_drift_report_has_changes(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(description="Original.")
        reg.register("changer", "/path", "openclaw", ir_dict)

        changed = _make_ir_dict(description="Changed.")
        report = reg.diff("changer", changed)
        assert len(report.changes) > 0

    def test_drift_changes_are_drift_change_instances(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(description="Before.")
        reg.register("dc-agent", "/path", "openclaw", ir_dict)

        report = reg.diff("dc-agent", _make_ir_dict(description="After."))
        assert all(isinstance(c, DriftChange) for c in report.changes)

    def test_drift_change_kind_is_modified(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(description="Old.")
        reg.register("mod-agent", "/path", "openclaw", ir_dict)

        report = reg.diff("mod-agent", _make_ir_dict(description="New."))
        modified = [c for c in report.changes if c.kind == "modified"]
        assert len(modified) >= 1

    def test_drift_on_tool_addition(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict()
        reg.register("tool-drifter", "/path", "openclaw", ir_dict)

        ir_with_tool = AgentIR(
            name="test-agent",
            description="A test agent.",
            persona=Persona(system_prompt="You are a test agent."),
            tools=[Tool(name="bash", description="Run shell commands", kind="shell")],
        )
        report = reg.diff("tool-drifter", ir_with_tool.model_dump())
        assert report.has_drift is True

    def test_drift_registered_is_true_when_drifted(self, tmp_path):
        reg = _make_registry(tmp_path)
        ir_dict = _make_ir_dict(description="A.")
        reg.register("drift-reg", "/path", "openclaw", ir_dict)

        report = reg.diff("drift-reg", _make_ir_dict(description="B."))
        assert report.registered is True

    def test_skill_md_content_change_triggers_drift(self, tmp_path):
        """Simulated SKILL.md content change: system_prompt changes → drift detected."""
        reg = _make_registry(tmp_path)
        original = _make_ir_dict(system_prompt="Original SKILL.md content.")
        reg.register("skill-agent", "/agent/dir", "openclaw", original)

        updated = _make_ir_dict(system_prompt="Updated SKILL.md content with new section.")
        report = reg.diff("skill-agent", updated)

        assert report.has_drift is True
        assert len(report.changes) >= 1


# ---------------------------------------------------------------------------
# Diff (unregistered agent)
# ---------------------------------------------------------------------------


class TestDiffUnregistered:
    """Tests for Registry.diff() on unregistered agents."""

    def test_unregistered_agent_has_registered_false(self, tmp_path):
        reg = _make_registry(tmp_path)
        report = reg.diff("never-registered", _make_ir_dict())
        assert report.registered is False

    def test_unregistered_agent_no_drift(self, tmp_path):
        reg = _make_registry(tmp_path)
        report = reg.diff("never-registered", _make_ir_dict())
        assert report.has_drift is False

    def test_unregistered_agent_empty_changes(self, tmp_path):
        reg = _make_registry(tmp_path)
        report = reg.diff("never-registered", _make_ir_dict())
        assert report.changes == []

    def test_unregistered_report_has_name(self, tmp_path):
        reg = _make_registry(tmp_path)
        report = reg.diff("ghost-agent", _make_ir_dict())
        assert report.name == "ghost-agent"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    """Tests for Registry.export()."""

    def test_export_returns_string(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("a", "/p", "openclaw", _make_ir_dict(name="a"))
        result = reg.export()
        assert isinstance(result, str)

    def test_export_is_valid_json(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("b", "/p", "openclaw", _make_ir_dict(name="b"))
        result = reg.export()
        parsed = json.loads(result)  # Should not raise
        assert isinstance(parsed, dict)

    def test_export_contains_version(self, tmp_path):
        reg = _make_registry(tmp_path)
        result = json.loads(reg.export())
        assert "version" in result
        assert result["version"] == "1.0"

    def test_export_contains_agents(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("export-agent", "/p", "openclaw", _make_ir_dict(name="export-agent"))
        result = json.loads(reg.export())
        assert "agents" in result
        assert "export-agent" in result["agents"]

    def test_export_contains_agent_count(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("c1", "/p1", "openclaw", _make_ir_dict(name="c1"))
        reg.register("c2", "/p2", "openclaw", _make_ir_dict(name="c2"))
        result = json.loads(reg.export())
        assert "agent_count" in result
        assert result["agent_count"] == 2

    def test_export_contains_exported_at(self, tmp_path):
        reg = _make_registry(tmp_path)
        result = json.loads(reg.export())
        assert "exported_at" in result
        # Should be ISO 8601
        assert "T" in result["exported_at"]

    def test_export_empty_registry(self, tmp_path):
        reg = _make_registry(tmp_path)
        result = json.loads(reg.export())
        assert result["agent_count"] == 0
        assert result["agents"] == {}

    def test_export_all_entries_have_required_fields(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("full-agent", "/full/path", "bedrock", _make_ir_dict(name="full-agent"))
        result = json.loads(reg.export())
        entry = result["agents"]["full-agent"]

        for field in (
            "name",
            "source_path",
            "platform",
            "ir_snapshot",
            "registered_at",
            "content_hash",
        ):
            assert field in entry, f"Entry missing field {field!r}"

    def test_export_multi_agent_all_included(self, tmp_path):
        reg = _make_registry(tmp_path)
        for i in range(5):
            reg.register(f"agent-{i}", f"/path/{i}", "openclaw", _make_ir_dict(name=f"agent-{i}"))

        result = json.loads(reg.export())
        assert result["agent_count"] == 5
        for i in range(5):
            assert f"agent-{i}" in result["agents"]


# ---------------------------------------------------------------------------
# RegistryEntry serialization
# ---------------------------------------------------------------------------


class TestRegistryEntrySerialization:
    """Tests for RegistryEntry.to_dict() / from_dict()."""

    def test_to_dict_round_trip(self, tmp_path):
        reg = _make_registry(tmp_path)
        entry = reg.register("serial", "/path", "openclaw", _make_ir_dict(name="serial"))
        d = entry.to_dict()
        restored = RegistryEntry.from_dict(d)

        assert restored.name == entry.name
        assert restored.source_path == entry.source_path
        assert restored.platform == entry.platform
        assert restored.content_hash == entry.content_hash
        assert restored.registered_at == entry.registered_at

    def test_to_dict_contains_all_fields(self, tmp_path):
        reg = _make_registry(tmp_path)
        entry = reg.register("fields-check", "/p", "vertex", _make_ir_dict())
        d = entry.to_dict()
        for key in (
            "name",
            "source_path",
            "platform",
            "ir_snapshot",
            "registered_at",
            "content_hash",
        ):
            assert key in d

    def test_registry_file_has_version_field(self, tmp_path):
        reg = _make_registry(tmp_path)
        reg.register("v-agent", "/p", "openclaw", _make_ir_dict())
        raw = json.loads(reg.registry_file.read_text())
        assert raw.get("version") == "1.0"


# ---------------------------------------------------------------------------
# Resilience: corrupt / missing registry file
# ---------------------------------------------------------------------------


class TestResilience:
    """Registry should recover gracefully from corrupt or missing files."""

    def test_missing_registry_file_starts_empty(self, tmp_path):
        reg = _make_registry(tmp_path)
        assert reg.list_agents() == []

    def test_corrupt_json_starts_empty(self, tmp_path):
        reg_dir = tmp_path / "corrupt-reg"
        reg_dir.mkdir()
        (reg_dir / "registry.json").write_text("{not valid json}")
        reg = Registry(registry_dir=reg_dir)
        assert reg.list_agents() == []

    def test_register_after_corrupt_works(self, tmp_path):
        reg_dir = tmp_path / "corrupt-reg2"
        reg_dir.mkdir()
        (reg_dir / "registry.json").write_text("INVALID")
        reg = Registry(registry_dir=reg_dir)
        entry = reg.register("recovery", "/p", "openclaw", _make_ir_dict(name="recovery"))
        assert entry.name == "recovery"
        assert reg.get("recovery") is not None
