# AWS Bedrock Agent Format Spec

**Task:** A05
**Status:** Canonical
**Version:** 1.0

---

## Overview

AWS Bedrock Agents are fully managed AI agents that orchestrate multi-step tasks using a foundation model (e.g., Claude), a natural-language instruction, optional action groups (REST APIs exposed via OpenAPI schema + Lambda), and optional knowledge bases (S3 + vector store).

AgentShift emits three artifact files for the Bedrock target:

| File | Purpose |
|------|---------|
| `instruction.txt` | Plain-text agent instruction (≤ 4,000 chars) |
| `openapi.json` | OpenAPI 3.0 schema for every action group |
| `cloudformation.yaml` | CloudFormation template to provision the agent |

---

## Platform Constraints

| Constraint | Value |
|-----------|-------|
| Instruction field max length | **4,000 characters** |
| Agent description max length | 200 characters |
| Max action groups per agent | 11 |
| Max actions per action group | 11 |
| Supported foundation models | Claude 3.x / Claude 3.5 / Claude Instant (must be enabled in region) |
| Regions | `us-east-1`, `us-west-2`, `ap-northeast-1`, `eu-west-1` (region availability varies) |
| OpenAPI schema max size (inline) | 4 MB |

---

## Bedrock Agent — Native Fields

### `AWS::Bedrock::Agent` CloudFormation resource

```yaml
Type: AWS::Bedrock::Agent
Properties:
  AgentName: string                   # Required. 1–100 chars, alphanumeric + hyphens
  AgentResourceRoleArn: string        # Required. IAM role ARN with bedrock:InvokeModel
  Description: string                 # Optional. ≤ 200 chars
  Instruction: string                 # Required. ≤ 4000 chars — this IS the system prompt
  FoundationModel: string             # Required. Model ID, e.g. "anthropic.claude-3-5-sonnet-20241022-v2:0"
  IdleSessionTTLInSeconds: integer    # Optional. 60–3600. Default 1800
  AutoPrepare: boolean                # Optional. Default false — set true to auto-build on deploy
  Tags:
    key: value
  ActionGroups:
    - ActionGroupName: string
      ActionGroupExecutor:
        Lambda: string                # Lambda function ARN
      ApiSchema:
        S3:
          S3BucketName: string
          S3ObjectKey: string
        # OR inline:
        Payload: string               # JSON string of the OpenAPI schema
      Description: string
      ActionGroupState: ENABLED | DISABLED
  KnowledgeBases:
    - KnowledgeBaseId: string
      KnowledgeBaseState: ENABLED | DISABLED
      Description: string
```

### `AWS::Bedrock::AgentAlias` CloudFormation resource

An alias is required to invoke the agent programmatically.

```yaml
Type: AWS::Bedrock::AgentAlias
Properties:
  AgentId: !GetAtt MyAgent.AgentId
  AgentAliasName: string              # Required. e.g. "live" or "v1"
  Description: string
  RoutingConfiguration:
    - AgentVersion: string            # e.g. "1" or "DRAFT"
```

---

## Action Group — OpenAPI Schema Format

Each action group exposes a set of operations the agent can invoke. The schema is **OpenAPI 3.0.0** with these Bedrock-specific rules:

1. All operations must use **POST** (Bedrock always POSTs to the Lambda).
2. Each operation must have an `operationId` (unique across all schemas).
3. Request and response bodies must be `application/json`.
4. `servers` array is **ignored** — Bedrock routes to the Lambda, not a real URL.
5. The `description` field on each operation is used by the model to decide when to call it — write these carefully.

