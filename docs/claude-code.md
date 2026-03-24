# OpenClaw → Claude Code

Full end-to-end guide for converting an OpenClaw skill to Claude Code format.

---

## Step 1: Convert

```bash
agentshift convert ~/.openclaw/skills/github --from openclaw --to claude-code --output ./github-claude
```

Output:

```
github-claude/
├── CLAUDE.md       ← instructions + persona (Claude Code reads this automatically)
└── settings.json   ← tool permissions (Bash, MCP, Read/Write paths)
```

---

## Step 2: Place the files

| Location | Scope | When to use |
|---|---|---|
| `~/.claude/CLAUDE.md` | Global — all projects | Skills you want everywhere |
| `<project>/.claude/CLAUDE.md` | Project-only | Skills scoped to one repo |

```bash
# Option A — global
mkdir -p ~/.claude
cp github-claude/CLAUDE.md ~/.claude/CLAUDE.md
cp github-claude/settings.json ~/.claude/settings.json

# Option B — project-scoped
mkdir -p my-project/.claude
cp github-claude/CLAUDE.md my-project/.claude/CLAUDE.md
cp github-claude/settings.json my-project/.claude/settings.json
```

> **Multiple skills:** Claude Code loads one `CLAUDE.md` per scope. Concatenate files and merge permission arrays to combine — or wait for `agentshift merge` (coming soon).

---

## Step 3: Use it

```bash
cd my-project
claude

# Or non-interactively
claude --print "check open PRs for owner/repo"
claude --print "what CI checks are failing on PR #55?"
```

---

## Step 4: Verify permissions

```bash
cat github-claude/settings.json
# → { "permissions": { "allow": ["Bash(gh:*)", "Bash(git:*)"] } }
```

Each `allow` entry follows the Claude Code format: `Tool(binary:*)` or `mcp__<server>__*`.

---

## What carries over from OpenClaw

| OpenClaw feature | Claude Code equivalent | Status |
|---|---|---|
| Skill instructions (body) | `CLAUDE.md` — loaded automatically | ✅ Full fidelity |
| Shell tool permissions | `settings.json` `allow: ["Bash(<binary>:*)"]` | ✅ Precise per-binary |
| MCP tools (slack, github) | `settings.json` `allow: ["mcp__<name>__*"]` | ✅ Works if MCP server configured |
| Knowledge files | `CLAUDE.md` knowledge section + `Read(path)` permissions | ✅ Paths preserved |
| Data file writes | `Write(path)` in `settings.json` | ✅ Exact paths |
| OS constraints | `settings.json` `supportedOs` | ✅ Preserved |
| Cron / scheduled triggers | Cloud Scheduled Tasks (Anthropic-managed) | ✅ See below |
| Install dependencies | Not applicable — assumes tools installed | ⚠️ Manual step |
| Telegram / Slack delivery | Not supported natively | ⚠️ See workarounds |

---

## Scheduled triggers

Claude Code has **cloud-managed scheduled tasks** that keep running even when your computer is off — just like OpenClaw cron jobs.

```bash
# Option 1 — conversational
/schedule daily PR review at 9am

# Option 2 — in-session loop
/loop 30m check if the deployment finished

# Option 3 — web UI: https://claude.ai/code/scheduled → New scheduled task
```

| OpenClaw (`jobs.json`) | Claude Code |
|---|---|
| `"schedule": "0 9 * * *"` | `/schedule daily at 9am` or set via web UI |
| `"message": "Give today's tip"` | Prompt field in the scheduled task |
| `"session_target": "isolated"` | Each run is a fresh cloud session (default) |

> `/loop` tasks disappear when Claude Code exits. For durable cron, use cloud scheduled tasks at `claude.ai/code/scheduled`.

---

## Remaining gaps

**1. Proactive delivery (Telegram, Slack, Discord)**
OpenClaw pushes results to messaging channels. Claude Code scheduled tasks output to GitHub branches or logs.

*Workaround:* End your scheduled task prompt with:
```
... do the work, then write the summary to summary.md and commit it to daily-summary/YYYY-MM-DD
```

**2. Persistent memory across sessions**
OpenClaw persists `MEMORY.md`. Claude Code sessions are stateless by default.

*Workaround:* Reference memory files in your project-level `CLAUDE.md` or pass them in your scheduled task prompt.

**3. Multi-channel routing**
OpenClaw routes output to Telegram, Slack, Discord, or email. Claude Code outputs to stdout or GitHub only.

*Workaround:* Add an MCP server for your channel (e.g. `mcp__slack__post_message`) and include it in `settings.json` permissions.

---

## Real example: github skill

The following shows the actual output of:

```bash
agentshift convert ~/.openclaw/skills/github --from openclaw --to claude-code --output /tmp/as-audit3/github
```

### CLAUDE.md

```markdown
# github

GitHub operations via `gh` CLI: issues, PRs, CI runs, code review, API queries. Use when: (1) checking PR status or CI, (2) creating/commenting on issues, (3) listing/filtering PRs or issues, (4) viewing run logs. NOT for: complex web UI interactions requiring manual browser flows (use browser tooling when available), bulk operations across many repos (script with gh api), or when gh auth is not configured.

## Instructions

# GitHub Skill

Use the `gh` CLI to interact with GitHub repositories, issues, PRs, and CI.

## When to Use

✅ **USE this skill when:**

- Checking PR status, reviews, or merge readiness
- Viewing CI/workflow run status and logs
- Creating, closing, or commenting on issues
- Creating or merging pull requests
- Querying GitHub API for repository data
- Listing repos, releases, or collaborators

## When NOT to Use

❌ **DON'T use this skill when:**

- Local git operations (commit, push, pull, branch) → use `git` directly
- Non-GitHub repos (GitLab, Bitbucket, self-hosted) → different CLIs
- Cloning repositories → use `git clone`
- Reviewing actual code changes → use `coding-agent` skill
- Complex multi-file diffs → use `coding-agent` or read files directly

## Setup

```bash
# Authenticate (one-time)
gh auth login

# Verify
gh auth status
```

## Common Commands

### Pull Requests

```bash
gh pr list --repo owner/repo
gh pr checks 55 --repo owner/repo
gh pr view 55 --repo owner/repo
gh pr create --title "feat: add feature" --body "Description"
gh pr merge 55 --squash --repo owner/repo
```

### Issues

```bash
gh issue list --repo owner/repo --state open
gh issue create --title "Bug: something broken" --body "Details..."
gh issue close 42 --repo owner/repo
```

### CI/Workflow Runs

```bash
gh run list --repo owner/repo --limit 10
gh run view <run-id> --repo owner/repo --log-failed
gh run rerun <run-id> --failed --repo owner/repo
```

## Tools

- **gh** (shell): Run gh commands
- **git** (shell): Run git commands
```

### settings.json

```json
{
  "permissions": {
    "allow": [
      "Bash(gh:*)",
      "Bash(git:*)"
    ]
  }
}
```

---

See also: [examples/github-to-claude-code/](../examples/github-to-claude-code/)
