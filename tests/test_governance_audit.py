"""T15 — Audit engine tests.

Tests for:
- GPR-L1/L2/L3 scoring formulas
- Overall GPR calculation
- CFS (Conversion Fidelity Score)
- Elevation tracking — decisions logged correctly
- CSV export format and column headers
- JSON export structure
- Edge cases: zero tools, all guardrails denied, perfect scores
"""

from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

import pytest

from agentshift.elevation import (
    PLATFORM_L2_CAPABILITIES,
    PLATFORM_L3_CAPABILITIES,
    ElevatedArtifact,
    ElevationResult,
    elevate_governance,
)
from agentshift.governance_audit import (
    GovernanceAudit,
    audit_batch,
    audit_conversion,
    export_csv,
    export_json,
)
from agentshift.ir import (
    AgentIR,
    Governance,
    Guardrail,
    PlatformAnnotation,
    ToolPermission,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_ir(
    *,
    name: str = "test-agent",
    description: str = "Test agent",
    guardrails: list[Guardrail] | None = None,
    tool_permissions: list[ToolPermission] | None = None,
    platform_annotations: list[PlatformAnnotation] | None = None,
) -> AgentIR:
    """Create an AgentIR with given governance layers."""
    gov = Governance(
        guardrails=guardrails or [],
        tool_permissions=tool_permissions or [],
        platform_annotations=platform_annotations or [],
    )
    return AgentIR(name=name, description=description, governance=gov)


def _safety_guardrail(n: int = 1) -> list[Guardrail]:
    return [Guardrail(id=f"g{i}", text=f"Safety rule {i}", category="safety") for i in range(n)]


def _bedrock_annotation(n: int = 1) -> list[PlatformAnnotation]:
    return [
        PlatformAnnotation(
            id=f"cf{i}",
            kind="content_filter",
            description=f"Content filter {i}",
            platform_target="bedrock",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# GPR-L1 scoring
# ---------------------------------------------------------------------------


class TestGPRL1:
    """GPR-L1: proportion of L1 guardrails preserved.

    Formula (from spec / audit code):
      GPR-L1 = l1_preserved / l1_total   (if l1_total > 0)
      GPR-L1 = 1.0                        (if l1_total == 0)

    All L1 guardrails are ALWAYS preserved — they become prompt text on every platform.
    """

    def test_gpr_l1_all_preserved(self):
        """5 guardrails → all 5 preserved → GPR-L1 = 1.0"""
        ir = _make_ir(guardrails=_safety_guardrail(5))
        audit = audit_conversion(ir, "copilot")
        assert audit.l1_total == 5
        assert audit.l1_preserved == 5
        assert audit.gpr_l1 == pytest.approx(1.0)

    def test_gpr_l1_single_guardrail(self):
        ir = _make_ir(guardrails=_safety_guardrail(1))
        audit = audit_conversion(ir, "claude-code")
        assert audit.l1_total == 1
        assert audit.l1_preserved == 1
        assert audit.gpr_l1 == pytest.approx(1.0)

    def test_gpr_l1_zero_guardrails_returns_one(self):
        """When there are no guardrails, GPR-L1 defaults to 1.0 (nothing to lose)."""
        ir = _make_ir()
        audit = audit_conversion(ir, "bedrock")
        assert audit.l1_total == 0
        assert audit.gpr_l1 == pytest.approx(1.0)

    def test_gpr_l1_platform_does_not_matter(self):
        """L1 guardrails are always preserved regardless of platform."""
        ir = _make_ir(guardrails=_safety_guardrail(3))
        for target in ["claude-code", "copilot", "bedrock", "vertex"]:
            audit = audit_conversion(ir, target)
            assert audit.gpr_l1 == pytest.approx(1.0), f"Failed for {target}"

    def test_gpr_l1_formula_is_ratio(self):
        """Formula sanity: gpr_l1 = l1_preserved / l1_total."""
        ir = _make_ir(guardrails=_safety_guardrail(7))
        audit = audit_conversion(ir, "copilot")
        expected = audit.l1_preserved / audit.l1_total
        assert audit.gpr_l1 == pytest.approx(expected)


# ---------------------------------------------------------------------------
# GPR-L2 scoring
# ---------------------------------------------------------------------------


class TestGPRL2:
    """GPR-L2: proportion of L2 tool permissions preserved natively.

    Formula:
      GPR-L2 = l2_preserved / l2_total   (if l2_total > 0)
      GPR-L2 = 1.0                        (if l2_total == 0)

    Elevated artifacts count as NOT preserved for GPR-L2.
    Copilot has no L2 capabilities — everything gets elevated.
    Claude-code has deny_list, deny_patterns, allow_list, disabled_tool.
    """

    def test_gpr_l2_zero_permissions_returns_one(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        assert audit.l2_total == 0
        assert audit.gpr_l2 == pytest.approx(1.0)

    def test_gpr_l2_copilot_elevates_all_disabled_tools(self):
        """Copilot has no native tool permissions — all get elevated → GPR-L2 = 0.0"""
        ir = _make_ir(
            tool_permissions=[
                ToolPermission(tool_name="shell", enabled=False),
                ToolPermission(tool_name="file", enabled=False),
            ]
        )
        audit = audit_conversion(ir, "copilot")
        assert audit.l2_total == 2
        assert audit.l2_preserved == 0
        assert audit.l2_elevated == 2
        assert audit.gpr_l2 == pytest.approx(0.0)

    def test_gpr_l2_bedrock_preserves_disabled_tool(self):
        """Bedrock supports 'disabled_tool' → disabling a tool is preserved."""
        ir = _make_ir(
            tool_permissions=[
                ToolPermission(tool_name="exec", enabled=False),
            ]
        )
        audit = audit_conversion(ir, "bedrock")
        assert audit.l2_preserved == 1
        assert audit.l2_elevated == 0
        assert audit.gpr_l2 == pytest.approx(1.0)

    def test_gpr_l2_rate_limit_always_elevated(self):
        """Rate limits are always elevated (no platform supports them natively)."""
        ir = _make_ir(
            tool_permissions=[
                ToolPermission(tool_name="api_call", rate_limit="10/min"),
            ]
        )
        for target in ["claude-code", "copilot", "bedrock", "vertex"]:
            audit = audit_conversion(ir, target)
            assert audit.gpr_l2 == pytest.approx(0.0), f"Expected elevation on {target}"

    def test_gpr_l2_formula_ratio(self):
        """gpr_l2 = l2_preserved / l2_total when l2_total > 0."""
        ir = _make_ir(
            tool_permissions=[
                ToolPermission(tool_name="exec", enabled=False),  # bedrock preserves this
                ToolPermission(tool_name="shell", rate_limit="5/min"),  # always elevated
            ]
        )
        audit = audit_conversion(ir, "bedrock")
        assert audit.l2_total == 2
        expected = audit.l2_preserved / audit.l2_total
        assert audit.gpr_l2 == pytest.approx(expected)

    def test_gpr_l2_counts_match(self):
        """l2_preserved + l2_elevated == l2_total (accounting invariant)."""
        ir = _make_ir(
            tool_permissions=[
                ToolPermission(tool_name="exec", enabled=False),
                ToolPermission(tool_name="web", deny_patterns=["*.evil.com"]),
                ToolPermission(tool_name="data", rate_limit="100/hour"),
            ]
        )
        audit = audit_conversion(ir, "bedrock")
        assert audit.l2_preserved + audit.l2_elevated == audit.l2_total


# ---------------------------------------------------------------------------
# GPR-L3 scoring
# ---------------------------------------------------------------------------


class TestGPRL3:
    """GPR-L3: proportion of L3 platform annotations preserved natively.

    Formula:
      GPR-L3 = l3_preserved / l3_total   (if l3_total > 0)
      GPR-L3 = 0.0                        (if l3_total == 0)

    Note: L3 defaults to 0.0 when absent (contrast with L1/L2 which default to 1.0).
    Bedrock supports all four annotation kinds.
    Claude-code supports none.
    """

    def test_gpr_l3_zero_annotations_returns_zero(self):
        """When there are no L3 annotations, GPR-L3 is 0.0 (spec default)."""
        ir = _make_ir()
        audit = audit_conversion(ir, "bedrock")
        assert audit.l3_total == 0
        assert audit.gpr_l3 == pytest.approx(0.0)

    def test_gpr_l3_bedrock_preserves_all_annotation_kinds(self):
        """Bedrock supports all four L3 kinds → all preserved."""
        ir = _make_ir(
            platform_annotations=[
                PlatformAnnotation(id="a1", kind="content_filter", description="cf"),
                PlatformAnnotation(id="a2", kind="pii_detection", description="pii"),
                PlatformAnnotation(id="a3", kind="denied_topics", description="dt"),
                PlatformAnnotation(id="a4", kind="grounding_check", description="gc"),
            ]
        )
        audit = audit_conversion(ir, "bedrock")
        assert audit.l3_total == 4
        assert audit.l3_preserved == 4
        assert audit.gpr_l3 == pytest.approx(1.0)

    def test_gpr_l3_claude_code_elevates_all(self):
        """Claude-code has no L3 support → all annotations elevated."""
        ir = _make_ir(
            platform_annotations=[
                PlatformAnnotation(id="a1", kind="content_filter", description="cf"),
            ]
        )
        audit = audit_conversion(ir, "claude-code")
        assert audit.l3_preserved == 0
        assert audit.l3_elevated == 1
        assert audit.gpr_l3 == pytest.approx(0.0)

    def test_gpr_l3_vertex_preserves_content_filter_and_pii(self):
        """Vertex supports content_filter and pii_detection."""
        ir = _make_ir(
            platform_annotations=[
                PlatformAnnotation(id="a1", kind="content_filter", description="cf"),
                PlatformAnnotation(id="a2", kind="pii_detection", description="pii"),
                PlatformAnnotation(
                    id="a3", kind="denied_topics", description="dt"
                ),  # Not supported
            ]
        )
        audit = audit_conversion(ir, "vertex")
        assert audit.l3_preserved == 2
        assert audit.l3_total == 3
        assert audit.gpr_l3 == pytest.approx(2 / 3)

    def test_gpr_l3_formula_ratio(self):
        """gpr_l3 = l3_preserved / l3_total when l3_total > 0."""
        ir = _make_ir(
            platform_annotations=[
                PlatformAnnotation(id="a1", kind="content_filter", description="cf"),
                PlatformAnnotation(id="a2", kind="content_filter", description="cf2"),
            ]
        )
        audit = audit_conversion(ir, "bedrock")
        expected = audit.l3_preserved / audit.l3_total
        assert audit.gpr_l3 == pytest.approx(expected)

    def test_gpr_l3_copilot_elevates_or_drops_all(self):
        """Copilot has no L3 support — annotations are elevated/dropped."""
        ir = _make_ir(
            platform_annotations=[
                PlatformAnnotation(id="a1", kind="content_filter", description="cf"),
                PlatformAnnotation(id="a2", kind="pii_detection", description="pii"),
            ]
        )
        audit = audit_conversion(ir, "copilot")
        assert audit.l3_preserved == 0
        assert audit.gpr_l3 == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Overall GPR
# ---------------------------------------------------------------------------


class TestGPROverall:
    """GPR-Overall: weighted by artifact count across all three layers.

    Formula:
      total_artifacts = l1_total + l2_total + l3_total
      total_preserved = l1_preserved + l2_preserved + l3_preserved
      gpr_overall = total_preserved / total_artifacts  (if total_artifacts > 0)
      gpr_overall = 1.0                                 (if total_artifacts == 0)
    """

    def test_gpr_overall_no_artifacts_returns_one(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        assert audit.gpr_overall == pytest.approx(1.0)

    def test_gpr_overall_only_l1(self):
        """Only L1 guardrails → overall = L1 rate (= 1.0, always preserved)."""
        ir = _make_ir(guardrails=_safety_guardrail(4))
        audit = audit_conversion(ir, "copilot")
        assert audit.gpr_overall == pytest.approx(1.0)

    def test_gpr_overall_weighted_formula(self):
        """Check the weighted average formula explicitly."""
        ir = _make_ir(
            guardrails=_safety_guardrail(2),  # L1: 2 total, 2 preserved
            tool_permissions=[
                ToolPermission(tool_name="t1", enabled=False),  # L2: depends on platform
            ],
            platform_annotations=[
                PlatformAnnotation(id="a1", kind="content_filter", description="cf"),
            ],
        )
        audit = audit_conversion(ir, "bedrock")
        total_artifacts = audit.l1_total + audit.l2_total + audit.l3_total
        total_preserved = audit.l1_preserved + audit.l2_preserved + audit.l3_preserved
        expected = total_preserved / total_artifacts
        assert audit.gpr_overall == pytest.approx(expected)

    def test_gpr_overall_copilot_penalized(self):
        """Copilot has no L2/L3 support → overall GPR drops when L2/L3 exist."""
        ir = _make_ir(
            guardrails=_safety_guardrail(1),
            tool_permissions=[ToolPermission(tool_name="exec", enabled=False)],
        )
        audit_cp = audit_conversion(ir, "copilot")
        audit_cc = audit_conversion(ir, "claude-code")
        # Claude-code supports disabled_tool, copilot does not
        assert audit_cc.gpr_overall >= audit_cp.gpr_overall

    def test_gpr_overall_perfect_on_bedrock_l1_only(self):
        ir = _make_ir(guardrails=_safety_guardrail(3))
        audit = audit_conversion(ir, "bedrock")
        assert audit.gpr_overall == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# CFS — Conversion Fidelity Score
# ---------------------------------------------------------------------------


class TestCFS:
    """CFS: non-governance fidelity (identity, tools, memory, schema checks).

    Formula:
      cfs = sum([identity, tools_listed, memory_handled, schema_valid]) / 4
    All checks are booleans; a fully valid agent gets CFS = 1.0.
    """

    def test_cfs_perfect_for_valid_agent(self):
        ir = _make_ir(name="good-agent", description="A fully described agent")
        audit = audit_conversion(ir, "copilot")
        assert audit.cfs == pytest.approx(1.0)

    def test_cfs_identity_requires_name_and_description(self):
        """cfs_identity = True when name AND description are present."""
        ir = _make_ir(name="valid-name", description="valid description")
        audit = audit_conversion(ir, "copilot")
        assert audit.cfs_identity is True

    def test_cfs_tools_listed_always_true(self):
        """cfs_tools_listed is always True (len >= 0 is always true)."""
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        assert audit.cfs_tools_listed is True

    def test_cfs_memory_handled_always_true(self):
        """Memory is explicitly not converted (documented behavior)."""
        ir = _make_ir()
        audit = audit_conversion(ir, "bedrock")
        assert audit.cfs_memory_handled is True

    def test_cfs_schema_valid_always_true(self):
        """Schema validity is assumed True (validate command checks separately)."""
        ir = _make_ir()
        audit = audit_conversion(ir, "vertex")
        assert audit.cfs_schema_valid is True

    def test_cfs_formula_ratio(self):
        """cfs = checked_true_count / 4"""
        ir = _make_ir(name="agent", description="desc")
        audit = audit_conversion(ir, "copilot")
        checks = [
            audit.cfs_identity,
            audit.cfs_tools_listed,
            audit.cfs_memory_handled,
            audit.cfs_schema_valid,
        ]
        expected = sum(checks) / len(checks)
        assert audit.cfs == pytest.approx(expected)

    def test_cfs_is_between_zero_and_one(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        assert 0.0 <= audit.cfs <= 1.0


# ---------------------------------------------------------------------------
# Elevation tracking
# ---------------------------------------------------------------------------


class TestElevationTracking:
    """Elevation: L2/L3 artifacts promoted to L1 when platform lacks native support."""

    def test_disabled_tool_elevated_on_copilot(self):
        """Copilot has no disable mechanism — disabled tool should be elevated."""
        ir = _make_ir(tool_permissions=[ToolPermission(tool_name="shell", enabled=False)])
        audit = audit_conversion(ir, "copilot")
        assert audit.l2_elevated == 1
        assert len(audit.elevated_artifacts) >= 1
        artifact = audit.elevated_artifacts[0]
        assert artifact["source_layer"] == "L2"
        assert artifact["artifact_type"] == "disabled_tool"

    def test_deny_patterns_elevated_on_copilot(self):
        ir = _make_ir(
            tool_permissions=[ToolPermission(tool_name="exec", deny_patterns=["rm -rf", "sudo"])]
        )
        audit = audit_conversion(ir, "copilot")
        assert len(audit.elevated_artifacts) >= 2
        types = [a["artifact_type"] for a in audit.elevated_artifacts]
        assert "deny_pattern" in types

    def test_rate_limit_elevated_everywhere(self):
        """Rate limits should always be elevated."""
        ir = _make_ir(
            tool_permissions=[ToolPermission(tool_name="web_search", rate_limit="5/minute")]
        )
        for target in ["claude-code", "copilot", "bedrock", "vertex"]:
            audit = audit_conversion(ir, target)
            types = [a["artifact_type"] for a in audit.elevated_artifacts]
            assert "rate_limit" in types, f"rate_limit not elevated for {target}"

    def test_l3_annotation_elevated_on_claude_code(self):
        ir = _make_ir(
            platform_annotations=[
                PlatformAnnotation(id="cf1", kind="content_filter", description="Block harmful")
            ]
        )
        audit = audit_conversion(ir, "claude-code")
        assert audit.l3_elevated == 1
        artifact = audit.elevated_artifacts[0]
        assert artifact["source_layer"] == "L3"
        assert artifact["artifact_type"] == "content_filter"

    def test_l3_annotation_preserved_on_bedrock(self):
        ir = _make_ir(
            platform_annotations=[
                PlatformAnnotation(id="cf1", kind="content_filter", description="Block harmful")
            ]
        )
        audit = audit_conversion(ir, "bedrock")
        assert audit.l3_preserved == 1
        assert audit.l3_elevated == 0
        assert len(audit.elevated_artifacts) == 0

    def test_elevated_artifact_has_required_keys(self):
        ir = _make_ir(tool_permissions=[ToolPermission(tool_name="shell", enabled=False)])
        audit = audit_conversion(ir, "copilot")
        assert len(audit.elevated_artifacts) > 0
        ea = audit.elevated_artifacts[0]
        required_keys = {
            "source_layer",
            "artifact_id",
            "artifact_type",
            "original_text",
            "elevated_instruction",
            "reason",
        }
        assert required_keys.issubset(ea.keys())

    def test_elevated_instruction_is_nonempty(self):
        ir = _make_ir(tool_permissions=[ToolPermission(tool_name="exec", rate_limit="1/hour")])
        audit = audit_conversion(ir, "copilot")
        for ea in audit.elevated_artifacts:
            assert ea["elevated_instruction"], "elevated_instruction should not be empty"

    def test_allow_pattern_elevated_on_unsupported_platform(self):
        """Allow patterns are elevated on platforms without allow_list support (e.g., bedrock)."""
        ir = _make_ir(
            tool_permissions=[
                ToolPermission(tool_name="read_file", allow_patterns=["/workspace/*"])
            ]
        )
        audit = audit_conversion(ir, "bedrock")
        types = [a["artifact_type"] for a in audit.elevated_artifacts]
        assert "allow_pattern" in types

    def test_no_elevation_on_claude_code_with_deny_patterns(self):
        """Claude-code supports deny_patterns → no elevation needed."""
        ir = _make_ir(tool_permissions=[ToolPermission(tool_name="exec", deny_patterns=["rm -rf"])])
        audit = audit_conversion(ir, "claude-code")
        types = [a["artifact_type"] for a in audit.elevated_artifacts]
        assert "deny_pattern" not in types


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


class TestCSVExport:
    """Tests for export_csv: format, column headers, row data."""

    EXPECTED_HEADERS = [
        "Agent",
        "Target",
        "Domain",
        "Complexity",
        "L1 Total",
        "L1 Preserved",
        "GPR-L1",
        "L2 Total",
        "L2 Preserved",
        "L2 Elevated",
        "GPR-L2",
        "L3 Total",
        "L3 Preserved",
        "GPR-L3",
        "GPR-Overall",
        "CFS",
    ]

    def test_csv_headers_match_spec(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot", agent_id="agent-1")
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "results.csv"
            export_csv([audit], csv_path)
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                assert reader.fieldnames == self.EXPECTED_HEADERS

    def test_csv_creates_file(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "output.csv"
            export_csv([audit], csv_path)
            assert csv_path.exists()

    def test_csv_creates_parent_directories(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "nested" / "deep" / "results.csv"
            export_csv([audit], csv_path)
            assert csv_path.exists()

    def test_csv_single_row_values(self):
        ir = _make_ir(
            name="my-agent",
            guardrails=_safety_guardrail(2),
        )
        audit = audit_conversion(
            ir, "copilot", agent_id="my-agent", domain="test", complexity="low"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "r.csv"
            export_csv([audit], csv_path)
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 1
            row = rows[0]
            assert row["Agent"] == "my-agent"
            assert row["Target"] == "copilot"
            assert row["Domain"] == "test"
            assert row["Complexity"] == "low"
            assert row["L1 Total"] == "2"
            assert row["L1 Preserved"] == "2"
            assert float(row["GPR-L1"]) == pytest.approx(1.0)

    def test_csv_multiple_rows(self):
        ir1 = _make_ir(name="agent-1")
        ir2 = _make_ir(name="agent-2")
        audits = [
            audit_conversion(ir1, "copilot"),
            audit_conversion(ir2, "bedrock"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "r.csv"
            export_csv(audits, csv_path)
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 2

    def test_csv_gpr_values_formatted_to_four_decimals(self):
        ir = _make_ir(guardrails=_safety_guardrail(3))
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "r.csv"
            export_csv([audit], csv_path)
            with csv_path.open() as f:
                reader = csv.DictReader(f)
                row = next(reader)
            # Values should be formatted as floats with 4 decimal places
            gpr_l1 = row["GPR-L1"]
            assert "." in gpr_l1
            decimal_places = len(gpr_l1.split(".")[1])
            assert decimal_places == 4

    def test_csv_empty_audit_list(self):
        """Exporting empty list produces header-only CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "empty.csv"
            export_csv([], csv_path)
            with csv_path.open() as f:
                content = f.read()
            lines = [l for l in content.strip().splitlines() if l]
            assert len(lines) == 1  # header only


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


class TestJSONExport:
    """Tests for export_json: structure, field presence, nested objects."""

    def test_json_creates_file(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "results.json"
            export_json([audit], json_path)
            assert json_path.exists()

    def test_json_creates_parent_directories(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "a" / "b" / "results.json"
            export_json([audit], json_path)
            assert json_path.exists()

    def test_json_is_valid_json(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "r.json"
            export_json([audit], json_path)
            data = json.loads(json_path.read_text())
            assert isinstance(data, list)

    def test_json_top_level_keys(self):
        ir = _make_ir(name="my-agent", description="test")
        audit = audit_conversion(ir, "bedrock", agent_id="my-agent")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "r.json"
            export_json([audit], json_path)
            data = json.loads(json_path.read_text())
            entry = data[0]
        required_keys = {
            "agent_id",
            "agent_name",
            "target",
            "domain",
            "complexity",
            "l1",
            "l2",
            "l3",
            "gpr_overall",
            "cfs",
            "elevated_artifacts",
        }
        assert required_keys.issubset(entry.keys())

    def test_json_l1_subkeys(self):
        ir = _make_ir(guardrails=_safety_guardrail(2))
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "r.json"
            export_json([audit], json_path)
            data = json.loads(json_path.read_text())
            l1 = data[0]["l1"]
        assert "total" in l1
        assert "preserved" in l1
        assert "gpr" in l1
        assert l1["total"] == 2
        assert l1["preserved"] == 2
        assert l1["gpr"] == pytest.approx(1.0)

    def test_json_l2_subkeys(self):
        ir = _make_ir(tool_permissions=[ToolPermission(tool_name="exec", enabled=False)])
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "r.json"
            export_json([audit], json_path)
            data = json.loads(json_path.read_text())
            l2 = data[0]["l2"]
        assert set(l2.keys()) >= {"total", "preserved", "elevated", "gpr"}

    def test_json_l3_subkeys(self):
        ir = _make_ir(
            platform_annotations=[
                PlatformAnnotation(id="a1", kind="content_filter", description="cf")
            ]
        )
        audit = audit_conversion(ir, "bedrock")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "r.json"
            export_json([audit], json_path)
            data = json.loads(json_path.read_text())
            l3 = data[0]["l3"]
        assert set(l3.keys()) >= {"total", "preserved", "elevated", "dropped", "gpr"}

    def test_json_elevated_artifacts_is_list(self):
        ir = _make_ir(tool_permissions=[ToolPermission(tool_name="shell", enabled=False)])
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "r.json"
            export_json([audit], json_path)
            data = json.loads(json_path.read_text())
            artifacts = data[0]["elevated_artifacts"]
        assert isinstance(artifacts, list)
        assert len(artifacts) >= 1

    def test_json_elevated_artifact_keys(self):
        ir = _make_ir(tool_permissions=[ToolPermission(tool_name="shell", enabled=False)])
        audit = audit_conversion(ir, "copilot")
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "r.json"
            export_json([audit], json_path)
            data = json.loads(json_path.read_text())
            artifact = data[0]["elevated_artifacts"][0]
        required = {
            "source_layer",
            "artifact_id",
            "artifact_type",
            "original_text",
            "elevated_instruction",
            "reason",
        }
        assert required.issubset(artifact.keys())

    def test_json_multiple_entries(self):
        ir1 = _make_ir(name="a1")
        ir2 = _make_ir(name="a2")
        audits = [audit_conversion(ir1, "copilot"), audit_conversion(ir2, "bedrock")]
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "r.json"
            export_json(audits, json_path)
            data = json.loads(json_path.read_text())
        assert len(data) == 2

    def test_json_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "empty.json"
            export_json([], json_path)
            data = json.loads(json_path.read_text())
        assert data == []


# ---------------------------------------------------------------------------
# audit_batch
# ---------------------------------------------------------------------------


class TestAuditBatch:
    """Tests for audit_batch (multi-agent × multi-target)."""

    def test_batch_produces_agents_times_targets(self):
        agents = [(_make_ir(name=f"agent-{i}"), f"agent-{i}", "domain", "low") for i in range(3)]
        targets = ["copilot", "bedrock"]
        audits = audit_batch(agents, targets)
        assert len(audits) == 6  # 3 × 2

    def test_batch_all_targets_represented(self):
        agents = [(_make_ir(name="a1"), "a1", "", "")]
        targets = ["copilot", "bedrock", "claude-code"]
        audits = audit_batch(agents, targets)
        result_targets = {a.target for a in audits}
        assert result_targets == set(targets)

    def test_batch_empty_agents(self):
        audits = audit_batch([], ["copilot"])
        assert audits == []

    def test_batch_empty_targets(self):
        agents = [(_make_ir(name="a"), "a", "", "")]
        audits = audit_batch(agents, [])
        assert audits == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: zero tools, all denied, perfect scores."""

    def test_zero_tools_no_impact_on_governance(self):
        """Having no tools defined doesn't affect governance scores."""
        ir = _make_ir(guardrails=_safety_guardrail(2))
        assert ir.tools == []
        audit = audit_conversion(ir, "copilot")
        assert audit.gpr_l1 == pytest.approx(1.0)
        assert audit.cfs == pytest.approx(1.0)

    def test_all_guardrails_always_preserved(self):
        """L1 is special — all guardrails are ALWAYS preserved (100% rate)."""
        ir = _make_ir(guardrails=_safety_guardrail(10))
        for target in ["claude-code", "copilot", "bedrock", "vertex"]:
            audit = audit_conversion(ir, target)
            assert audit.gpr_l1 == pytest.approx(1.0)

    def test_all_l2_denied_on_copilot(self):
        """On copilot, all tool permissions get elevated → GPR-L2 = 0.0"""
        ir = _make_ir(
            tool_permissions=[
                ToolPermission(tool_name="exec", enabled=False),
                ToolPermission(tool_name="shell", deny_patterns=["rm -rf"]),
            ]
        )
        audit = audit_conversion(ir, "copilot")
        assert audit.gpr_l2 == pytest.approx(0.0)
        assert audit.l2_elevated == audit.l2_total

    def test_perfect_scores_on_bedrock_with_full_governance(self):
        """Bedrock with only L1 + L3 content filters → perfect GPR."""
        ir = _make_ir(
            guardrails=_safety_guardrail(3),
            platform_annotations=[
                PlatformAnnotation(id="cf1", kind="content_filter", description="safety"),
                PlatformAnnotation(id="pii1", kind="pii_detection", description="pii"),
            ],
        )
        audit = audit_conversion(ir, "bedrock")
        assert audit.gpr_l1 == pytest.approx(1.0)
        assert audit.gpr_l3 == pytest.approx(1.0)
        assert audit.cfs == pytest.approx(1.0)

    def test_governance_audit_agent_id_defaults_to_name(self):
        """When agent_id is not provided, it defaults to ir.name."""
        ir = _make_ir(name="my-bot")
        audit = audit_conversion(ir, "copilot")
        assert audit.agent_id == "my-bot"
        assert audit.agent_name == "my-bot"

    def test_governance_audit_agent_id_custom(self):
        ir = _make_ir(name="my-bot")
        audit = audit_conversion(ir, "copilot", agent_id="custom-id")
        assert audit.agent_id == "custom-id"
        assert audit.agent_name == "my-bot"

    def test_governance_audit_domain_and_complexity_stored(self):
        ir = _make_ir()
        audit = audit_conversion(ir, "copilot", domain="healthcare", complexity="high")
        assert audit.domain == "healthcare"
        assert audit.complexity == "high"

    def test_gpr_all_zero_l3_with_l1_present(self):
        """If only L1 and L3 exist, and L3 is all elevated, overall GPR reflects that."""
        ir = _make_ir(
            guardrails=_safety_guardrail(2),
            platform_annotations=[
                PlatformAnnotation(id="x", kind="content_filter", description="filter")
            ],
        )
        audit = audit_conversion(ir, "claude-code")  # no L3 support
        # L1 preserved = 2, L3 preserved = 0
        total = audit.l1_total + audit.l3_total  # 3
        preserved = audit.l1_preserved + audit.l3_preserved  # 2
        assert audit.gpr_overall == pytest.approx(preserved / total)

    def test_elevation_result_target_stored(self):
        """ElevationResult.target should match the requested target platform."""
        ir = _make_ir()
        result = elevate_governance(ir, "bedrock")
        assert result.target == "bedrock"

    def test_elevation_l1_preserved_list_matches_guardrails(self):
        """ElevationResult.l1_preserved should contain all original guardrails."""
        guardrails = _safety_guardrail(3)
        ir = _make_ir(guardrails=guardrails)
        result = elevate_governance(ir, "copilot")
        assert len(result.l1_preserved) == 3
        ids = {g.id for g in result.l1_preserved}
        assert ids == {"g0", "g1", "g2"}
