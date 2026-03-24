# weather — GCP Vertex AI Agent

Get current weather and forecasts via wttr.in or Open-Meteo. Use when: user asks about weather, temperature, or forecasts for any location. NOT for: historical weather data, severe weather alerts, or detailed meteorological analysis. No API key needed.

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
  --agent-id=weather \
  --source=agent.json \
  --location=us-central1
```

### Test the agent

```bash
gcloud alpha agent-builder agents run \
  --agent-id=weather \
  --location=us-central1 \
  --query="Hello!"
```

## Tools (Stubs — manual implementation required)

The following tools are marked as stubs and require implementation as
Cloud Functions or Cloud Run services before the agent is fully functional:

- **curl** (shell) — implement as Cloud Function or Cloud Run service

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