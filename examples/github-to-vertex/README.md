# github — GCP Vertex AI Agent

GitHub operations via `gh` CLI: issues, PRs, CI runs, code review, API queries. Use when: (1) checking PR status or CI, (2) creating/commenting on issues, (3) listing/filtering PRs or issues, (4) viewing run logs. NOT for: complex web UI interactions requiring manual browser flows (use browser tooling when available), bulk operations across many repos (script with gh api), or when gh auth is not configured.

> **Converted from OpenClaw by [AgentShift](https://agentshift.sh)**

## Generated Files

| File | Description |
|------|-------------|
| `agent.json` | Vertex AI Agent Builder configuration |
| `README.md` | This file — setup and deploy instructions |

## Prerequisites

1. A Google Cloud project with billing enabled
2. The `gcloud` CLI installed and authenticated:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

3. Enable required APIs:

```bash
gcloud services enable aiplatform.googleapis.com
```

## Deploy

### Import the agent

```bash
gcloud alpha agent-builder agents import \
  --agent-id=github \
  --source=agent.json \
  --location=us-central1
```

### Test the agent

```bash
gcloud alpha agent-builder agents run \
  --agent-id=github \
  --location=us-central1 \
  --query="Hello!"
```

## Tools (Stubs — manual implementation required)

The following tools are marked as stubs and require implementation as
Cloud Functions or Cloud Run services before the agent is fully functional:

- **gh** (shell) — implement as Cloud Function or Cloud Run service
- **git** (shell) — implement as Cloud Function or Cloud Run service

See the [Vertex AI Agent Builder docs](https://cloud.google.com/vertex-ai/docs/agent-builder/create-manage-agents) for integration details.

## About

This agent was automatically converted using AgentShift.

- **Source format:** OpenClaw SKILL.md
- **Target format:** GCP Vertex AI Agent Builder
- **Converter:** [AgentShift](https://agentshift.sh)

To convert other OpenClaw skills:
```bash
agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to vertex --output /tmp/vertex-output
```