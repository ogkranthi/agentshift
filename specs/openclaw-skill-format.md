# OpenClaw SKILL.md Format Spec

**Status:** Canonical
**Source:** Observed from `~/.nvm/versions/node/v22.22.1/lib/node_modules/openclaw/skills/` and `~/.openclaw/skills/`

---

## Overview

An OpenClaw skill is a directory containing a required `SKILL.md` file and optional supporting files. The `SKILL.md` follows a **YAML frontmatter + Markdown body** pattern.

```
skill-name/
├── SKILL.md               # Required — identity + instructions
├── AGENTS.md              # Optional — workspace/session rules for the agent
├── SOUL.md                # Optional — agent personality and values
├── USER.md                # Optional — user profile and preferences
├── IDENTITY.md            # Optional — agent name, creature, emoji
├── TOOLS.md               # Optional — local tool/device notes
├── HEARTBEAT.md           # Optional — periodic check tasks
├── BOOTSTRAP.md           # Optional — first-run initialization script
├── knowledge/             # Optional — reference documents (loaded on demand)
│   ├── week-by-week.md
│   └── nutrition.md
├── data/                  # Optional — runtime data written by the agent
│   ├── symptoms-log.md
│   └── appointments.md
├── scripts/               # Optional — executable scripts
├── references/            # Optional — detailed reference docs
├── assets/                # Optional — output files (templates, images)
└── .openclaw/
    └── workspace-state.json   # Runtime state (auto-managed)
```

---

## SKILL.md Structure

```
---
<YAML frontmatter>
---

# Skill Title

<Markdown body — agent instructions>
```

The YAML frontmatter and Markdown body are separated by `---` delimiters.

---

## YAML Frontmatter Fields

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Skill slug. Lowercase, hyphens. e.g. `weather`, `pregnancy-companion`. Must match the directory name. |
| `description` | string | One-sentence description + trigger guidance. This is the **primary triggering signal** — OpenClaw reads only `name` and `description` to decide when to load the skill. |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `homepage` | URI | URL for the tool's documentation or project page. |
| `os` | string[] | Operating systems. Values: `darwin`, `linux`, `windows`. Omit for cross-platform. |
| `metadata` | object | Nested platform-specific metadata (see below). |

### `metadata.openclaw` Object

The `metadata` field always wraps an `openclaw` key:

```yaml
metadata:
  openclaw:
    emoji: "☔"
    requires:
      bins: ["curl"]
      anyBins: ["claude", "codex"]
      config: ["channels.slack"]
    install:
      - id: brew
        kind: brew
        formula: gh
        bins: [gh]
        label: "Install GitHub CLI (brew)"
```

#### `metadata.openclaw` Fields

| Field | Type | Description |
|-------|------|-------------|
| `emoji` | string | Display emoji for the skill in OpenClaw UI. |
| `requires.bins` | string[] | All of these binaries must be present for the skill to work. |
| `requires.anyBins` | string[] | At least one of these binaries must be present. |
| `requires.config` | string[] | OpenClaw config keys that must be set. e.g. `channels.slack`. |
| `install` | InstallStep[] | One or more installation methods for the skill's dependencies (see below). |

#### InstallStep Object

```yaml
install:
  - id: brew
    kind: brew
    formula: gh
    bins: [gh]
    label: "Install GitHub CLI (brew)"
  - id: apt
    kind: apt
    package: gh
    bins: [gh]
    label: "Install GitHub CLI (apt)"
  - id: go
    kind: go
    module: github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest
    bins: [blogwatcher]
    label: "Install blogwatcher (go)"
```

| Field | Description |
|-------|-------------|
| `id` | Unique identifier for this install method. e.g. `brew`, `apt`, `go`. |
| `kind` | Package manager: `brew`, `apt`, `go`, `npm`, `pip`, `cargo`, `script`. |
| `formula` | Homebrew formula name (when `kind: brew`). |
| `package` | apt/npm/pip package name (when `kind: apt`/`npm`/`pip`). |
| `module` | Go module path (when `kind: go`). |
| `bins` | Binary names installed by this step (for verification). |
| `label` | Human-readable label shown during install. |

---

## Frontmatter Examples

### Minimal (no dependencies)

```yaml
---
name: pregnancy-companion
description: 24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates, and supports a healthy pregnancy journey
os:
  - darwin
  - linux
---
```

### With emoji and binary requirement

