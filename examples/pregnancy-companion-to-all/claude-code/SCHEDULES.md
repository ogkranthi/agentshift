# Scheduled Tasks — pregnancy-companion

This skill has scheduled triggers in OpenClaw. Below are the equivalent setups for Claude Code.

> **Note:** Delivery to Telegram/Slack/Discord is not natively supported in Claude Code. Use cloud scheduled tasks for durable scheduling, or see the workarounds below.

## pregnancy-morning-tip

**Schedule:** `0 8 * * *`
**OpenClaw delivery:** telegram → `8618552148`

**Prompt:**
```
It's morning! Send a warm, encouraging daily message to the mom-to-be. Include:
1. A pregnancy tip relevant to the current week of pregnancy (calculate from due date ~November 15, 2026)
2. A quick nutrition or hydration reminder appropriate for her current trimester
3. A short encouraging or fun fact about baby's development

Keep it concise and warm — this is a Telegram message, not an essay. 3-5 short lines max. Use the knowledge files in ~/.openclaw/skills/pregnancy-companion/knowledge/ for accurate info.

Start with a warm greeting like 'Good morning, mama!' and end with something uplifting.
```

**Set up in Claude Code:**

Option 1 — Cloud scheduled task (recommended, survives restarts):
```
# In any Claude Code session:
/schedule cron(0 8 * * *) It's morning! Send a warm, encouraging daily message to the mom-to-be. Include:
# Or visit: https://claude.ai/code/scheduled → New scheduled task
```

Option 2 — In-session loop (disappears when Claude Code exits):
```
/loop 1d It's morning! Send a warm, encouraging daily message to the mom-to-be. Include:
```

## pregnancy-weekly-update

**Schedule:** `0 9 * * 0`
**OpenClaw delivery:** telegram → `8618552148`

**Prompt:**
```
It's Sunday — time for the weekly pregnancy update! Calculate the current pregnancy week from due date ~November 15, 2026. Read ~/.openclaw/skills/pregnancy-companion/knowledge/week-by-week.md for this week's info.

Send a structured update:
1. 'You're now X weeks pregnant!' with the fruit/veggie size comparison
2. What's happening with baby this week (2-3 bullet points)
3. Common symptoms to expect this week
4. One thing to do or prepare this week
5. What's coming up at the next prenatal appointment (if applicable, check knowledge/appointments.md)

Also check ~/.openclaw/skills/pregnancy-companion/data/symptoms-log.md — if there are entries from this past week, add a brief 'This week you reported: ...' summary.

Keep it warm, celebratory, and informative. This is the highlight message of the week!
```

**Set up in Claude Code:**

Option 1 — Cloud scheduled task (recommended, survives restarts):
```
# In any Claude Code session:
/schedule cron(0 9 * * 0) It's Sunday — time for the weekly pregnancy update! Calculate the current pregna
# Or visit: https://claude.ai/code/scheduled → New scheduled task
```

Option 2 — In-session loop (disappears when Claude Code exits):
```
/loop 7d It's Sunday — time for the weekly pregnancy update! Calculate the current pregna
```

## pregnancy-evening-checkin

**Schedule:** `0 20 * * *`
**OpenClaw delivery:** telegram → `8618552148`

**Prompt:**
```
It's evening — time for a gentle check-in. Send a warm, short message asking how she's feeling today. Keep it casual and caring, not clinical.

Examples of tone:
- 'Hey! How was your day? Any new symptoms or feelings to share?'
- 'Evening check-in! How's the body treating you today?'
- 'How are you and the little one doing tonight?'

Vary the message each day — don't repeat the same wording. Mention that she can share symptoms, mood, or anything on her mind and you'll keep track.

2-3 lines max. Keep it light and supportive.
```

**Set up in Claude Code:**

Option 1 — Cloud scheduled task (recommended, survives restarts):
```
# In any Claude Code session:
/schedule cron(0 20 * * *) It's evening — time for a gentle check-in. Send a warm, short message asking how
# Or visit: https://claude.ai/code/scheduled → New scheduled task
```

Option 2 — In-session loop (disappears when Claude Code exits):
```
/loop 1d It's evening — time for a gentle check-in. Send a warm, short message asking how
```

## pregnancy-appointment-reminder

**Schedule:** `0 19 * * *`
**OpenClaw delivery:** telegram → `8618552148`

**Prompt:**
```
Check ~/.openclaw/skills/pregnancy-companion/data/appointments.md for any appointments scheduled for tomorrow. Also check ~/.openclaw/skills/pregnancy-companion/data/questions-for-doctor.md for any saved questions.

If there IS an appointment tomorrow:
- Send a reminder with the appointment details (time, type, location)
- List any saved questions from questions-for-doctor.md
- Suggest 1-2 additional questions relevant to the current pregnancy week
- Remind to bring insurance card, any test results, etc.

If there is NO appointment tomorrow:
- Do NOT send any message. Reply with just: 'No appointment tomorrow — no reminder needed.'
```

**Set up in Claude Code:**

Option 1 — Cloud scheduled task (recommended, survives restarts):
```
# In any Claude Code session:
/schedule cron(0 19 * * *) Check ~/.openclaw/skills/pregnancy-companion/data/appointments.md for any appoin
# Or visit: https://claude.ai/code/scheduled → New scheduled task
```

Option 2 — In-session loop (disappears when Claude Code exits):
```
/loop 1d Check ~/.openclaw/skills/pregnancy-companion/data/appointments.md for any appoin
```
