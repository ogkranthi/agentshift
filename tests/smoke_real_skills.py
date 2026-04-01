"""Real-skills smoke test — parses every skill in both OpenClaw skill directories."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from agentshift.parsers.openclaw import parse_skill_dir

SKILL_DIRS = [
    Path(
        "/Users/kranthikumar/.nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills"
    ),
    Path("/Users/kranthikumar/.openclaw/skills"),
]

COL_SKILL = 30
COL_STATUS = 8
COL_ISSUES = 50


def check_skill(skill_path: Path) -> tuple[str, list[str]]:
    """Parse a skill dir and return (status, issues). status is 'PASS' or 'FAIL'."""
    issues: list[str] = []

    try:
        ir = parse_skill_dir(skill_path)
    except Exception as exc:
        tb = traceback.format_exc()
        return "FAIL", [f"Exception: {type(exc).__name__}: {exc}", tb]

    if not ir.name or not ir.name.strip():
        issues.append("name is empty")
    if not ir.description or not ir.description.strip():
        issues.append("description is empty")
    if ir.metadata.source_platform != "openclaw":
        issues.append(
            f"source_platform={ir.metadata.source_platform!r}, expected 'openclaw'"
        )

    # No raw Python object reprs in emitted output
    import tempfile

    from agentshift.emitters.claude_code import emit

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            emit(ir, tmp_path)
        except Exception as exc:
            issues.append(f"Emitter error: {type(exc).__name__}: {exc}")
        else:
            claude_md = tmp_path / "CLAUDE.md"
            if claude_md.exists():
                content = claude_md.read_text(encoding="utf-8")
                # Check for raw object reprs
                if "<agentshift." in content or "object at 0x" in content:
                    issues.append("CLAUDE.md contains raw Python object repr")
                # Check valid UTF-8 (already decoded above, but verify non-empty)
                if not content.strip():
                    issues.append("CLAUDE.md is empty after emit")
                # Check skill name appears somewhere in CLAUDE.md
                # name may be slugified so check loosely
                if ir.name and ir.name[:6].lower() not in content.lower():
                    issues.append(f"CLAUDE.md missing skill name {ir.name!r}")
            else:
                issues.append("CLAUDE.md not created by emitter")

            settings_json = tmp_path / "settings.json"
            if not settings_json.exists():
                issues.append("settings.json not created by emitter")

    return ("PASS" if not issues else "FAIL"), issues


def main() -> int:
    rows: list[tuple[str, str, list[str], str]] = (
        []
    )  # (dir_label, skill_name, issues, status)

    for skills_dir in SKILL_DIRS:
        if not skills_dir.exists():
            print(f"[SKIP] Skills dir not found: {skills_dir}")
            continue

        skill_paths = sorted(p for p in skills_dir.iterdir() if p.is_dir())
        for skill_path in skill_paths:
            status, issues = check_skill(skill_path)
            rows.append((str(skills_dir.name), skill_path.name, issues, status))

    # Print summary table
    header = f"{'SKILL':<{COL_SKILL}} {'STATUS':<{COL_STATUS}} ISSUES"
    print()
    print("=" * 90)
    print("AgentShift Real-Skills Smoke Test")
    print("=" * 90)
    print(header)
    print("-" * 90)

    total = len(rows)
    passed = 0
    failed = 0

    for _dir_label, skill_name, issues, status in rows:
        display_name = f"{skill_name}"
        if status == "PASS":
            passed += 1
            issue_str = ""
        else:
            failed += 1
            # First issue only for table; full details below
            issue_str = issues[0] if issues else "unknown"
            # Truncate
            if len(issue_str) > COL_ISSUES:
                issue_str = issue_str[: COL_ISSUES - 3] + "..."

        status_icon = "✓" if status == "PASS" else "✗"
        print(
            f"{display_name:<{COL_SKILL}} {status_icon} {status:<{COL_STATUS - 2}} {issue_str}"
        )

    print("-" * 90)
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")
    print()

    # Print full failure details
    if failed:
        print("FAILURE DETAILS")
        print("=" * 90)
        for _dir_label, skill_name, issues, status in rows:
            if status == "FAIL":
                print(f"\n[{skill_name}]")
                for i, issue in enumerate(issues):
                    print(f"  {i + 1}. {issue}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
