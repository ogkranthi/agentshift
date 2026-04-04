# AutoGen AgentChat — Format Spec

**Version:** autogen-agentchat ≥ 0.4 (2025)
**Direction:** IR → AutoGen JSON (emit only; parse is stretch goal)
**Status:** Spec complete — ready for D33

---

## Overview

Microsoft AutoGen AgentChat is a high-level Python framework for building multi-agent AI systems.
Starting with v0.4 (late 2024), AutoGen uses a **declarative JSON component model** where every
building block (agents, teams, models, tools) can be serialized to/from JSON.

This enables the "AutoGen Studio" visual builder to export/import agent configs as JSON files.

GitHub: https://github.com/microsoft/autogen
Docs:   https://microsoft.github.io/autogen/stable/

---

## Component JSON Schema

Every AutoGen component follows this envelope:

```json
{
  "provider": "<fully.qualified.class.path>",
  "component_type": "agent" | "team" | "model" | "termination" | "tool",
  "version": 1,
  "component_version": 1,
  "description": "Human-readable description",
  "label": "DisplayLabel",
  "config": { /* component-specific fields */ }
}
```

---

## Agent Component: `AssistantAgent`

```json
{
  "provider": "autogen_agentchat.agents.AssistantAgent",
  "component_type": "agent",
  "version": 1,
  "component_version": 1,
  "description": "An agent that provides assistance with tool use.",
  "label": "AssistantAgent",
  "config": {
    "name": "my_agent",
    "system_message": "You are a helpful AI assistant.",
    "model_client": {
      "provider": "autogen_ext.models.openai.OpenAIChatCompletionClient",
      "component_type": "model",
      "version": 1,
      "component_version": 1,
      "description": "Chat completion client for OpenAI hosted models.",
      "label": "OpenAIChatCompletionClient",
      "config": {
        "model": "gpt-4o"
      }
    },
    "tools": [],
    "handoffs": [],
    "model_context": {
      "provider": "autogen_core.model_context.UnboundedChatCompletionContext",
      "component_type": "chat_completion_context",
      "version": 1,
      "component_version": 1,
      "description": "Unbounded chat history context.",
      "label": "UnboundedChatCompletionContext",
      "config": {}
    },
    "description": "An agent that provides assistance with ability to use tools.",
    "model_client_stream": false,
    "reflect_on_tool_use": false,
    "tool_call_summary_format": "{result}"
  }
}
```

### `AssistantAgent.config` Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | `string` | ✅ | Agent identifier (snake_case) |
| `system_message` | `string` | ✅ | System prompt |
| `model_client` | `Component` | ✅ | Model provider config |
| `tools` | `Component[]` | ❌ | Tool component objects |
| `handoffs` | `Component[]` | ❌ | Handoff objects |
| `model_context` | `Component` | ❌ | Chat history handler |
| `description` | `string` | ❌ | Short description |
| `model_client_stream` | `bool` | ❌ | Enable streaming |
| `reflect_on_tool_use` | `bool` | ❌ | Self-reflection after tool calls |
| `tool_call_summary_format` | `string` | ❌ | How to summarize tool results |

---

## Team Component: `RoundRobinGroupChat`

```json
{
  "provider": "autogen_agentchat.teams.RoundRobinGroupChat",
  "component_type": "team",
  "version": 1,
  "component_version": 1,
  "description": "Round-robin multi-agent chat.",
  "label": "RoundRobinGroupChat",
  "config": {
    "participants": [ /* Agent components */ ],
    "termination_condition": {
      "provider": "autogen_agentchat.conditions.TextMentionTermination",
      "component_type": "termination",
      "version": 1,
      "component_version": 1,
      "description": "Terminate when TERMINATE is mentioned.",
      "label": "TextMentionTermination",
      "config": { "text": "TERMINATE" }
    }
  }
}
```

### Available Team Types

| Provider | Description |
|----------|-------------|
| `autogen_agentchat.teams.RoundRobinGroupChat` | Each participant takes turns |
| `autogen_agentchat.teams.SelectorGroupChat` | Model selects next speaker |
| `autogen_agentchat.teams.MagenticOneGroupChat` | Orchestrator-subagent pattern |
| `autogen_agentchat.teams.Swarm` | Handoff-driven routing |

---

## Model Client Components

### OpenAI
```json
{
  "provider": "autogen_ext.models.openai.OpenAIChatCompletionClient",
  "component_type": "model",
  "config": { "model": "gpt-4o" }
}
```

### Azure OpenAI
```json
{
  "provider": "autogen_ext.models.openai.AzureOpenAIChatCompletionClient",
  "component_type": "model",
  "config": {
    "model": "gpt-4o",
    "azure_endpoint": "${AZURE_OPENAI_ENDPOINT}",
    "api_version": "2024-08-01-preview"
  }
}
```

### Anthropic
```json
{
  "provider": "autogen_ext.models.anthropic.AnthropicChatCompletionClient",
  "component_type": "model",
  "config": { "model": "claude-3-5-sonnet-20241022" }
}
```

---

## Tool Component

```json
{
  "provider": "autogen_core.tools.FunctionTool",
  "component_type": "tool",
  "version": 1,
  "component_version": 1,
  "description": "A tool that calls a Python function.",
  "label": "get_weather",
  "config": {
    "name": "get_weather",
    "description": "Get current weather for a city",
    "func": "tools.get_weather"
  }
}
```

---

## Generated Output Structure

The emitter generates a JSON config + Python tools file:

