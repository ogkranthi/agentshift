# AgentShift — Autonomous Build Crew

## Architecture

AgentShift is built by a team of 4 autonomous agents coordinated through a shared BACKLOG.md.

```
🚢 Chief (coordinator)
├── 📐 Architect (specs, schemas, research)
├── 💻 Dev (Python implementation)
└── 🧪 Tester (tests, validation, QA)
```

## Agent Roles

### 🚢 Chief (`agentshift-chief`)
- **Owns**: Coordination, backlog management, status updates
- **Tools**: sessions_spawn, sessions_send, message, cron
- **Telegram**: Receives commands, sends status updates
- **Does NOT**: Write code, specs, or tests

### 📐 Architect (`agentshift-architect`)
- **Owns**: IR schema, platform format specs, mapping docs
- **Writes to**: `specs/`, `docs/adr/`
- **Tools**: web_search, web_fetch, read, write, edit, exec
- **Sequence**: Produces specs BEFORE dev implements

### 💻 Dev (`agentshift-dev`)
- **Owns**: Python codebase — parsers, emitters, CLI, IR model
- **Writes to**: `src/agentshift/`, `pyproject.toml`
- **Tools**: read, write, edit, exec
- **Sequence**: Implements AFTER architect produces spec

### 🧪 Tester (`agentshift-tester`)
- **Owns**: Test suite, fixtures, config validation
- **Writes to**: `tests/`
- **Tools**: read, write, edit, exec
- **Sequence**: Tests AFTER dev implements; also reviews dev PRs

## Build Flow

1. Chief reads BACKLOG.md, identifies ready tasks
2. Architect researches and writes specs (A-prefixed tasks)
3. Dev implements based on specs (D-prefixed tasks)
4. Tester writes tests and validates (T-prefixed tasks)
5. Tester reviews and merges dev PRs
6. Chief reports progress to Telegram

## Branch Convention
- `agent/architect/{task-id}` — spec branches
- `agent/dev/{task-id}` — implementation branches
- `agent/tester/{task-id}` — test branches

## Project Structure
```
agentshift/
├── src/agentshift/       # Python package
│   ├── cli.py            # Typer CLI
│   ├── ir.py             # IR model
│   ├── parsers/          # Source format parsers
│   └── emitters/         # Target format emitters
├── specs/                # Format specs (by architect)
├── tests/                # Test suite (by tester)
├── docs/                 # Documentation
├── examples/             # Example conversions
├── BACKLOG.md            # Task queue
└── AGENTS.md             # This file
```