```yaml
---
name: weather
description: "Get current weather and forecasts via wttr.in or Open-Meteo. Use when: user asks about weather, temperature, or forecasts for any location. NOT for: historical weather data, severe weather alerts."
homepage: https://wttr.in/:help
metadata: { "openclaw": { "emoji": "☔", "requires": { "bins": ["curl"] } } }
---
```

> Note: The `metadata` field can be expressed as inline JSON (single-line) or as multi-line YAML.

### With config requirement (Slack)

```yaml
---
name: slack
description: Use when you need to control Slack from OpenClaw via the slack tool.
metadata: { "openclaw": { "emoji": "💬", "requires": { "config": ["channels.slack"] } } }
---
```

### With binary alternatives and install steps

```yaml
---
name: coding-agent
description: 'Delegate coding tasks to Codex, Claude Code, or Pi agents. Use when: (1) building/creating features, (2) reviewing PRs, (3) refactoring. NOT for: simple one-liner fixes, reading code.'
metadata:
  {
    "openclaw": { "emoji": "🧩", "requires": { "anyBins": ["claude", "codex", "opencode", "pi"] } },
  }
---
```

### With install steps (multi-line YAML)

```yaml
---
name: github
description: "GitHub operations via `gh` CLI: issues, PRs, CI runs, code review. Use when: checking PR status, creating issues, listing PRs. NOT for: local git operations."
metadata:
  {
    "openclaw":
      {
        "emoji": "🐙",
        "requires": { "bins": ["gh"] },
        "install":
          [
            {
              "id": "brew",
              "kind": "brew",
              "formula": "gh",
              "bins": ["gh"],
              "label": "Install GitHub CLI (brew)",
            },
            {
              "id": "apt",
              "kind": "apt",
              "package": "gh",
              "bins": ["gh"],
              "label": "Install GitHub CLI (apt)",
            },
          ],
      },
  }
---
```

---

## Markdown Body Structure

The body is free-form Markdown. OpenClaw loads the full body as system prompt context after the skill triggers.

### Description Format Best Practices (observed)

Effective `description` fields follow this pattern:

```
<What it does>. Use when: <trigger conditions (1), (2), ...>. NOT for: <anti-triggers>.
```

This dual-signal format lets OpenClaw's routing layer both select the skill (trigger) and prevent false positives (anti-trigger).

### Typical Body Sections

```markdown
# Skill Name

## When to Use / When NOT to Use
Explicit positive/negative examples.

## Setup
One-time configuration steps.

## Commands / Actions
Core workflows with code examples.

## Examples / Templates
Copy-paste patterns for common tasks.

## Notes / Caveats
Rate limits, gotchas, edge cases.
```

There is no enforced schema for the body — the structure is guidance to the agent.

---

## Supporting Files

These files are convention-based, not required by the OpenClaw engine.

### `AGENTS.md`

Workspace and session rules. Loaded at agent startup. Covers:
- Memory system (daily notes in `memory/YYYY-MM-DD.md`, long-term `MEMORY.md`)
- Heartbeat behavior (when to speak in group chats, when to stay silent)
- Red lines (never exfiltrate data, ask before destructive commands)
- Tool usage conventions

### `SOUL.md`

Agent values, personality, and purpose. Defines who the agent is rather than what it does. Loaded alongside `AGENTS.md` at startup.

### `USER.md`

User profile. Name, timezone, preferences, communication style. Loaded at startup. Kept separate from `SOUL.md` so agent identity and user context are distinct.

### `IDENTITY.md`

Agent name, creature type, emoji, and vibe. Created during `BOOTSTRAP.md` first-run flow.

### `TOOLS.md`

Local device/environment notes that are specific to the user's setup:
- Camera names and locations
- SSH host aliases
- TTS voice preferences
- Device nicknames

Kept separate from `SKILL.md` because skills are shareable but this file is personal.

### `HEARTBEAT.md`

Periodic task checklist. When empty (or containing only comments), the agent replies `HEARTBEAT_OK` to heartbeat polls. When populated, the agent executes the listed tasks.

```markdown
# HEARTBEAT.md

## Tasks
- Check email for urgent messages
- Review today's calendar
- Log morning weight if available
```

### `BOOTSTRAP.md`

First-run initialization script. The agent reads this once, sets up `SOUL.md`, `IDENTITY.md`, and `USER.md`, then deletes `BOOTSTRAP.md`. It is not present in mature skill directories.

---

## Cron Triggers

OpenClaw cron jobs are **not** expressed inside `SKILL.md`. They live in `~/.openclaw/cron/jobs.json` and are managed via `openclaw cron` commands.

A cron job that invokes a skill looks like:

