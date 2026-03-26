# pregnancy-companion — GCP Vertex AI Agent

24/7 pregnancy companion — answers questions, tracks symptoms, gives weekly updates, and supports a healthy pregnancy journey

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
  --agent-id=pregnancy-companion \
  --source=agent.json \
  --location=us-central1
```

### Test the agent

```bash
gcloud alpha agent-builder agents run \
  --agent-id=pregnancy-companion \
  --location=us-central1 \
  --query="Hello!"
```

## Knowledge (Stubs)

Knowledge sources require a Vertex AI Search data store or Agent Builder data store:

- **appointments** (file) — Knowledge file: appointments.md
- **exercise** (file) — Knowledge file: exercise.md
- **nutrition** (file) — Knowledge file: nutrition.md
- **warning-signs** (file) — Knowledge file: warning-signs.md
- **week-by-week** (file) — Knowledge file: week-by-week.md

See the [Vertex AI data stores guide](https://cloud.google.com/generative-ai-app-builder/docs/create-datastore-ingest) for setup instructions.

## Scheduled Triggers (Cloud Scheduler stubs)

Use Cloud Scheduler to invoke this agent on a schedule:

### pregnancy-morning-tip

```bash
gcloud scheduler jobs create http \
  --schedule='0 8 * * *' \
  --uri=YOUR_AGENT_ENDPOINT \
  --message-body='It's morning! Send a warm, encouraging daily message to the mom-to-be. Include:
1. A pregnancy tip relevant to the current week of pregnancy (calculate from due date ~November 15, 2026)
2. A quick nutrition or hydration reminder appropriate for her current trimester
3. A short encouraging or fun fact about baby's development

Keep it concise and warm — this is a Telegram message, not an essay. 3-5 short lines max. Use the knowledge files in ~/.openclaw/skills/pregnancy-companion/knowledge/ for accurate info.

Start with a warm greeting like 'Good morning, mama!' and end with something uplifting.' \
  --location=us-central1
```

### pregnancy-weekly-update

```bash
gcloud scheduler jobs create http \
  --schedule='0 9 * * 0' \
  --uri=YOUR_AGENT_ENDPOINT \
  --message-body='It's Sunday — time for the weekly pregnancy update! Calculate the current pregnancy week from due date ~November 15, 2026. Read ~/.openclaw/skills/pregnancy-companion/knowledge/week-by-week.md for this week's info.

Send a structured update:
1. 'You're now X weeks pregnant!' with the fruit/veggie size comparison
2. What's happening with baby this week (2-3 bullet points)
3. Common symptoms to expect this week
4. One thing to do or prepare this week
5. What's coming up at the next prenatal appointment (if applicable, check knowledge/appointments.md)

Also check ~/.openclaw/skills/pregnancy-companion/data/symptoms-log.md — if there are entries from this past week, add a brief 'This week you reported: ...' summary.

Keep it warm, celebratory, and informative. This is the highlight message of the week!' \
  --location=us-central1
```

### pregnancy-evening-checkin

```bash
gcloud scheduler jobs create http \
  --schedule='0 20 * * *' \
  --uri=YOUR_AGENT_ENDPOINT \
  --message-body='It's evening — time for a gentle check-in. Send a warm, short message asking how she's feeling today. Keep it casual and caring, not clinical.

Examples of tone:
- 'Hey! How was your day? Any new symptoms or feelings to share?'
- 'Evening check-in! How's the body treating you today?'
- 'How are you and the little one doing tonight?'

Vary the message each day — don't repeat the same wording. Mention that she can share symptoms, mood, or anything on her mind and you'll keep track.

2-3 lines max. Keep it light and supportive.' \
  --location=us-central1
```

### pregnancy-appointment-reminder

```bash
gcloud scheduler jobs create http \
  --schedule='0 19 * * *' \
  --uri=YOUR_AGENT_ENDPOINT \
  --message-body='Check ~/.openclaw/skills/pregnancy-companion/data/appointments.md for any appointments scheduled for tomorrow. Also check ~/.openclaw/skills/pregnancy-companion/data/questions-for-doctor.md for any saved questions.

If there IS an appointment tomorrow:
- Send a reminder with the appointment details (time, type, location)
- List any saved questions from questions-for-doctor.md
- Suggest 1-2 additional questions relevant to the current pregnancy week
- Remind to bring insurance card, any test results, etc.

If there is NO appointment tomorrow:
- Do NOT send any message. Reply with just: 'No appointment tomorrow — no reminder needed.'' \
  --location=us-central1
```

## About

This agent was automatically converted using AgentShift.

- **Source format:** OpenClaw SKILL.md
- **Target format:** GCP Vertex AI Agent Builder
- **Converter:** [AgentShift](https://agentshift.sh)

To convert other OpenClaw skills:
```bash
agentshift convert ~/.openclaw/skills/<skill-name> --from openclaw --to vertex --output /tmp/vertex-output
```