### Minimal action group schema

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "WeatherActions",
    "description": "Weather lookup actions for the agent",
    "version": "1.0.0"
  },
  "paths": {
    "/get_weather": {
      "post": {
        "operationId": "get_weather",
        "description": "Fetch current weather for a given city. Use when the user asks about weather conditions.",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "location": {
                    "type": "string",
                    "description": "City name or airport code, e.g. 'London' or 'LHR'"
                  },
                  "units": {
                    "type": "string",
                    "enum": ["metric", "imperial"],
                    "description": "Temperature unit system"
                  }
                },
                "required": ["location"]
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful weather response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "temperature": { "type": "number" },
                    "conditions": { "type": "string" },
                    "humidity": { "type": "number" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### Supported JSON Schema types in Bedrock

| Type | Supported | Notes |
|------|-----------|-------|
| `string` | ✅ | |
| `number` / `integer` | ✅ | |
| `boolean` | ✅ | |
| `array` | ✅ | Items must be a supported type |
| `object` | ✅ | Nested objects allowed |
| `oneOf` / `anyOf` / `allOf` | ❌ | Not supported — use flat objects |
| `$ref` | ✅ (limited) | Only within the same document |

---

## Lambda Handler Contract

The Lambda function receives this payload structure from Bedrock:

```json
{
  "messageVersion": "1.0",
  "agent": {
    "name": "my-agent",
    "id": "AGENTID123",
    "alias": "ALIASID456",
    "version": "1"
  },
  "inputText": "What's the weather in London?",
  "sessionId": "abc-123",
  "actionGroup": "WeatherActions",
  "apiPath": "/get_weather",
  "httpMethod": "POST",
  "parameters": [],
  "requestBody": {
    "content": {
      "application/json": {
        "properties": [
          { "name": "location", "type": "string", "value": "London" },
          { "name": "units", "type": "string", "value": "metric" }
        ]
      }
    }
  },
  "sessionAttributes": {},
  "promptSessionAttributes": {}
}
```

The Lambda must return:

```json
{
  "messageVersion": "1.0",
  "response": {
    "actionGroup": "WeatherActions",
    "apiPath": "/get_weather",
    "httpMethod": "POST",
    "httpStatusCode": 200,
    "responseBody": {
      "application/json": {
        "body": "{\"temperature\": 12.5, \"conditions\": \"Partly cloudy\", \"humidity\": 78}"
      }
    }
  }
}
```

Note: `responseBody.application/json.body` is a **JSON string** (double-encoded), not a nested object.

---

## Knowledge Base Integration

Bedrock Knowledge Bases use S3 + a vector store (OpenSearch Serverless, Pinecone, Redis, etc.) for RAG.

```yaml
Type: AWS::Bedrock::KnowledgeBase
Properties:
  Name: string
  Description: string
  RoleArn: string                     # IAM role for Bedrock to access S3
  KnowledgeBaseConfiguration:
    Type: VECTOR
    VectorKnowledgeBaseConfiguration:
      EmbeddingModelArn: arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1
  StorageConfiguration:
    Type: OPENSEARCH_SERVERLESS
    OpensearchServerlessConfiguration:
      CollectionArn: string
      VectorIndexName: string
      FieldMapping:
        VectorField: embedding
        TextField: text
        MetadataField: metadata
```

---

## IR → Bedrock Field Mapping

| IR field | Bedrock field | Notes |
|----------|--------------|-------|
| `name` | `AgentName` | Slugified; replace spaces with hyphens |
| `description` | `Description` | Truncated to 200 chars if needed |
| `persona.system_prompt` | `Instruction` | **Truncated to 4,000 chars**. Emit warning if truncated |
| `persona.language` | Not mapped | Include language instruction in the system_prompt if non-English |
| `tools[kind=function\|openapi]` | `ActionGroups[].ApiSchema` | Each tool group becomes one action group |
| `tools[kind=mcp]` | ⚠️ stub only | MCP not natively supported; emit TODO stub comment |
| `tools[kind=shell]` | ⚠️ stub only | Shell not natively supported; emit TODO stub comment |
| `tools[kind=builtin]` | ⚠️ stub only | Builtin tools not available; emit warning |
| `tools[].auth.type=api_key` | Lambda env var | Emit TODO: set `TOOL_API_KEY` in Lambda environment |
| `knowledge[kind=file]` | Knowledge base S3 source | Emit CloudFormation for KB + S3 bucket; file must be uploaded |
| `knowledge[kind=vector_store]` | Knowledge base storage config | Map to OpenSearch Serverless or other vector backend |
| `knowledge[].load_mode=indexed` | Knowledge base (RAG) | Native Bedrock retrieval |
| `knowledge[].load_mode=always` | Prepended to `Instruction` | Inline small files in the instruction if they fit within 4k limit |
| `triggers[kind=cron]` | EventBridge rule | CloudFormation: `AWS::Events::Rule` targeting agent alias |
| `triggers[kind=webhook]` | API Gateway + Lambda | Emit stub Lambda that invokes the agent |
| `constraints.guardrails` | `AWS::Bedrock::Guardrail` | Map known guardrail names to Bedrock content filters |
| `metadata.platform_extensions.bedrock.agent_id` | `AgentId` (outputs) | Preserve on round-trip |
| `metadata.platform_extensions.bedrock.alias_id` | `AgentAliasId` (outputs) | Preserve on round-trip |

### Instruction truncation strategy

When `persona.system_prompt` exceeds 4,000 characters:

1. Emit a `# WARNING: Instruction truncated to 4000 chars` comment in the CloudFormation YAML.
2. Truncate at the last sentence boundary before 4,000 chars.
3. Add a note in `instruction.txt`: `[... truncated — original in ir.json persona.system_prompt]`

---

## Complete CloudFormation Example

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: AgentShift-generated Bedrock agent — pregnancy-companion

Parameters:
  ActionGroupLambdaArn:
    Type: String
    Description: ARN of the Lambda function implementing action group logic

Resources:
  AgentRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: pregnancy-companion-bedrock-role
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: bedrock.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: BedrockInvokeModel
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow
                Action: bedrock:InvokeModel
                Resource: "*"

  PregnancyCompanionAgent:
    Type: AWS::Bedrock::Agent
    Properties:
      AgentName: pregnancy-companion
      AgentResourceRoleArn: !GetAtt AgentRole.Arn
      Description: "24/7 pregnancy companion — answers questions, tracks symptoms"
      Instruction: |
        You are a warm, knowledgeable pregnancy companion. You answer questions
        about pregnancy, track symptoms, provide weekly updates, and support a
        healthy pregnancy journey. Always recommend consulting a healthcare
        provider for medical decisions.
      FoundationModel: anthropic.claude-3-5-sonnet-20241022-v2:0
      IdleSessionTTLInSeconds: 1800
      AutoPrepare: true
      ActionGroups:
        - ActionGroupName: PregnancyTracking
          Description: Tools to log and retrieve pregnancy tracking data
          ActionGroupExecutor:
            Lambda: !Ref ActionGroupLambdaArn
          ApiSchema:
            Payload: |
              {
                "openapi": "3.0.0",
                "info": { "title": "PregnancyTracking", "version": "1.0.0" },
                "paths": {
                  "/log_symptom": {
                    "post": {
                      "operationId": "log_symptom",
                      "description": "Log a pregnancy symptom with severity",
                      "requestBody": {
                        "required": true,
                        "content": {
                          "application/json": {
                            "schema": {
                              "type": "object",
                              "properties": {
                                "symptom": { "type": "string" },
                                "severity": { "type": "integer" },
                                "date": { "type": "string" }
                              },
                              "required": ["symptom"]
                            }
                          }
                        }
                      },
                      "responses": {
                        "200": {
                          "description": "Symptom logged",
                          "content": {
                            "application/json": {
                              "schema": {
                                "type": "object",
                                "properties": { "status": { "type": "string" } }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
          ActionGroupState: ENABLED

  PregnancyCompanionAlias:
    Type: AWS::Bedrock::AgentAlias
    Properties:
      AgentId: !GetAtt PregnancyCompanionAgent.AgentId
      AgentAliasName: live
      Description: Production alias

Outputs:
  AgentId:
    Value: !GetAtt PregnancyCompanionAgent.AgentId
  AliasId:
    Value: !GetAtt PregnancyCompanionAlias.AgentAliasId
```

---

## Emitter Output Layout

```
output/
├── instruction.txt         # Plain-text instruction (≤ 4000 chars)
├── openapi.json            # Action group OpenAPI schema (one file, multiple paths)
├── cloudformation.yaml     # Full CFN template
└── README.md               # Setup instructions (upload to S3, deploy stack, etc.)
```

---

## Stub Comments for Unsupported Features

When IR features have no Bedrock equivalent, emit clearly marked TODO stubs:

```yaml
# TODO [agentshift]: MCP tool 'slack' has no Bedrock equivalent.
# Implement this functionality in the action group Lambda or remove it.
# Original IR tool: { "name": "slack", "kind": "mcp", "description": "..." }
```

```yaml
# TODO [agentshift]: Cron trigger 'daily-tip' mapped to EventBridge rule stub.
# Update ScheduleExpression and Lambda target ARN before deploying.
```

---

## Notes for the Implementing Dev (D08)

1. **Instruction truncation is the most common failure** — always check `len(system_prompt) > 4000` and handle it.
2. **Group IR tools by action group** — if IR has multiple function/openapi tools, decide whether to put them all in one action group or separate groups. Default: one action group named `{agent-name}-actions`.
3. **OpenAPI paths must start with `/`** — use `/{tool_name}` as the path, `tool_name` as `operationId`.
4. **All operations must be POST** — Bedrock ignores the HTTP method in the schema and always POSTs.
5. **Emit a stub Lambda** in the CloudFormation (or reference a parameter) — the dev using the output will need to wire up real logic.
6. **`AutoPrepare: true`** saves a manual "Prepare" step in the console; always emit it.
7. **IAM role** is required — always emit a minimal role with `bedrock:InvokeModel`.
8. **Knowledge bases** require a separate CloudFormation stack or nested stack — flag this clearly in README.md.
9. **Preserve `metadata.platform_extensions.bedrock`** on round-trip (agent_id, alias_id).
10. **Model ID** — default to `anthropic.claude-3-5-sonnet-20241022-v2:0`; allow override via `metadata.platform_extensions.bedrock.foundation_model`.
