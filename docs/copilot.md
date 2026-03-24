# OpenClaw → GitHub Copilot

Full end-to-end guide for converting an OpenClaw skill to GitHub Copilot agent format.

---

## Step 1: Convert

```bash
agentshift convert ~/.openclaw/skills/github --from openclaw --to copilot --output ./github-copilot
```

Output:

```
github-copilot/
├── github.agent.md   ← Copilot agent definition (frontmatter + instructions)
└── README.md         ← installation steps for VS Code
```

---

## Step 2: Install in VS Code

**Option A — Command palette (personal use):**
1. Open VS Code
2. `Cmd+Shift+P` → "GitHub Copilot: Install Agent from File"
3. Select `github.agent.md`
4. Agent appears as `@github` in Copilot Chat

**Option B — Workspace (share with team):**
```bash
mkdir -p .github/copilot-agents
cp github-copilot/github.agent.md .github/copilot-agents/
```
Commit to repo — all team members get the agent automatically.

---

## Step 3: Use it

In VS Code Copilot Chat:

```
@github list open PRs for owner/repo
@github check CI status on PR #55
@github create an issue for the login bug I just found
@github show me the last 5 failed workflow runs
```

---

## Step 4: Verify

```bash
head -10 github-copilot/github.agent.md
```

Should show:
```yaml
---
name: "github"
description: "GitHub operations via `gh` CLI..."
model:
  - "Claude Sonnet 4.6 (copilot)"
tools:
  - execute/runInTerminal
---
```

---

## What carries over from OpenClaw

| OpenClaw feature | Copilot equivalent | Status |
|---|---|---|
| Skill instructions (body) | Agent markdown body | ✅ Full fidelity |
| Shell tool usage | `execute/runInTerminal` | ✅ Maps cleanly |
| Knowledge file reads | `read/readFile` tool | ✅ |
| Data file writes | `edit/editFiles` tool | ✅ |
| MCP tools (slack, notion) | MCP server — configure separately in VS Code | ⚠️ Manual step |
| Cron / scheduled triggers | Not supported — Copilot is chat-only | ❌ |
| Telegram / Slack delivery | Not applicable | ❌ |

---

## Contribute to awesome-copilot

The generated `.agent.md` files can be submitted directly to [github/awesome-copilot](https://github.com/github/awesome-copilot):

```bash
# Fork https://github.com/github/awesome-copilot

# Convert your skill
agentshift convert ~/.openclaw/skills/github --from openclaw --to copilot --output /tmp/out

# Copy to your fork
cp /tmp/out/github.agent.md agents/github-cli.agent.md

# Open PR
gh pr create --repo github/awesome-copilot \
  --title "feat: add github-cli agent (converted from OpenClaw via AgentShift)"
```

---

## Real example: github skill

The following shows the actual output of:

```bash
agentshift convert ~/.openclaw/skills/github --from openclaw --to copilot --output /tmp/copilot-github
```

### github.agent.md

```yaml
---
name: "github"
description: "GitHub operations via `gh` CLI: issues, PRs, CI runs, code review, API queries. Use when: (1) checking PR status or CI, (2) creating/commenting on issues, (3) listing/filtering PRs or issues, (4) viewing run logs. NOT for: complex web UI interactions requiring manual browser flows (use browser tooling when available), bulk operations across many repos (script with gh api), or when gh auth is not configured."
model:
  - "Claude Sonnet 4.6 (copilot)"
  - "Claude Opus 4.6 (copilot)"
  - "GPT-5.3-Codex"
tools:
  - execute/runInTerminal
---

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

### API Queries

```bash
gh api repos/owner/repo/pulls/55 --jq '.title, .state, .user.login'
gh api repos/owner/repo --jq '{stars: .stargazers_count, forks: .forks_count}'
```

## Notes

- Always specify `--repo owner/repo` when not in a git directory
- Use URLs directly: `gh pr view https://github.com/owner/repo/pull/55`
- Rate limits apply; use `gh api --cache 1h` for repeated queries
```

---

See also: [examples/github-to-copilot/](../examples/github-to-copilot/)
