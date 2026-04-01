"""AgentShift output validators — per-platform schema validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

console = Console()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    is_warning: bool = False


@dataclass
class ValidationReport:
    platform: str
    output_dir: Path
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def errors(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and not c.is_warning]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed and c.is_warning]

    @property
    def passed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.passed]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Platform validators
# ---------------------------------------------------------------------------


def _validate_claude_code(output_dir: Path) -> ValidationReport:
    report = ValidationReport(platform="claude-code", output_dir=output_dir)

    # CLAUDE.md exists and non-empty
    claude_md = output_dir / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8").strip()
        if content:
            report.checks.append(
                CheckResult("CLAUDE.md exists and non-empty", True, "")
            )
        else:
            report.checks.append(
                CheckResult("CLAUDE.md non-empty", False, "CLAUDE.md is empty")
            )
    else:
        report.checks.append(
            CheckResult("CLAUDE.md exists", False, "CLAUDE.md not found")
        )

    # settings.json exists and valid JSON
    settings_path = output_dir / "settings.json"
    settings: dict[str, Any] | None = None
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            report.checks.append(CheckResult("settings.json valid JSON", True, ""))
        except json.JSONDecodeError as e:
            report.checks.append(
                CheckResult("settings.json valid JSON", False, f"JSON parse error: {e}")
            )
    else:
        report.checks.append(
            CheckResult("settings.json exists", False, "settings.json not found")
        )

    if settings is not None:
        # has "permissions" key
        if "permissions" in settings:
            report.checks.append(
                CheckResult("settings.json has 'permissions'", True, "")
            )
        else:
            report.checks.append(
                CheckResult(
                    "settings.json has 'permissions'",
                    False,
                    "Missing 'permissions' key in settings.json",
                )
            )

        # permissions.allow is a list (if present)
        perms = settings.get("permissions", {})
        if isinstance(perms, dict) and "allow" in perms:
            allow = perms["allow"]
            if isinstance(allow, list):
                report.checks.append(
                    CheckResult("permissions.allow is a list", True, "")
                )
                # warn if Bash(*) is present — too broad
                if "Bash(*)" in allow:
                    report.checks.append(
                        CheckResult(
                            "permissions.allow no Bash(*)",
                            False,
                            "Allow entry 'Bash(*)' is too broad — consider scoping Bash permissions",
                            is_warning=True,
                        )
                    )
            else:
                report.checks.append(
                    CheckResult(
                        "permissions.allow is a list",
                        False,
                        f"permissions.allow must be a list, got {type(allow).__name__}",
                    )
                )

    return report


def _validate_copilot(output_dir: Path) -> ValidationReport:
    report = ValidationReport(platform="copilot", output_dir=output_dir)

    # <name>.agent.md exists
    agent_md_files = list(output_dir.glob("*.agent.md"))
    if not agent_md_files:
        report.checks.append(
            CheckResult(
                "*.agent.md exists",
                False,
                "No *.agent.md file found in output directory",
            )
        )
        return report

    report.checks.append(CheckResult("*.agent.md exists", True, ""))
    agent_md = agent_md_files[0]

    # Parse YAML frontmatter
    raw = agent_md.read_text(encoding="utf-8")
    frontmatter: dict[str, Any] | None = None

    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            try:
                frontmatter = yaml.safe_load(raw[3:end]) or {}
                report.checks.append(CheckResult("YAML frontmatter valid", True, ""))
            except yaml.YAMLError as e:
                report.checks.append(
                    CheckResult(
                        "YAML frontmatter valid", False, f"YAML parse error: {e}"
                    )
                )
        else:
            report.checks.append(
                CheckResult(
                    "YAML frontmatter valid",
                    False,
                    "Frontmatter closing '---' not found",
                )
            )
    else:
        report.checks.append(
            CheckResult(
                "YAML frontmatter present",
                False,
                "No YAML frontmatter found in .agent.md",
            )
        )

    if frontmatter is not None:
        # required keys: name, description, model (list), tools (list)
        for key in ("name", "description", "model", "tools"):
            if key in frontmatter:
                report.checks.append(CheckResult(f"frontmatter has '{key}'", True, ""))
            else:
                report.checks.append(
                    CheckResult(
                        f"frontmatter has '{key}'",
                        False,
                        f"Missing required frontmatter key: '{key}'",
                    )
                )

        # model must be a non-empty list
        model = frontmatter.get("model")
        if isinstance(model, list):
            if model:
                report.checks.append(CheckResult("model list non-empty", True, ""))
            else:
                report.checks.append(
                    CheckResult("model list non-empty", False, "model list is empty")
                )
        elif model is not None:
            report.checks.append(
                CheckResult(
                    "model is a list",
                    False,
                    f"model must be a list, got {type(model).__name__}",
                )
            )

        # tools must be a list
        tools = frontmatter.get("tools")
        if tools is not None and not isinstance(tools, list):
            report.checks.append(
                CheckResult(
                    "tools is a list",
                    False,
                    f"tools must be a list, got {type(tools).__name__}",
                )
            )

        # description must be a non-empty string
        desc = frontmatter.get("description")
        if isinstance(desc, str):
            if desc.strip():
                report.checks.append(CheckResult("description non-empty", True, ""))
            else:
                report.checks.append(
                    CheckResult(
                        "description non-empty", False, "description is empty string"
                    )
                )
        elif desc is not None:
            report.checks.append(
                CheckResult(
                    "description is string",
                    False,
                    f"description must be a string, got {type(desc).__name__}",
                )
            )

    return report


def _validate_bedrock(output_dir: Path) -> ValidationReport:
    report = ValidationReport(platform="bedrock", output_dir=output_dir)

    # instruction.txt exists and length <= 4000
    instr_path = output_dir / "instruction.txt"
    if instr_path.exists():
        report.checks.append(CheckResult("instruction.txt exists", True, ""))
        content = instr_path.read_text(encoding="utf-8")
        if len(content) <= 4000:
            report.checks.append(
                CheckResult("instruction.txt length <= 4000", True, "")
            )
        else:
            report.checks.append(
                CheckResult(
                    "instruction.txt length <= 4000",
                    False,
                    f"instruction.txt is {len(content)} chars, exceeds 4000 char limit",
                )
            )
    else:
        report.checks.append(
            CheckResult("instruction.txt exists", False, "instruction.txt not found")
        )

    # openapi.json exists and valid JSON with required keys
    openapi_path = output_dir / "openapi.json"
    openapi: dict[str, Any] | None = None
    if openapi_path.exists():
        try:
            openapi = json.loads(openapi_path.read_text(encoding="utf-8"))
            report.checks.append(CheckResult("openapi.json valid JSON", True, ""))
        except json.JSONDecodeError as e:
            report.checks.append(
                CheckResult("openapi.json valid JSON", False, f"JSON parse error: {e}")
            )
    else:
        report.checks.append(
            CheckResult("openapi.json exists", False, "openapi.json not found")
        )

    if openapi is not None:
        for key in ("openapi", "info", "paths"):
            if key in openapi:
                report.checks.append(CheckResult(f"openapi.json has '{key}'", True, ""))
            else:
                report.checks.append(
                    CheckResult(
                        f"openapi.json has '{key}'",
                        False,
                        f"openapi.json missing required key: '{key}'",
                    )
                )

    # cloudformation.yaml exists and parses with Resources containing AWS::Bedrock::Agent
    cf_path = output_dir / "cloudformation.yaml"
    cf: dict[str, Any] | None = None
    if cf_path.exists():
        try:
            cf = _load_cf_yaml(cf_path.read_text(encoding="utf-8"))
            report.checks.append(
                CheckResult("cloudformation.yaml valid YAML", True, "")
            )
        except Exception as e:
            report.checks.append(
                CheckResult(
                    "cloudformation.yaml valid YAML", False, f"YAML parse error: {e}"
                )
            )
    else:
        report.checks.append(
            CheckResult(
                "cloudformation.yaml exists", False, "cloudformation.yaml not found"
            )
        )

    if cf is not None:
        if "Resources" in cf:
            report.checks.append(
                CheckResult("cloudformation.yaml has Resources", True, "")
            )
            resources = cf["Resources"]
            bedrock_agents = [
                k
                for k, v in resources.items()
                if isinstance(v, dict) and v.get("Type") == "AWS::Bedrock::Agent"
            ]
            if bedrock_agents:
                report.checks.append(
                    CheckResult("Resources has AWS::Bedrock::Agent", True, "")
                )
            else:
                report.checks.append(
                    CheckResult(
                        "Resources has AWS::Bedrock::Agent",
                        False,
                        "No AWS::Bedrock::Agent resource found in CloudFormation template",
                    )
                )
        else:
            report.checks.append(
                CheckResult(
                    "cloudformation.yaml has Resources",
                    False,
                    "Missing 'Resources' key in cloudformation.yaml",
                )
            )

    return report


def _validate_m365(output_dir: Path) -> ValidationReport:
    report = ValidationReport(platform="m365", output_dir=output_dir)

    # declarative-agent.json exists, valid JSON, required keys, instructions length
    da_path = output_dir / "declarative-agent.json"
    da: dict[str, Any] | None = None
    if da_path.exists():
        try:
            da = json.loads(da_path.read_text(encoding="utf-8"))
            report.checks.append(
                CheckResult("declarative-agent.json valid JSON", True, "")
            )
        except json.JSONDecodeError as e:
            report.checks.append(
                CheckResult(
                    "declarative-agent.json valid JSON", False, f"JSON parse error: {e}"
                )
            )
    else:
        report.checks.append(
            CheckResult(
                "declarative-agent.json exists",
                False,
                "declarative-agent.json not found",
            )
        )

    if da is not None:
        for key in ("$schema", "version", "name", "description", "instructions"):
            if key in da:
                report.checks.append(
                    CheckResult(f"declarative-agent.json has '{key}'", True, "")
                )
            else:
                report.checks.append(
                    CheckResult(
                        f"declarative-agent.json has '{key}'",
                        False,
                        f"Missing required key: '{key}'",
                    )
                )

        instructions = da.get("instructions", "")
        if isinstance(instructions, str) and len(instructions) <= 8000:
            report.checks.append(CheckResult("instructions length <= 8000", True, ""))
        elif isinstance(instructions, str):
            report.checks.append(
                CheckResult(
                    "instructions length <= 8000",
                    False,
                    f"instructions is {len(instructions)} chars, exceeds 8000 char limit",
                )
            )

    # manifest.json exists, valid JSON, has copilotAgents key
    manifest_path = output_dir / "manifest.json"
    manifest: dict[str, Any] | None = None
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            report.checks.append(CheckResult("manifest.json valid JSON", True, ""))
        except json.JSONDecodeError as e:
            report.checks.append(
                CheckResult("manifest.json valid JSON", False, f"JSON parse error: {e}")
            )
    else:
        report.checks.append(
            CheckResult("manifest.json exists", False, "manifest.json not found")
        )

    if manifest is not None:
        if "copilotAgents" in manifest:
            report.checks.append(
                CheckResult("manifest.json has 'copilotAgents'", True, "")
            )
        else:
            report.checks.append(
                CheckResult(
                    "manifest.json has 'copilotAgents'",
                    False,
                    "Missing 'copilotAgents' key in manifest.json",
                )
            )

    return report


def _validate_vertex(output_dir: Path) -> ValidationReport:
    report = ValidationReport(platform="vertex", output_dir=output_dir)

    # agent.json exists, valid JSON, required keys
    agent_path = output_dir / "agent.json"
    agent: dict[str, Any] | None = None
    if agent_path.exists():
        try:
            agent = json.loads(agent_path.read_text(encoding="utf-8"))
            report.checks.append(CheckResult("agent.json valid JSON", True, ""))
        except json.JSONDecodeError as e:
            report.checks.append(
                CheckResult("agent.json valid JSON", False, f"JSON parse error: {e}")
            )
    else:
        report.checks.append(
            CheckResult("agent.json exists", False, "agent.json not found")
        )

    if agent is not None:
        for key in ("displayName", "goal", "instructions"):
            if key in agent:
                report.checks.append(CheckResult(f"agent.json has '{key}'", True, ""))
            else:
                report.checks.append(
                    CheckResult(
                        f"agent.json has '{key}'",
                        False,
                        f"Missing required key: '{key}'",
                    )
                )

        goal = agent.get("goal", "")
        if isinstance(goal, str) and len(goal) <= 8000:
            report.checks.append(CheckResult("goal length <= 8000", True, ""))
        elif isinstance(goal, str):
            report.checks.append(
                CheckResult(
                    "goal length <= 8000",
                    False,
                    f"goal is {len(goal)} chars, exceeds 8000 char limit",
                )
            )

    return report


# ---------------------------------------------------------------------------
# CloudFormation YAML loader with tag support
# ---------------------------------------------------------------------------


def _cf_tag_constructor(loader: yaml.Loader, tag_suffix: str, node: yaml.Node) -> Any:
    """Handle CloudFormation intrinsic functions like !Ref, !Sub, !GetAtt."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    else:
        return loader.construct_mapping(node)


