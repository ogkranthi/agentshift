# Vertex AI Agent Builder Format Spec

**Task:** A06
**Status:** Canonical
**Version:** 1.0

---

## Overview

Vertex AI Agent Builder (formerly Dialogflow CX) provides a managed agent platform on Google Cloud. Agents are defined by a **goal** (the system instruction / persona), **playbooks** (structured task workflows), **tools** (OpenAPI, Vertex AI Extensions, Function tools, or Data Store lookups), and optional **data stores** for grounding/RAG.

AgentShift targets the **Reasoning Engine / Agent Builder API** model (not the older Dialogflow CX flow model), which is the recommended approach for LLM-based agents.

AgentShift emits:

| File | Purpose |
|------|---------|
| `agent.json` | Agent resource definition (goal, display name, etc.) |
| `tools.json` | Tool definitions (OpenAPI, function, data store) |
| `deployment.sh` | `gcloud` CLI commands to create/update the agent |
| `README.md` | Setup and deployment instructions |

---

## Platform Constraints

| Constraint | Value |
|-----------|-------|
| Goal (system instruction) max length | **8,000 characters** |
| Agent display name max length | 128 characters |
| Max tools per agent | 128 |
| Max actions per OpenAPI tool | No documented hard limit |
| Supported models | Gemini 1.5 Flash, Gemini 1.5 Pro, Gemini 2.0 Flash, Gemini 2.5 Pro |
| Regions | `us-central1`, `europe-west1`, `asia-northeast1`, and others |

---

## Vertex AI Agent — Native Resource Structure

Vertex AI Agents are created via the `agents` sub-resource of a Reasoning Engine, or directly via the Agent Builder console/API. The key resource is `projects/{project}/locations/{location}/agents/{agent_id}`.

### Agent resource (REST / JSON)

