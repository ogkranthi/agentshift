# LangGraph Agent Format Specification

**File:** `specs/langgraph-agent-format.md`
**Version:** 1.0
**Status:** Canonical
**Author:** AgentShift Architect

---

## Overview

This document describes the LangGraph agent format: how agents are defined as stateful graphs, how tools are bound, what the state schema looks like, and how agents are packaged and deployed on the LangGraph Platform (LangSmith Deployment). This spec is the authoritative reference for the AgentShift `LangGraphEmitter` — implementers should be able to emit a fully functional LangGraph agent package from IR without additional research.

LangGraph is a low-level orchestration framework for building stateful, long-running agents as directed graphs. It is built by LangChain Inc and runs in Python (3.9+) and JavaScript/TypeScript (Node 18+). This spec focuses on the Python implementation, which is the target for AgentShift's emitter.

---

## Table of Contents

1. [Core Concepts](#1-core-concepts)
2. [Graph Definition (StateGraph API)](#2-graph-definition-stategraph-api)
3. [State Schema](#3-state-schema)
4. [Nodes](#4-nodes)
5. [Edges and Routing](#5-edges-and-routing)
6. [Tool Binding](#6-tool-binding)
7. [Memory and Persistence (Checkpointers)](#7-memory-and-persistence-checkpointers)
8. [Compilation](#8-compilation)
9. [Invocation and Streaming](#9-invocation-and-streaming)
10. [Deployment Package Structure](#10-deployment-package-structure)
11. [langgraph.json Configuration File](#11-langgraphjson-configuration-file)
12. [IR → LangGraph Mapping](#12-ir--langgraph-mapping)
13. [Complete Emitter Output Example](#13-complete-emitter-output-example)

---

## 1. Core Concepts

| Concept | Description |
|---------|-------------|
| **StateGraph** | The primary class for building an agent graph. Accepts a state schema and returns a builder. |
| **State** | A `TypedDict` (or `Annotated` variant) representing the shared data passed between nodes. |
| **Node** | A Python function (or runnable) that takes `State` and returns a partial state update. |
| **Edge** | A directed connection from one node to another. Can be unconditional or conditional. |
| **Checkpointer** | A persistence backend that snapshots state after every super-step. Enables memory, interrupts, and time-travel. |
| **CompiledStateGraph** | The result of calling `.compile()` on a `StateGraph`. This is the deployable artifact. |
| **Thread** | A unique `thread_id` scoping a sequence of runs. Required when a checkpointer is attached. |
| **`START` / `END`** | Special sentinel nodes representing the entry and exit points of the graph. |

---

## 2. Graph Definition (StateGraph API)

### 2.1 Imports

```python
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from typing import Annotated
from typing_extensions import TypedDict
import operator
```

### 2.2 Basic Pattern

```python
# 1. Define state schema
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# 2. Create builder
builder = StateGraph(AgentState)

# 3. Add nodes
builder.add_node("llm_call", llm_call_fn)
builder.add_node("tools", tool_node_fn)

# 4. Connect with edges
builder.add_edge(START, "llm_call")
builder.add_conditional_edges("llm_call", should_continue, ["tools", END])
builder.add_edge("tools", "llm_call")

# 5. Compile
graph = builder.compile()
```

### 2.3 StateGraph Constructor

```python
StateGraph(
    state_schema: Type[State],          # TypedDict or dataclass
    config_schema: Type | None = None,  # Optional: configurable fields
    input: Type | None = None,          # Optional: input-only schema subset
    output: Type | None = None,         # Optional: output-only schema subset
)
```

### 2.4 MessagesState Shorthand

LangGraph ships a pre-built `MessagesState` for message-passing agents:

```python
from langgraph.graph import MessagesState
# Equivalent to:
# class MessagesState(TypedDict):
#     messages: Annotated[list[AnyMessage], add_messages]
```

Most ReAct-style agents can use `MessagesState` directly without defining a custom state schema.

---

## 3. State Schema

The state schema is the central data structure flowing through the graph. It is a Python `TypedDict` (or Pydantic model in advanced usage).

### 3.1 Plain TypedDict

```python
from typing_extensions import TypedDict

class State(TypedDict):
    input: str
    result: str
    steps: int
```

Each key is a **channel**. By default, each channel uses **last-write-wins** (the latest node return value overwrites).

### 3.2 Annotated Reducers

Use `Annotated[T, reducer]` to specify how to merge values from multiple nodes writing to the same channel:

```python
from typing import Annotated
import operator

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # append new messages
    scores: Annotated[list[float], operator.add]          # concatenate lists
    count: Annotated[int, operator.add]                   # sum integers
```

### 3.3 Built-in Reducers

| Reducer | Behavior | Import |
|---------|----------|--------|
| `add_messages` | Appends new messages; deduplicates by `id` | `from langgraph.graph.message import add_messages` |
| `operator.add` | Concatenates lists or sums numbers | `import operator` |
| Custom function | Any `(current, update) -> new` function | User-defined |

### 3.4 Pre-built State Classes

| Class | Fields | Use Case |
|-------|--------|----------|
| `MessagesState` | `messages: Annotated[list[AnyMessage], add_messages]` | Chat / ReAct agents |
| Custom TypedDict | User-defined channels | Domain-specific agents |

### 3.5 Input/Output Subsets

For clean API surfaces, define separate input and output schemas:

```python
class InputState(TypedDict):
    user_input: str

class OutputState(TypedDict):
    answer: str

class FullState(InputState, OutputState):
    internal_steps: list[str]

graph = StateGraph(FullState, input=InputState, output=OutputState)
```

---

## 4. Nodes

A node is a Python function that:
- Accepts the current state (dict or TypedDict)
- Returns a **partial** state dict (only the keys it wants to update)

### 4.1 Basic Node

```python
def my_node(state: AgentState) -> dict:
    # Read from state
    messages = state["messages"]
    # Do work...
    # Return only what changed
    return {"messages": [AIMessage(content="Hello")]}
```

### 4.2 LLM Call Node

```python
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage

llm = init_chat_model("claude-sonnet-4-6", temperature=0)
llm_with_tools = llm.bind_tools(tools)

def call_llm(state: AgentState) -> dict:
    system = SystemMessage(content="You are a helpful assistant.")
    response = llm_with_tools.invoke([system] + state["messages"])
    return {"messages": [response]}
```

### 4.3 Tool Execution Node

```python
from langchain_core.messages import ToolMessage

def tool_node(state: AgentState) -> dict:
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        tool = tools_by_name[tool_call["name"]]
        result = tool.invoke(tool_call["args"])
        results.append(ToolMessage(
            content=str(result),
            tool_call_id=tool_call["id"]
        ))
    return {"messages": results}
```

### 4.4 ToolNode Helper

LangGraph ships a pre-built `ToolNode`:

```python
from langgraph.prebuilt import ToolNode

tools = [search_web, get_weather]
tool_executor = ToolNode(tools)
builder.add_node("tools", tool_executor)
```

### 4.5 Adding Nodes

```python
# By function (name inferred from function name)
builder.add_node(my_function)

# With explicit name
builder.add_node("my_node", my_function)

# With a LangChain runnable
builder.add_node("llm", my_chain)
```

---

## 5. Edges and Routing

### 5.1 Unconditional Edge

Always routes from source to target:

```python
builder.add_edge(START, "llm_call")
builder.add_edge("tool_executor", "llm_call")
builder.add_edge("llm_call", END)
```

### 5.2 Conditional Edge

Routes based on a function that inspects state:

```python
from typing import Literal

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return "__end__"

builder.add_conditional_edges(
    "llm_call",          # source node
    should_continue,     # routing function
    ["tools", END]       # allowed destinations (for visualization)
)
```

The routing function can return:
- A string (node name)
- `END` / `"__end__"` to stop
- A list of node names (for parallel fan-out)

### 5.3 tools_condition Helper

LangGraph ships a pre-built routing function for ReAct agents:

```python
from langgraph.prebuilt import tools_condition

builder.add_conditional_edges("llm_call", tools_condition)
# Equivalent to: route to "tools" if last message has tool_calls, else END
```

### 5.4 Entry Point

`START` is a special sentinel; always use it as the first edge source:

```python
builder.add_edge(START, "first_node")
```

### 5.5 Set Entry Point (Alternative)

```python
builder.set_entry_point("first_node")  # deprecated; prefer add_edge(START, ...)
```

---

## 6. Tool Binding

### 6.1 Defining Tools with `@tool`

```python
from langchain.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get current weather for a location.
    
    Args:
        location: City name or airport code (e.g., 'San Francisco' or 'SFO')
    """
    # Implementation
    return f"Weather in {location}: 72°F, sunny"

@tool
def search_web(query: str) -> str:
    """Search the web for information.
    
    Args:
        query: The search query string
    """
    return f"Search results for: {query}"
```

**Important:** The docstring becomes the tool description seen by the LLM. The `Args:` section describes parameters. Keep them clear and specific.

### 6.2 Binding Tools to an LLM

```python
tools = [get_weather, search_web]
tools_by_name = {t.name: t for t in tools}

# Bind tools — adds function definitions to LLM API calls
llm_with_tools = llm.bind_tools(tools)
```

`bind_tools` converts LangChain tool objects into the LLM provider's native function-calling format (OpenAI function specs, Anthropic tool specs, etc.).

### 6.3 Structured Tool Parameters (Pydantic)

For complex parameter schemas, use Pydantic:

```python
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

class WeatherInput(BaseModel):
    location: str = Field(description="City name or airport code")
    units: str = Field(default="metric", description="'metric' or 'imperial'")

def get_weather(location: str, units: str = "metric") -> str:
    """Get current weather."""
    ...

weather_tool = StructuredTool.from_function(
    func=get_weather,
    name="get_weather",
    description="Fetch current weather for a location",
    args_schema=WeatherInput,
)
```

### 6.4 Tool Auth and Environment Variables

Tools that require API keys should read from environment variables:

```python
import os

@tool
def call_external_api(query: str) -> str:
    """Call external API."""
    api_key = os.environ["MY_API_KEY"]  # raise if missing
    # ...
```

### 6.5 MCP Tool Wrappers

LangGraph can use MCP servers as tool sources via `langchain-mcp-adapters`:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

server_params = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-brave-search"],
    env={"BRAVE_API_KEY": os.environ["BRAVE_API_KEY"]}
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        mcp_tools = await load_mcp_tools(session)

tools = mcp_tools  # use exactly like @tool-decorated functions
```

---

## 7. Memory and Persistence (Checkpointers)

### 7.1 Checkpointer Types

| Checkpointer | Package | Use Case |
|-------------|---------|----------|
| `InMemorySaver` | `langgraph` | Development and testing only |
| `AsyncInMemorySaver` | `langgraph` | Async development |
| `PostgresSaver` | `langgraph-checkpoint-postgres` | Production (sync) |
| `AsyncPostgresSaver` | `langgraph-checkpoint-postgres` | Production (async) |
| `SqliteSaver` | `langgraph-checkpoint-sqlite` | Local persistence |
| Agent Server managed | LangSmith Deployment | Production managed |

### 7.2 Attaching a Checkpointer

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# Must pass thread_id when invoking
config = {"configurable": {"thread_id": "user-123"}}
result = graph.invoke({"messages": [HumanMessage("Hello")]}, config)
```

### 7.3 Thread-based Memory

With a checkpointer, each `thread_id` is an isolated conversation:

```python
# First turn
config = {"configurable": {"thread_id": "session-abc"}}
graph.invoke({"messages": [HumanMessage("My name is Alice")]}, config)

# Second turn — graph remembers "Alice"
graph.invoke({"messages": [HumanMessage("What's my name?")]}, config)
```

### 7.4 Long-term Memory Store

For cross-session memory, use a `BaseStore`:

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()
graph = builder.compile(checkpointer=checkpointer, store=store)

# In a node, access the store via config
def memory_node(state: AgentState, config: RunnableConfig, *, store: BaseStore) -> dict:
    namespace = ("user_profiles", config["configurable"]["user_id"])
    items = store.search(namespace, query="preferences")
    store.put(namespace, "preference-1", {"topic": "weather"})
    return {"messages": []}
```

### 7.5 PostgreSQL Checkpointer (Production)

```python
from langgraph.checkpoint.postgres import PostgresSaver

conn_string = "postgresql://user:pass@host:5432/db"
checkpointer = PostgresSaver.from_conn_string(conn_string)
checkpointer.setup()  # Creates tables on first run

graph = builder.compile(checkpointer=checkpointer)
```

---

## 8. Compilation

The `compile()` call validates the graph structure and returns a `CompiledStateGraph` (also called `CompiledGraph`).

### 8.1 Basic Compilation

```python
graph = builder.compile()
```

### 8.2 Compilation with Options

```python
from langgraph.checkpoint.memory import InMemorySaver

graph = builder.compile(
    checkpointer=InMemorySaver(),   # Persistence backend
    interrupt_before=["human_review"],  # Pause before these nodes
    interrupt_after=["llm_call"],   # Pause after these nodes
    debug=False,                    # Enable debug logging
)
```

### 8.3 Interrupt Points (Human-in-the-Loop)

```python
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["approval_node"],  # Pause before node runs
)

# First invoke: stops before "approval_node"
state = graph.invoke({"messages": [HumanMessage("Please draft an email")]}, config)

# Inspect state, modify if needed, then resume
graph.update_state(config, {"approved": True})
result = graph.invoke(None, config)  # Resume from checkpoint
```

### 8.4 Compiled Graph Methods

| Method | Description |
|--------|-------------|
| `graph.invoke(input, config)` | Synchronous run, returns final state |
| `graph.stream(input, config, stream_mode)` | Streaming run, yields chunks |
| `graph.ainvoke(input, config)` | Async invoke |
| `graph.astream(input, config, stream_mode)` | Async streaming |
| `graph.get_state(config)` | Get current checkpoint state |
| `graph.update_state(config, values)` | Inject state update (for HITL) |
| `graph.get_state_history(config)` | List all checkpoints for thread |
| `graph.get_graph()` | Return graph visualization object |
| `graph.get_graph().draw_mermaid()` | Get Mermaid diagram string |
| `graph.get_graph().draw_mermaid_png()` | Get PNG bytes of diagram |

---

## 9. Invocation and Streaming

### 9.1 Invoke

```python
from langchain_core.messages import HumanMessage

result = graph.invoke(
    {"messages": [HumanMessage(content="What is the weather in NYC?")]},
    config={"configurable": {"thread_id": "session-1"}}
)
# result is the final state dict
print(result["messages"][-1].content)
```

### 9.2 Streaming Modes

```python
# Stream node updates (one dict per node execution)
for chunk in graph.stream(input, config, stream_mode="updates"):
    print(chunk)
    # {"llm_call": {"messages": [AIMessage(...)]}}

# Stream full state at each step
for state in graph.stream(input, config, stream_mode="values"):
    print(state["messages"][-1])

# Stream LLM tokens (requires streaming-enabled LLM)
for chunk in graph.stream(input, config, stream_mode="messages"):
    print(chunk)  # (AIMessageChunk, metadata)
```

### 9.3 Config Dictionary

```python
config = {
    "configurable": {
        "thread_id": "unique-session-id",   # Required with checkpointer
        "user_id": "user-456",              # Custom configurable fields
    },
    "recursion_limit": 50,                  # Max steps (default: 25)
    "tags": ["production", "weather-agent"],
}
```

---

## 10. Deployment Package Structure

### 10.1 Directory Layout

The AgentShift emitter should produce this directory structure:

```
{agent_name}/
├── {agent_name}/              # Python package
│   ├── __init__.py
│   ├── agent.py               # Main graph definition; exports `graph`
│   ├── state.py               # State schema definition
│   ├── nodes.py               # Node function implementations
│   ├── tools.py               # Tool definitions
│   └── prompts.py             # System prompt and message templates
├── tests/
│   └── test_agent.py          # Smoke tests
├── .env.example               # Required environment variables
├── requirements.txt           # Python dependencies
├── langgraph.json             # LangGraph Platform deployment config
└── README.md                  # Usage and setup instructions
```

### 10.2 `requirements.txt` Minimum Dependencies

```
langgraph>=0.2.0
langchain>=0.3.0
langchain-core>=0.3.0
langchain-anthropic>=0.3.0      # or langchain-openai, etc.
langgraph-checkpoint-postgres    # for production persistence
python-dotenv>=1.0.0
```

### 10.3 `.env.example`

```bash
# LLM provider
ANTHROPIC_API_KEY=your-key-here
# or
OPENAI_API_KEY=your-key-here

# LangSmith (optional, for observability)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-key-here
LANGSMITH_PROJECT=my-agent-project

# Tool-specific env vars
MY_TOOL_API_KEY=your-key-here
```

---

## 11. `langgraph.json` Configuration File

The `langgraph.json` file is the deployment manifest consumed by the LangGraph CLI and LangSmith Deployment Platform. It specifies where graphs live, what dependencies are needed, and deployment options.

### 11.1 Full Schema

```json
{
  "python_version": "3.11",
  "dependencies": [
    ".",
    "langchain-anthropic"
  ],
  "graphs": {
    "agent": "./my_agent/agent.py:graph"
  },
  "env": ".env",
  "base_image": "langchain/langgraph-api:latest",
  "image_distro": "debian",
  "store": {
    "index": {
      "embed": "openai:text-embedding-3-small",
      "dims": 1536,
      "fields": ["$"]
    },
    "ttl": {
      "refresh_on_read": true,
      "default_ttl": 10080,
      "sweep_interval_minutes": 60
    }
  },
  "dockerfile_lines": [
    "RUN apt-get install -y curl"
  ],
  "http": {
    "disable_assistants": false,
    "disable_threads": false
  },
  "auth": "./my_agent/auth.py:auth"
}
```

### 11.2 Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `python_version` | string | No | Python version. e.g. `"3.11"`. Default: `"3.11"` |
| `dependencies` | array | **Yes** | List of pip packages or local paths. Use `"."` for local package. |
| `graphs` | object | **Yes** | Map of `{graph_id: "path/to/file.py:variable"}`. Variable must be a `CompiledStateGraph` or a callable returning one. |
| `env` | string or object | No | Path to `.env` file, or inline `{"KEY": "value"}` map |
| `base_image` | string | No | Docker base image tag. Default: `langchain/langgraph-api:latest` |
| `image_distro` | string | No | Linux distro: `"debian"`, `"wolfi"`, `"bookworm"`, `"bullseye"` |
| `store` | object | No | Long-term memory store configuration |
| `store.index` | object | No | Semantic search config: `embed` (model), `dims` (vector size), `fields` (JSON paths) |
| `store.ttl` | object | No | Item expiration config |
| `dockerfile_lines` | array | No | Additional Dockerfile `RUN` instructions for system dependencies |
| `http` | object | No | API endpoint toggles |
| `auth` | string | No | Path to custom auth handler: `"path/to/file.py:handler_var"` |

### 11.3 Graph Reference Formats

```json
{
  "graphs": {
    "my_agent": "./pkg/agent.py:graph",
    "factory_agent": "./pkg/agent.py:make_graph"
  }
}
```

- `./pkg/agent.py:graph` — `graph` is a `CompiledStateGraph` instance
- `./pkg/agent.py:make_graph` — `make_graph` is a callable taking `RunnableConfig` and returning a graph

### 11.4 Multiple Graphs

One deployment can expose multiple graphs:

```json
{
  "graphs": {
    "research_agent": "./agents/research.py:graph",
    "writer_agent": "./agents/writer.py:graph",
    "router": "./agents/router.py:graph"
  }
}
```

---

## 12. IR → LangGraph Mapping

This table describes how each AgentShift IR field maps to LangGraph artifacts.

### 12.1 Top-level Fields

| IR Field | LangGraph Artifact | Notes |
|----------|-------------------|-------|
| `name` | Directory name, package name, graph ID in `langgraph.json` | Converted to valid Python package name (hyphens → underscores) |
| `description` | README.md heading, docstring on `graph` object | |
| `version` | `__version__` in `__init__.py`, `requirements.txt` comment | |
| `author` | README.md, pyproject.toml if present | |
| `homepage` | README.md links | |

### 12.2 Persona

| IR Field | LangGraph Artifact |
|----------|--------------------|
| `persona.system_prompt` | `SystemMessage(content=...)` prepended to messages in `call_llm()` node in `nodes.py` |
| `persona.language` | Comment in system prompt: `# Language: {language}` |
| `persona.personality_notes` | Comment in `prompts.py` above the system prompt string |

**Emitter pattern:**
```python
# prompts.py
SYSTEM_PROMPT = """
{persona.system_prompt}
""".strip()
```

```python
# nodes.py
from .prompts import SYSTEM_PROMPT
from langchain_core.messages import SystemMessage

def call_llm(state: AgentState) -> dict:
    response = llm_with_tools.invoke(
        [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    )
    return {"messages": [response]}
```

### 12.3 Tools

| IR Tool Kind | LangGraph Implementation |
|-------------|--------------------------|
| `function` | `@tool`-decorated function in `tools.py`; parameters from `tool.parameters` |
| `mcp` | `load_mcp_tools()` via `langchain-mcp-adapters`; server config from `tool.endpoint` |
| `openapi` | `requests`-based `@tool` wrapping the endpoint; auth from `tool.auth` |
| `shell` | `@tool` wrapping `subprocess.run()`; only valid for local dev, warn in README |
| `builtin` | Skip (LangGraph doesn't have builtin tools like Claude Code does) |
| `unknown` | Emit stub `@tool` with `# TODO: implement` comment |

**Tool parameter mapping:**
```python
# IR tool.parameters schema → @tool with Pydantic model
from pydantic import BaseModel, Field

class GetWeatherInput(BaseModel):
    location: str = Field(description="City name or airport code")
    units: str = Field(default="metric", description="'metric' or 'imperial'")

@tool(args_schema=GetWeatherInput)
def get_weather(location: str, units: str = "metric") -> str:
    """Get current weather for a location."""
    # TODO: implement
    raise NotImplementedError
```

**Auth mapping:**

| IR Auth Type | LangGraph Implementation |
|-------------|--------------------------|
| `none` | No auth in tool |
| `api_key` | `os.environ["{env_var}"]` in tool body |
| `bearer` | `Authorization: Bearer {os.environ[env_var]}` in requests call |
| `basic` | Basic auth tuple from env vars |
| `oauth2` | Stub with `# TODO: OAuth2 setup` comment |
| `config_key` | `# TODO: Map from OpenClaw config key {config_key}` comment |

### 12.4 Knowledge Sources

| IR Knowledge Kind | LangGraph Implementation |
|------------------|--------------------------|
| `file` / `directory` | `@tool` wrapping `open(path).read()` or `os.listdir()`; path from `knowledge.path` |
| `url` | `@tool` using `requests.get(url)` with BeautifulSoup parsing |
| `vector_store` | `@tool` stub with `# TODO: connect to vector store at {path}` |
| `database` | `@tool` stub with `# TODO: connect to DB at {path}` |
| `s3` | `@tool` stub with `# TODO: implement S3 retrieval` |

**Load mode mapping:**

| `load_mode` | LangGraph Pattern |
|-------------|-------------------|
| `always` | Pre-load content at agent initialization; inject into system prompt |
| `on_demand` | Expose as `@tool`; agent calls when needed |
| `indexed` | Expose as retrieval `@tool` backed by a vector store |

### 12.5 Triggers

Triggers are **not** natively handled by LangGraph itself — they require external scheduling:

| IR Trigger Kind | LangGraph/External Implementation |
|----------------|-----------------------------------|
| `cron` | Python `schedule` library or APScheduler calling `graph.invoke()`; or LangSmith Deployment cron jobs |
| `webhook` | FastAPI endpoint that calls `graph.invoke()` |
| `message` | Messaging platform webhook → FastAPI → `graph.invoke()` |
| `event` | Event bus consumer → `graph.invoke()` |
| `manual` | Direct invocation only |

**Emitter output for cron triggers:**
```python
# In README.md, generate a cron setup example:
# To run on schedule: cron_expr from trigger
# import schedule
# schedule.every().day.at("09:00").do(run_agent)
# Or use LangSmith Deployment cron configuration
```

### 12.6 Constraints

| IR Constraint | LangGraph Handling |
|--------------|-------------------|
| `max_instruction_chars` | Truncate `SYSTEM_PROMPT` if it exceeds limit; warn in README |
| `supported_os` | Note in README and `.env.example` |
| `required_bins` | Document in README as prerequisites |
| `guardrails` | Append guardrail instructions to system prompt |
| `topic_restrictions` | Append "Do not discuss: {topic}" to system prompt |

### 12.7 Metadata

| IR Metadata Field | LangGraph Handling |
|------------------|-------------------|
| `source_platform` | Comment in `agent.py`: `# Converted from {source_platform} via AgentShift` |
| `emoji` | README.md heading emoji |
| `tags` | README.md tags section, `langgraph.json` labels |
| `created_at` | Comment in generated files |

---

## 13. Complete Emitter Output Example

Given an IR for the `weather` agent, the emitter produces:

### `weather/langgraph.json`

```json
{
  "python_version": "3.11",
  "dependencies": ["."],
  "graphs": {
    "weather": "./weather/agent.py:graph"
  },
  "env": ".env"
}
```

### `weather/weather/state.py`

```python
"""State schema for the weather agent."""
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Working state passed between nodes."""
    messages: Annotated[list[AnyMessage], add_messages]
```

### `weather/weather/prompts.py`

```python
"""System prompt and message templates for the weather agent."""

SYSTEM_PROMPT = """
You are a helpful weather assistant. You provide current weather information
and forecasts for any location the user asks about. Use the available tools
to fetch accurate, up-to-date weather data.
""".strip()
```

### `weather/weather/tools.py`

```python
"""Tools available to the weather agent."""
import os
import requests
from langchain.tools import tool
from pydantic import BaseModel, Field


class GetWeatherInput(BaseModel):
    location: str = Field(description="City name or airport code (e.g. 'San Francisco')")
    units: str = Field(default="metric", description="Temperature units: 'metric' or 'imperial'")


@tool(args_schema=GetWeatherInput)
def get_weather(location: str, units: str = "metric") -> str:
    """Get current weather for a location."""
    api_key = os.environ["OPENWEATHER_API_KEY"]
    url = f"https://api.openweathermap.org/data/2.5/weather"
    resp = requests.get(url, params={"q": location, "units": units, "appid": api_key})
    resp.raise_for_status()
    data = resp.json()
    return f"{location}: {data['main']['temp']}°, {data['weather'][0]['description']}"


TOOLS = [get_weather]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
```

### `weather/weather/nodes.py`

```python
"""Node functions for the weather agent."""
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, ToolMessage
from .state import AgentState
from .tools import TOOLS, TOOLS_BY_NAME
from .prompts import SYSTEM_PROMPT

_llm = init_chat_model("claude-sonnet-4-6", temperature=0)
_llm_with_tools = _llm.bind_tools(TOOLS)


def call_llm(state: AgentState) -> dict:
    """Call the LLM with tools bound."""
    response = _llm_with_tools.invoke(
        [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    )
    return {"messages": [response]}


def call_tools(state: AgentState) -> dict:
    """Execute tool calls from the last LLM message."""
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        tool = TOOLS_BY_NAME[tool_call["name"]]
        result = tool.invoke(tool_call["args"])
        results.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    return {"messages": results}
```

### `weather/weather/agent.py`

```python
"""
Weather agent — compiled LangGraph graph.

Converted from OpenClaw via AgentShift (https://github.com/agentshift/agentshift)
Source: openclaw
"""
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .nodes import call_llm, call_tools


def _should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """Route to tools if the LLM made a tool call, otherwise end."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "__end__"


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("llm_call", call_llm)
    builder.add_node("tools", call_tools)
    builder.add_edge(START, "llm_call")
    builder.add_conditional_edges("llm_call", _should_continue, ["tools", END])
    builder.add_edge("tools", "llm_call")
    return builder


graph = build_graph().compile()
```

### `weather/weather/__init__.py`

```python
"""Weather agent — LangGraph implementation."""
from .agent import graph

__version__ = "1.0.0"
__all__ = ["graph"]
```

### `weather/requirements.txt`

```
langgraph>=0.2.0
langchain>=0.3.0
langchain-core>=0.3.0
langchain-anthropic>=0.3.0
python-dotenv>=1.0.0
requests>=2.31.0
```

### `weather/.env.example`

```bash
ANTHROPIC_API_KEY=your-anthropic-key
OPENWEATHER_API_KEY=your-openweather-key

# LangSmith observability (optional)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=weather-agent
```

### `weather/README.md`

```markdown
# ☀️ weather — LangGraph Agent

> Get current weather and forecasts via wttr.in or Open-Meteo.

Generated by [AgentShift](https://github.com/agentshift/agentshift) from OpenClaw SKILL.md.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your API keys
3. Run locally: `langgraph dev`

## Usage

\```python
from langchain_core.messages import HumanMessage
from weather.agent import graph

result = graph.invoke({"messages": [HumanMessage("What's the weather in NYC?")]})
print(result["messages"][-1].content)
\```

## Deploy to LangSmith

\```bash
pip install langgraph-cli
langgraph deploy
\```

## Required Environment Variables

- `ANTHROPIC_API_KEY` — Anthropic API key for Claude
- `OPENWEATHER_API_KEY` — OpenWeatherMap API key
```

---

## Appendix A: Pre-built ReAct Agent

LangGraph ships a `create_react_agent` helper for simple tool-calling agents:

```python
from langgraph.prebuilt import create_react_agent
from langchain.chat_models import init_chat_model

llm = init_chat_model("claude-sonnet-4-6", temperature=0)
tools = [get_weather, search_web]

graph = create_react_agent(
    model=llm,
    tools=tools,
    state_modifier=SYSTEM_PROMPT,  # or SystemMessage(content=...)
    checkpointer=InMemorySaver(),
)
```

**When to use vs. custom graph:**
- Use `create_react_agent` for simple tool-calling agents with standard ReAct loop
- Use custom `StateGraph` when you need: custom state fields, multi-step pipelines, parallel execution, human-in-the-loop, or non-standard routing

For AgentShift emitter: prefer custom `StateGraph` (explicit, easier to inspect) but mention `create_react_agent` as an alternative in the README.

---

## Appendix B: Functional API

LangGraph also supports a functional style without explicit graph declaration:

```python
from langgraph.func import entrypoint, task

@task
def call_llm_task(messages):
    return llm_with_tools.invoke(messages)

@task  
def call_tool_task(tool_call):
    return tools_by_name[tool_call["name"]].invoke(tool_call)

@entrypoint()
def agent(messages):
    response = call_llm_task(messages).result()
    while response.tool_calls:
        tool_results = [call_tool_task(tc).result() for tc in response.tool_calls]
        messages = messages + [response] + tool_results
        response = call_llm_task(messages).result()
    return messages + [response]
```

This is functionally equivalent to the Graph API. The emitter should use the Graph API (easier to visualize and debug).

---

## Appendix C: Checkpointer Summary

```
Development:  InMemorySaver (no persistence across process restarts)
Production:   PostgresSaver / AsyncPostgresSaver
Local file:   SqliteSaver
Managed:      LangSmith Deployment Agent Server (automatic, no config needed)
```

---

*Spec version 1.0 — AgentShift Architect*
