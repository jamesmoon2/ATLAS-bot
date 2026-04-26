# ATLAS Channel User Guide

ATLAS is organized around dedicated Discord channels. Each configured channel has its own
conversation session, model preference, channel role context, and scheduled notifications. Use
channel IDs in production so Discord renames do not change routing.

## Quick Map

| Channel      | Best For                                      | Conversation Style                              |
| ------------ | --------------------------------------------- | ----------------------------------------------- |
| `#atlas`     | General ATLAS work and catch-all questions    | Broad, flexible, cross-domain                   |
| `#health`    | Training, recovery, meds, symptoms, wearables | Concrete logging and health/training decisions  |
| `#projects`  | Project work, tasks, decisions, vault cleanup | Action-oriented project and second-brain review |
| `#briefings` | Daily/weekly reports and ambient summaries    | Read-mostly, concise reports                    |
| `#atlas-dev` | Bot development, CI, MCP, operations          | Technical operations and implementation work    |

ATLAS auto-responds to normal messages in these configured channels. In any other channel, mention
ATLAS directly when you want a response.

## How Channel Routing Works

- Channel lookup is ID-first, name-second. Set `ATLAS_CHANNEL_ID_*` values in `.env` for rename-safe
  production routing.
- Conversation sessions live under `sessions/{channel_id}/`, so each Discord channel keeps its own
  continuity, attachments, and model preference.
- Each configured session gets an `ATLAS-Channel-Role.md` file that tells the active agent what the
  channel is for and which skills to prefer.
- Skills are not hard-restricted by channel. The channel role gives soft preferences, and `#atlas`
  remains the catch-all when a request spans domains.
- Cron notifications use channel-specific webhook variables. If a target webhook is missing, the
  dispatcher falls back to `DISCORD_WEBHOOK_ATLAS`, then `DISCORD_WEBHOOK_URL`.
- Use `ATLAS_CONFIGURED_CHANNELS=atlas,health,briefings` as a temporary allowlist if you want only
  selected configured channels to auto-activate.

## `#atlas`

Use `#atlas` when the work does not clearly belong elsewhere, crosses multiple areas, or needs a
general assistant thread.

**Good uses**

- Ask broad questions about tasks, notes, plans, and decisions.
- Start cross-domain threads that touch health, projects, calendar, and the vault.
- Use second-brain commands such as `!recall`, `!recent-notes`, `!open-loops`, `!orphan-notes`, and
  `!librarian`.
- Ask for backend concepts lessons or general technical explanations.

**Preferred skills**

| Skill                     | Use It For                                        |
| ------------------------- | ------------------------------------------------- |
| `second-brain-librarian`  | Vault recall, open-loop review, note cleanup      |
| `backend-concepts-lesson` | Short backend architecture lessons from the queue |

**Cron jobs**

No job targets `#atlas` directly by default. It is the fallback webhook target when a
channel-specific webhook is missing.

**Tips**

- Use `#atlas` for "I do not know where this belongs yet."
- Move recurring health, project, and reporting workflows into their dedicated channels once the
  category is clear.

## `#health`

Use `#health` for training, medication, recovery, symptoms, wearable data, and body-state decisions.
This is the most structured channel: the best messages include dates, doses, workout names,
symptoms, or what changed.

**Good uses**

- "Log today's lift."
- "I took TRT and HCG."
- "Plan next week's training around my calendar."
- "Why does recovery look bad today?"
- "I skipped the workout; update Training-State."
- Upload screenshots from Peloton, Garmin, or health apps when useful.

**Preferred skills**

| Skill                     | Use It For                                                      |
| ------------------------- | --------------------------------------------------------------- |
| `morning-briefing`        | Weather, schedule, training, medication, and recovery snapshot  |
| `health-pattern-monitor`  | Silent-unless-noteworthy recovery and wearable trend alerts     |
| `weekly-training-planner` | Recovery-aware weekly training plan and workout calendar events |
| `log-workout`             | Strength workout logs using Garmin and Training-State           |
| `log-cardio`              | Cardio, Peloton, ruck, run, and hike logs                       |
| `log-medication`          | Medication dose logging into the vault                          |

**Cron jobs**

| Job                       | Schedule       | What Lands Here                                    |
| ------------------------- | -------------- | -------------------------------------------------- |
| `weekly_training_planner` | Sun 12:00 PM   | Upcoming training week and calendar workout events |
| `med_reminder`            | 5:00 AM, 8 PM  | Medication reminders, unless no dose is due        |
| `med_config_sync`         | Daily 1:00 AM  | Only posts when `meds.json` drifts from the vault  |
| `health_pattern_monitor`  | Daily 10:30 AM | Only posts when Oura/WHOOP trends need attention   |

**Tips**

- For logging, say what happened in plain language. ATLAS will structure the note.
- Add "with notes: ..." when logging symptoms, pain, or recovery context.
- React to medication reminders with a checkmark to log the dose through the bot.
- Use `#briefings` to read the morning summary; use `#health` to ask follow-up questions or make
  changes.

## `#projects`

Use `#projects` for project state, tasks, decisions, stale threads, and second-brain maintenance.
This channel is for turning context into next actions.

**Good uses**

- "What projects need attention?"
- "Summarize open loops from the vault."
- "Capture this as a decision."
- "Find notes that should be linked or cleaned up."
- "What did we say we would do on the provider switch?"