```json
{
  "id": "pregnancy-daily-tip",
  "agentId": "pregnancy-companion",
  "schedule": {
    "expr": "0 9 * * *"
  },
  "enabled": true,
  "name": "Daily Pregnancy Tip",
  "description": "Morning tip for the pregnancy companion",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "Give today's pregnancy tip based on the current week. Keep it brief and warm."
  },
  "sessionTarget": "isolated",
  "delivery": {
    "mode": "announce",
    "channel": "telegram",
    "accountId": "mybot",
    "to": "123456789"
  }
}
```

Key cron job fields:

| Field | Description |
|-------|-------------|
| `id` | Unique job identifier |
| `agentId` | The skill `name` this job targets |
| `schedule.expr` | 5-field cron expression (`min hour dom month dow`) |
| `schedule.every` | Interval shorthand alternative. e.g. `"30m"`, `"2h"` |
| `wakeMode` | `"now"` = run immediately when triggered |
| `payload.kind` | `"agentTurn"` = inject a message into a new agent session |
| `payload.message` | The message/prompt injected into the agent session |
| `sessionTarget` | `"isolated"` = fresh session, `"main"` = main session |
| `delivery.mode` | `"announce"` = send output to channel, `"silent"` = no output |
| `delivery.channel` | `"telegram"`, `"slack"`, `"discord"`, `"email"`, `"stdout"` |
| `delivery.to` | Destination identifier (chat_id, channel_id, email) |

### Skill-Side Cron Documentation Convention

Although cron jobs live outside `SKILL.md`, it's good practice to document expected cron behavior in the skill body:

```markdown
## Proactive Support

When triggered by cron jobs, provide:
- Daily tips relevant to the current pregnancy week
- Weekly pregnancy updates with baby development info
- Appointment reminders with suggested questions
```

---

## Knowledge Sources

Knowledge files are referenced by path in `SKILL.md` rather than declared in a schema. The agent reads them with the `bash` tool (or `Read` tool) when needed.

```markdown
## Knowledge Base

Refer to the files in `~/.openclaw/skills/pregnancy-companion/knowledge/`:
- `week-by-week.md` — Baby development and symptoms by week
- `nutrition.md` — Pregnancy nutrition guide by trimester
```

Standard directory layout:

```
skill-name/
└── knowledge/
    ├── week-by-week.md
    ├── nutrition.md
    └── warning-signs.md
```

---

## Data Files

Runtime data written by the agent lives in a `data/` subdirectory:

```
skill-name/
└── data/
    ├── symptoms-log.md
    ├── weight-log.md
    ├── appointments.md
    └── questions-for-doctor.md
```

These are referenced by absolute or `~`-relative paths in the system prompt:

```markdown
**Symptoms**: Append to `~/.openclaw/skills/pregnancy-companion/data/symptoms-log.md`
```

---

## Progressive Loading

OpenClaw loads skill content in three stages:

1. **`name` + `description` only** — always in context (~100 words). Used for routing/triggering.
2. **Full `SKILL.md` body** — loaded when the skill is selected.
3. **`knowledge/` and `references/` files** — loaded by the agent on demand using file-read tools.

Keep `SKILL.md` bodies under 500 lines to minimize context cost.

---

## Complete Minimal Example

```
skill-name/
└── SKILL.md
```

```yaml
---
name: wttr-weather
description: "Get current weather for any city using wttr.in. Use when: user asks about weather, temperature, or forecasts. NOT for: historical data or severe weather alerts."
homepage: https://wttr.in/:help
metadata: { "openclaw": { "emoji": "🌤️", "requires": { "bins": ["curl"] } } }
---

# Weather

Get current conditions and forecasts from wttr.in. No API key required.

## Current weather

```bash
curl "wttr.in/London?format=3"
```

## 3-day forecast

```bash
curl "wttr.in/London"
```

## Format codes

- `%t` temperature  `%w` wind  `%h` humidity  `%p` precipitation

## Notes

- Supports city names, ZIP codes, and airport codes
- Rate limited — don't spam requests
```

---

## Full Example — pregnancy-companion

See `~/.openclaw/skills/pregnancy-companion/SKILL.md` for the complete reference implementation.

Key observations from that file:
- No `metadata` block (no external binary dependencies)
- `os: [darwin, linux]` restricts platform
- Body uses `##` sections for clear agent instructions
- Safety rules are explicit, numbered, and marked `CRITICAL`
- Data file paths use `~/.openclaw/skills/<name>/data/` convention
- Knowledge files use `~/.openclaw/skills/<name>/knowledge/` convention
