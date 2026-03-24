# OpenClaw → GCP Vertex AI

Full end-to-end guide for converting an OpenClaw skill to GCP Vertex AI Agent Builder format.

---

## Step 1: Convert

```bash
agentshift convert ~/.openclaw/skills/github --from openclaw --to vertex --output ./github-vertex
```

Output:

```
github-vertex/
├── agent.json    ← Vertex AI Agent Builder config (display name, goal, instructions)
└── README.md     ← prerequisites + deploy command
```

---

## Step 2: Prerequisites

- Google Cloud project with billing enabled
- Vertex AI API enabled (`gcloud services enable aiplatform.googleapis.com`)
- `gcloud` CLI installed and authenticated (`gcloud auth login`)
- Dialogflow CX API enabled (`gcloud services enable dialogflow.googleapis.com`)

---

## Step 3: Deploy

```bash
gcloud ai agents create \
  --project=<your-project-id> \
  --location=us-central1 \
  --display-name="github-agent" \
  --config-file=github-vertex/agent.json
```

---

## Step 4: Test

```bash
gcloud ai agents stream-query \
  --project=<your-project-id> \
  --location=us-central1 \
  --agent=<agent-id from deploy output> \
  --query="List open PRs for owner/repo"
```

---

## What carries over from OpenClaw

| OpenClaw feature | Vertex AI equivalent | Status |
|---|---|---|
| Skill instructions (body) | `agent.json` goal + instructions | ✅ Full fidelity |
| Shell tools (gh, curl, etc.) | Cloud Function stubs (referenced in instructions) | ⚠️ You must implement the Cloud Function |
| MCP tools | Tool stub (manual wiring required) | ⚠️ Manual implementation required |
| Knowledge files | Vertex AI Data Store (manual setup) | ⚠️ Data Store setup required |
| Cron / scheduled triggers | Cloud Scheduler + Eventarc | ⚠️ Wire to Cloud Scheduler |
| Telegram / Slack delivery | Not supported natively | ❌ |

---

## Limitations

- **Shell tools become Cloud Function stubs** — tools like `gh` or `curl` are described in instructions; you must implement and register Cloud Functions
- **No native cron** — use Cloud Scheduler + Eventarc to trigger the agent on a schedule
- **No Telegram/Slack delivery** — Vertex AI agents return responses via API; push delivery requires a separate integration
- **Tool grounding requires manual wiring** — each tool must be registered as a Vertex AI Extension or Cloud Function

---

## Check portability first

```bash
agentshift diff ~/.openclaw/skills/github --from openclaw --targets vertex
```

---

See also: [examples/github-to-vertex/](../examples/github-to-vertex/)