```
{agent_name}_autogen/
├── agent_config.json   # Full AutoGen component config (team + agent + model)
├── tools.py            # Tool function stubs
├── run.py              # Entry point (loads config, runs agent)
├── requirements.txt    # autogen-agentchat + autogen-ext
└── README.md           # How to run + configuration notes
```

---

## IR → AutoGen JSON Mapping (Emitter)

| IR Field | AutoGen Target | Notes |
|----------|----------------|-------|
| `name` | `config.name` (snake_case) + `label` | Also sets team label |
| `description` | `description` + `config.description` | Outer and inner description |
| `persona.system_prompt` | `config.system_message` | Direct; appended with TERMINATE instruction |
| `persona.sections` | Prepended to `system_message` | As `## Section` headers |
| `model` | `model_client.config.model` | Map model names if needed |
| `tools[kind=function]` | `FunctionTool` component in `config.tools` | Typed Python functions in tools.py |
| `tools[kind=shell]` | `FunctionTool` wrapping `subprocess.run()` | Shell command wrapped in function |
| `tools[kind=mcp]` | `MCPToolServer` integration | Via `autogen_ext.tools.mcp` adapter |
| `tools[].name` | `tool.label` + `config.name` | snake_case |
| `tools[].description` | `tool.description` + `config.description` | Direct |
| `knowledge[]` | README note + stub | Use external RAG tool (`autogen_ext.tools.langchain`) |
| `triggers[]` | README note | No native trigger system |
| `constraints.guardrails` | Prepended to `system_message` | Added as `## Rules` prefix |
| `governance` | Inline comments | Manual implementation needed |

### System Message Convention

AutoGen agents are expected to terminate with the word `TERMINATE`. The emitter appends this to the
system message:

```
{original instructions}

When the task is complete, reply with TERMINATE.
```

---

## Full Example: Single-Agent Config (agent_config.json)

```json
{
  "provider": "autogen_agentchat.teams.RoundRobinGroupChat",
  "component_type": "team",
  "version": 1,
  "component_version": 1,
  "description": "AgentShift-generated single-agent team",
  "label": "PregnancyCompanionTeam",
  "config": {
    "participants": [
      {
        "provider": "autogen_agentchat.agents.AssistantAgent",
        "component_type": "agent",
        "version": 1,
        "component_version": 1,
        "description": "24/7 pregnancy companion agent",
        "label": "AssistantAgent",
        "config": {
          "name": "pregnancy_companion",
          "system_message": "You are a 24/7 pregnancy companion...\n\nWhen the task is complete, reply with TERMINATE.",
          "model_client": {
            "provider": "autogen_ext.models.openai.OpenAIChatCompletionClient",
            "component_type": "model",
            "version": 1,
            "component_version": 1,
            "description": "OpenAI Chat Completion",
            "label": "OpenAIChatCompletionClient",
            "config": { "model": "gpt-4o" }
          },
          "tools": [],
          "handoffs": [],
          "model_context": {
            "provider": "autogen_core.model_context.UnboundedChatCompletionContext",
            "component_type": "chat_completion_context",
            "version": 1,
            "component_version": 1,
            "description": "Unbounded chat completion context",
            "label": "UnboundedChatCompletionContext",
            "config": {}
          },
          "description": "24/7 pregnancy companion",
          "model_client_stream": false,
          "reflect_on_tool_use": false,
          "tool_call_summary_format": "{result}"
        }
      }
    ],
    "termination_condition": {
      "provider": "autogen_agentchat.conditions.TextMentionTermination",
      "component_type": "termination",
      "version": 1,
      "component_version": 1,
      "description": "Terminate when TERMINATE is mentioned",
      "label": "TextMentionTermination",
      "config": { "text": "TERMINATE" }
    }
  }
}
```

---

## Platform Constraints

| Constraint | Detail |
|------------|--------|
| TERMINATE convention | Agents must say `TERMINATE` to end conversation |
| Model naming | Different than OpenAI SDK — full model client class required |
| Tools via Python | Tool implementations are Python functions; JSON config references them |
| No native triggers | External scheduler required |
| No native knowledge base | Use RAG tool components (`autogen_ext.tools.langchain`) |

---

## Portability Notes

- **Instructions**: ✅ 100% portable (no char limit)
- **Tools**: ✅ Stubs generated + FunctionTool references in JSON
- **Model**: ✅ Model client component maps to major providers
- **Knowledge**: ⚠️ README + tool stub
- **Triggers**: ⚠️ README only
- **Multi-agent**: ⚠️ Single-agent RoundRobin by default; multi-agent from AGENTS.md registry

---

## MCP Tool Integration

AutoGen supports MCP servers via the `autogen_ext.tools.mcp` package:

```python
from autogen_ext.tools.mcp import StdioMCPToolAdapter, SseMCPToolAdapter
from mcp import StdioServerParameters

# Stdio MCP server
mcp_tool = StdioMCPToolAdapter(
    server_params=StdioServerParameters(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]),
    tool_name="filesystem",
)

# Add to agent's tools list
agent = AssistantAgent(name="agent", tools=[mcp_tool], ...)
```

In JSON component config, MCP tools are referenced as:
```json
{
  "provider": "autogen_ext.tools.mcp.StdioMCPToolAdapter",
  "component_type": "tool",
  "config": {
    "server_params": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]},
    "tool_name": "filesystem"
  }
}
```

The emitter should generate MCP tool components when `ir.tools[kind=mcp]` is present.

---

## References

- AutoGen GitHub: https://github.com/microsoft/autogen
- AgentChat Docs: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/
- AutoGen Studio: https://microsoft.github.io/autogen/stable/user-guide/autogenstudio-user-guide/
- Component Model: https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/framework/component-config.html