**Preferred skills**

| Skill                    | Use It For                                          |
| ------------------------ | --------------------------------------------------- |
| `second-brain-librarian` | Recent notes, open loops, orphan notes, stale notes |

**Cron jobs**

| Job                      | Schedule        | What Lands Here                                     |
| ------------------------ | --------------- | --------------------------------------------------- |
| `stale_project_detector` | Sat 8:00 AM     | Projects untouched for 30+ days                     |
| `context_drift`          | Sun 8:00 AM     | Misalignment between decisions and recent execution |
| `librarian_digest`       | Mon/Fri 7:45 AM | Recent notes, open loops, stale notes, link ideas   |

**Tips**

- Ask for specific outputs: "give me the next three actions" works better than "review everything."
- Use `!recall <query>` when you need a fast vault search.
- Use `!librarian` when you want a compact digest on demand instead of waiting for the scheduled job.

## `#briefings`

Use `#briefings` as the read-mostly report channel. It should stay quiet, scannable, and useful at a
glance. The bot can answer here, but long back-and-forth work usually belongs in `#atlas`,
`#health`, or `#projects`.

**Good uses**

- Read the morning briefing.
- Read the end-of-day summary.
- Read the weekly review.
- Ask a short clarification about a report.

**Preferred skills**

| Skill              | Use It For                                               |
| ------------------ | -------------------------------------------------------- |
| `morning-briefing` | Daily weather, calendar, training, meds, and recovery    |
| `daily-summary`    | End-of-day activity and context summary                  |
| `weekly-review`    | Weekly training, health, medication, and progress review |

**Cron jobs**

| Job                | Schedule       | What Lands Here                                            |
| ------------------ | -------------- | ---------------------------------------------------------- |
| `morning_briefing` | Daily 5:30 AM  | Weather, calendar, training, meds, recovery                |
| `daily_summary`    | Daily 11:55 PM | Daily context, file, task, decision, and health recap      |
| `weekly_review`    | Sun 8:00 PM    | Seven-day health, training, adherence, and progress review |

**Tips**

- Treat this as the "read the state of the system" channel.
- If a briefing reveals work to do, continue the execution in the relevant channel.
- Keep ad hoc requests concise here so scheduled reports remain easy to scan.

## `#atlas-dev`

Use `#atlas-dev` for ATLAS itself: repository changes, CI, bot restarts, MCP auth, provider
switching, cron behavior, and operational alerts.

**Good uses**

- "Fix the failing CI run."
- "Restart the bot."
- "Check MCP health."
- "Why did the cron job not post?"
- "Add a new channel/skill/job."

**Preferred skills**

| Skill                     | Use It For                                      |
| ------------------------- | ----------------------------------------------- |
| `backend-concepts-lesson` | Technical learning queue and architecture notes |

**Cron jobs**

| Job                | Schedule       | What Lands Here                                           |
| ------------------ | -------------- | --------------------------------------------------------- |
| `mcp_health_check` | Mon 6:00 AM    | OAuth/tool availability for Calendar, Gmail, Oura, Garmin |
| `session_archive`  | Daily 12:05 AM | Nightly session archive/reset result                      |

**Tips**

- Keep deployment and operational requests here so they do not mix with personal planning threads.
- Use this channel for provider changes because it leaves an obvious audit trail.
- If a cron notification is missing, check whether the target `DISCORD_WEBHOOK_*` variable is set.

## Silent Support Jobs

These jobs are scheduled but do not post to a Discord channel during normal operation. Their output is
logged under `logs/cron/`.

| Job                   | Schedule       | Purpose                                          |
| --------------------- | -------------- | ------------------------------------------------ |
| `vault_index_refresh` | Daily 2:15 AM  | Rebuild `vault-index.json` and `vault-index.md`  |
| `oura_context_update` | Daily 10:00 AM | Backfill Oura + WHOOP recovery into workout logs |

## Commands That Work In Any Responding Channel

| Command             | Best Channel            | Description                                |
| ------------------- | ----------------------- | ------------------------------------------ |
| `!help`             | Any                     | Show available commands                    |
| `!model`            | Any                     | Show the current model for this channel    |
| `!model <model>`    | Any                     | Switch model for this channel              |
| `!recall <query>`   | `#atlas`, `#projects`   | Search the vault like a librarian          |
| `!recent-notes`     | `#atlas`, `#projects`   | Summarize recently updated notes           |
| `!open-loops`       | `#atlas`, `#projects`   | Review unresolved tasks and waiting states |
| `!orphan-notes`     | `#atlas`, `#projects`   | Find notes needing links or cleanup        |
| `!librarian`        | `#atlas`, `#projects`   | Generate a compact vault digest            |
| `!reset` / `!clear` | Current working channel | Reset that channel's session               |

## Best Practices

- Put the request where you want the memory to live. A training thread in `#health` keeps health
  context cleaner than scattering it through `#atlas`.
- Use `#briefings` for consumption and the topical channels for action.
- Include concrete dates when changing logs or plans.
- Upload source artifacts in the same channel where you want ATLAS to use them.
- Use `!reset` when a channel thread has become stale or confused; it resets only that channel.
- Prefer channel ID pins over channel names in production.
- Keep `DISCORD_WEBHOOK_URL` only as a fallback. Channel-specific webhooks make scheduled messages
  land where they are most useful.
