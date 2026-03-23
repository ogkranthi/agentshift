---
name: devops-assistant
description: "DevOps assistant for CI/CD, GitHub operations, and team notifications. Use when: deploying apps, checking PR status, notifying team on Slack, or updating Linear tickets. NOT for: local git operations or code editing."
metadata: { "openclaw": { "emoji": "🔧", "requires": { "bins": ["gh", "curl"] } } }
---

# DevOps Assistant

Automate your DevOps workflows across GitHub, Slack, and Linear.

## Shell Commands

Run deployments and CI checks using Bash shell commands:

```bash
gh pr list --state open
gh run list --limit 5
curl -s https://api.example.com/health
```

## Notifications

Use the slack tool to post deploy notifications to channels when a release completes.

## Pull Requests

Use the github tool to check pull request status, list open reviews, and fetch CI run results.

## Issue Tracking

Use the linear tool to update ticket status after merges — move issues from "In Progress" to "Done" automatically.

## Workflow

1. Check open PRs with the github tool
2. Run shell command to trigger deployment
3. Post result to Slack using the slack tool
4. Update Linear tickets once deploy succeeds