def _load_cf_yaml(text: str) -> dict[str, Any]:
    """Load CloudFormation YAML with support for CF-specific tags."""
    loader_class = yaml.SafeLoader

    class CFLoader(loader_class):  # type: ignore[valid-type, misc]
        pass

    CFLoader.add_multi_constructor("!", _cf_tag_constructor)
    return yaml.load(text, Loader=CFLoader)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


_VALIDATORS = {
    "claude-code": _validate_claude_code,
    "copilot": _validate_copilot,
    "bedrock": _validate_bedrock,
    "m365": _validate_m365,
    "vertex": _validate_vertex,
}


def run_validation(output_dir: Path, platform: str) -> ValidationReport:
    """Run platform-specific validation and return a ValidationReport."""
    platform = platform.lower()
    if platform not in _VALIDATORS:
        raise ValueError(
            f"Unknown platform: {platform!r}. Supported: {', '.join(_VALIDATORS)}"
        )
    return _VALIDATORS[platform](output_dir)


# ---------------------------------------------------------------------------
# Rich output renderer
# ---------------------------------------------------------------------------


def _print_report(report: ValidationReport, con: Console) -> None:
    con.print(
        f"\n[bold]Validating[/bold] [cyan]{report.output_dir}[/cyan] "
        f"for [green]{report.platform}[/green]\n"
    )
    for check in report.checks:
        if check.passed:
            con.print(f"  [green]✓[/green] {check.name}")
        elif check.is_warning:
            con.print(f"  [yellow]⚠[/yellow]  {check.name}: {check.message}")
        else:
            con.print(f"  [red]✗[/red] {check.name}: {check.message}")

    con.print()
    if report.ok:
        con.print("[green]✅ Validation passed[/green]")
    else:
        n = len(report.errors)
        con.print(f"[red]❌ Validation failed ({n} error{'s' if n != 1 else ''})[/red]")


def validate_output(output_dir: Path, platform: str, as_json: bool = False) -> bool:
    """Validate output directory for the given platform.

    Prints results to console. Returns True if validation passed.
    Raises SystemExit(1) on failure.
    """
    try:
        report = run_validation(output_dir, platform)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e

    if as_json:
        import sys

        data = {
            "platform": report.platform,
            "output_dir": str(report.output_dir),
            "ok": report.ok,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "warning": c.is_warning,
                    "message": c.message,
                }
                for c in report.checks
            ],
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
        }
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    else:
        _print_report(report, console)

    return report.ok