```json
{
  "displayName": "Pregnancy Companion",
  "goal": "You are a warm, knowledgeable pregnancy companion...",
  "instructions": [
    "Always recommend consulting a healthcare provider for medical decisions.",
    "Respond in a warm, supportive tone.",
    "Never diagnose or prescribe."
  ],
  "tools": [
    {
      "name": "projects/PROJECT/locations/LOCATION/agents/AGENT/tools/TOOL_ID"
    }
  ]
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `displayName` | string | ✅ | ≤ 128 chars |
| `goal` | string | ✅ | ≤ 8,000 chars — this is the primary system prompt |
| `instructions` | array[string] | — | Additional behavioral rules prepended to `goal` |
| `tools` | array[ref] | — | References to Tool resources |

---

## Tool Resource — Three Types

### Type 1: OpenAPI Tool

Exposes a REST API the agent can call. The agent uses the operation descriptions to decide which endpoint to invoke.

```json
{
  "displayName": "WeatherAPI",
  "description": "Look up current weather by location",
  "openApiFunctionDeclarations": {
    "specification": {
      "openapi": "3.0.0",
      "info": {
        "title": "WeatherAPI",
        "version": "1.0.0"
      },
      "servers": [
        { "url": "https://api.openweathermap.org/data/2.5" }
      ],
      "paths": {
        "/weather": {
          "get": {
            "operationId": "getCurrentWeather",
            "description": "Get current weather for a location",
            "parameters": [
              {
                "name": "q",
                "in": "query",
                "required": true,
                "schema": { "type": "string" },
                "description": "City name, e.g. 'London'"
              },
              {
                "name": "units",
                "in": "query",
                "schema": { "type": "string", "enum": ["metric", "imperial"] }
              }
            ],
            "responses": {
              "200": {
                "description": "Weather data",
                "content": {
                  "application/json": {
                    "schema": {
                      "type": "object",
                      "properties": {
                        "temp": { "type": "number" },
                        "description": { "type": "string" }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    },
    "authentication": {
      "apiKeyConfig": {
        "name": "appid",
        "in": "QUERY",
        "httpElementLocation": "HTTP_IN_QUERY"
      }
    }
  }
}
```

**Key difference from Bedrock:** Vertex AI uses real HTTP endpoints — `servers[].url` is followed and the agent makes actual HTTP calls. Bedrock uses Lambda; Vertex uses real URLs.

### Type 2: Function Tool (for Cloud Functions / local logic)

```json
{
  "displayName": "SymptomTracker",
  "description": "Log and retrieve pregnancy symptoms",
  "functionDeclarations": [
    {
      "name": "log_symptom",
      "description": "Log a pregnancy symptom with optional severity score",
      "parameters": {
        "type": "object",
        "properties": {
          "symptom": {
            "type": "string",
            "description": "Name of the symptom"
          },
          "severity": {
            "type": "integer",
            "description": "Severity from 1 (mild) to 10 (severe)"
          },
          "date": {
            "type": "string",
            "description": "ISO 8601 date string"
          }
        },
        "required": ["symptom"]
      }
    },
    {
      "name": "get_symptoms",
      "description": "Retrieve logged symptoms for a date range",
      "parameters": {
        "type": "object",
        "properties": {
          "start_date": { "type": "string" },
          "end_date": { "type": "string" }
        }
      }
    }
  ]
}
```

Function tools are invoked client-side (the agent returns a function call that your code executes). They are analogous to OpenAI function calling.

### Type 3: Data Store Tool (for grounding / RAG)

```json
{
  "displayName": "PregnancyKnowledgeBase",
  "description": "Search pregnancy guides, week-by-week development, and nutrition info",
  "datastoreSpec": {
    "datastoreType": "PUBLIC_WEB",
    "confidenceThreshold": 0.7,
    "dataStores": [
      "projects/PROJECT/locations/global/collections/default_collection/dataStores/DATA_STORE_ID"
    ]
  }
}
```

Alternatively, for private/uploaded documents:

```json
{
  "datastoreSpec": {
    "datastoreType": "UNSTRUCTURED_DOCUMENTS",
    "dataStores": [
      "projects/PROJECT/locations/us-central1/collections/default_collection/dataStores/DATA_STORE_ID"
    ]
  }
}
```

---

## Authentication Configuration

Vertex AI tools support several auth methods:

```json
{
  "authentication": {
    "apiKeyConfig": {
      "name": "api_key",
      "in": "HEADER",
      "httpElementLocation": "HTTP_IN_HEADER"
    }
  }
}
```

```json
{
  "authentication": {
    "oauthConfig": {
      "scope": "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}
```

```json
{
  "authentication": {
    "serviceAccountConfig": {
      "serviceAccount": "my-sa@project.iam.gserviceaccount.com",
      "audience": "https://my-service.run.app"
    }
  }
}
```

---

## Deployment via `gcloud` CLI

```bash
# Create agent
gcloud alpha agents create \
  --display-name="Pregnancy Companion" \
  --goal="$(cat goal.txt)" \
  --location=us-central1 \
  --project=MY_PROJECT

# Create OpenAPI tool
gcloud alpha agents tools create \
  --agent=AGENT_ID \
  --display-name="WeatherAPI" \
  --open-api-spec=openapi.json \
  --location=us-central1 \
  --project=MY_PROJECT

# Associate tool with agent
gcloud alpha agents update AGENT_ID \
  --add-tool=TOOL_ID \
  --location=us-central1 \
  --project=MY_PROJECT
```

Alternatively, use the REST API:

```
POST https://us-central1-aiplatform.googleapis.com/v1beta1/projects/PROJECT/locations/us-central1/agents
Authorization: Bearer $(gcloud auth print-access-token)
Content-Type: application/json
```

---

## Data Store Setup for Knowledge Bases

```bash
# Create data store
gcloud alpha ais data-stores create \
  --display-name="PregnancyGuides" \
  --location=us-central1 \
  --project=MY_PROJECT

# Import documents from GCS
gcloud alpha ais data-stores import-documents \
  --data-store=DATA_STORE_ID \
  --gcs-source=gs://my-bucket/knowledge/*.md \
  --location=us-central1 \
  --project=MY_PROJECT
```

---

## IR → Vertex AI Field Mapping

| IR field | Vertex AI field | Notes |
|----------|----------------|-------|
| `name` | `displayName` (slugified → Title Case) | e.g. `pregnancy-companion` → `Pregnancy Companion` |
| `description` | `description` (on agent resource) | Up to 500 chars |
| `persona.system_prompt` | `goal` | **Truncated to 8,000 chars**. Emit warning if truncated |
| `persona.language` | Include language in `goal` preamble | No native language field; instruct the model in the goal |
| `constraints.guardrails` | `instructions` array entries | Each guardrail becomes a bullet in `instructions` |
| `tools[kind=function\|openapi]` | OpenAPI tool or function tool | Prefer OpenAPI tool if URL is available, function tool otherwise |
| `tools[kind=mcp]` | ⚠️ stub only | MCP not natively supported; emit TODO comment |
| `tools[kind=shell]` | ⚠️ stub only | No shell execution; emit TODO comment |
| `tools[kind=builtin]` | ⚠️ stub only | No platform builtins; emit TODO comment |
| `tools[].auth.type=api_key` | `authentication.apiKeyConfig` | Map env_var name to `apiKeyConfig.name` |
| `tools[].auth.type=oauth2` | `authentication.oauthConfig` | Map scopes |
| `knowledge[kind=file]` | Data Store tool (UNSTRUCTURED_DOCUMENTS) | Requires GCS upload step in deployment.sh |
| `knowledge[kind=vector_store]` | Data Store tool (existing store) | Reference existing data store by path |
| `knowledge[].load_mode=always` | Prepend content to `goal` if small | Small files (< 500 chars) can be inlined in goal |
| `knowledge[].load_mode=indexed` | Data Store tool | RAG via data store |
| `triggers[kind=cron]` | Cloud Scheduler → Cloud Run/Functions | Emit stub deployment script |
| `triggers[kind=webhook]` | Cloud Run endpoint | Emit stub |
| `constraints.max_instruction_chars` | Enforced as 8,000 | Override with `metadata.platform_extensions.vertex_ai.max_goal_chars` |
| `metadata.platform_extensions.vertex_ai.model` | Model selection | Override default Gemini model |

---

## Complete `agent.json` Example

```json
{
  "displayName": "Pregnancy Companion",
  "description": "24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates",
  "goal": "You are a warm, knowledgeable pregnancy companion. You help users throughout their pregnancy journey by answering questions, tracking symptoms, and providing weekly development updates.\n\nYou have access to:\n- A symptom tracking tool to log and retrieve health data\n- A pregnancy knowledge base with week-by-week development info and nutrition guides\n\nAlways recommend consulting a healthcare provider for medical decisions.",
  "instructions": [
    "Never diagnose medical conditions or prescribe treatments.",
    "Respond in a warm, supportive, non-clinical tone.",
    "Use simple, accessible language — avoid medical jargon.",
    "When tracking symptoms, always confirm the entry with the user."
  ],
  "tools": []
}
```

## Complete `tools.json` Example

```json
[
  {
    "displayName": "SymptomTracker",
    "description": "Log and retrieve pregnancy symptoms",
    "functionDeclarations": [
      {
        "name": "log_symptom",
        "description": "Log a pregnancy symptom. Call this when the user wants to record a symptom.",
        "parameters": {
          "type": "object",
          "properties": {
            "symptom": { "type": "string", "description": "Symptom name, e.g. 'nausea'" },
            "severity": { "type": "integer", "description": "1=mild, 10=severe" },
            "date": { "type": "string", "description": "ISO 8601 date, defaults to today" }
          },
          "required": ["symptom"]
        }
      }
    ]
  },
  {
    "displayName": "PregnancyKnowledgeBase",
    "description": "Search pregnancy guides and week-by-week development information",
    "datastoreSpec": {
      "datastoreType": "UNSTRUCTURED_DOCUMENTS",
      "confidenceThreshold": 0.6,
      "dataStores": [
        "projects/MY_PROJECT/locations/us-central1/collections/default_collection/dataStores/pregnancy-kb"
      ]
    }
  }
]
```

---

## Emitter Output Layout

```
output/
├── agent.json          # Agent resource definition
├── tools.json          # Array of tool resource definitions
├── deployment.sh       # gcloud CLI commands to deploy
└── README.md           # Setup instructions
```

---

## Stub Comments for Unsupported Features

```json
{
  "_comment_TODO_agentshift": "MCP tool 'slack' has no Vertex AI Agent Builder equivalent. Implement as a Cloud Function and expose via OpenAPI tool, or remove.",
  "_comment_original_ir": "{ \"name\": \"slack\", \"kind\": \"mcp\", \"description\": \"...\" }"
}
```

---

## Notes for the Implementing Dev (D09)

1. **No direct equivalent to MCP** — all tools must be OpenAPI-based HTTP endpoints, Cloud Functions exposed as functions, or data stores. When IR has `kind=mcp`, emit a function tool stub with a TODO.
2. **`goal` is the only system instruction field** — `instructions` array is supplementary; put the main persona in `goal`.
3. **Goal truncation at 8,000 chars** — more generous than Bedrock, but still check. Truncate at sentence boundary.
4. **Real HTTP calls for OpenAPI tools** — unlike Bedrock, Vertex AI makes real HTTP requests. The `servers[].url` must be a real, accessible endpoint. Emit a placeholder URL with a TODO if no URL is available.
5. **Function tools are client-executed** — the agent returns a `functionCall` and the calling code must dispatch and return a `functionResponse`. The emitter should document this in README.md.
6. **Data stores require a GCS bucket** — knowledge files must be uploaded to GCS before the data store can be created. Emit GCS upload commands in `deployment.sh`.
7. **Model selection** — default to `gemini-1.5-pro-002`. Allow override via `metadata.platform_extensions.vertex_ai.model`.
8. **Guardrails as instructions** — IR `constraints.guardrails` strings map to `instructions` array entries. Prefix each with "Never " or rephrase as a constraint.
9. **`displayName` from `name`** — convert slug to Title Case: `pregnancy-companion` → `Pregnancy Companion`.
10. **Preserve `metadata.platform_extensions.vertex_ai`** on round-trip (agent resource ID, project, location).
