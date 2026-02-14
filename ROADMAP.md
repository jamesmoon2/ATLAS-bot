# ATLAS Product Roadmap

## Context

ATLAS is a personal AI assistant Discord bot wrapping Claude Code CLI, integrated with an Obsidian vault (second brain), Oura Ring, Google Calendar, Gmail, and weather APIs. It currently has 12 cron jobs, 6 skills, a custom Oura MCP server, and a hook-based context injection system.

The user wants to evolve ATLAS from a reactive chat assistant into a proactive, ambient personal operating system. Key goals: better cross-session memory, proactive intelligence (alerts and nudges), new integrations (Garmin, finance, web research), multi-channel Discord organization, and mobile/ambient operation. All AI processing must go through Claude Code CLI (no raw API calls).

---

## Phase 1: Multi-Channel Architecture + Context Improvements

**Goal**: Organize Discord into topic channels and improve cross-session memory.

### 1.1 Multi-Channel Discord Setup

Create dedicated channels with per-channel behavior:

| Channel | Purpose | Webhook Routing |
|---------|---------|-----------------|
| `#atlas` | General conversation (existing) | Default |
| `#health` | Workouts, meds, Oura, training | Morning briefing, med reminders, health alerts |
| `#projects` | Project work, tasks, decisions | Stale project alerts, task nudges |
| `#briefings` | Read-only briefings and reports | Daily summary, weekly/monthly reviews |

**Implementation**:
- **Modify `bot.py`**: Replace hardcoded `CHANNEL_SETTINGS` with a `CHANNEL_CONFIGS` dict keyed by channel name. Each config defines: hooks, permissions, model, and a role description injected into the system prompt. Change `on_message` activation check from single channel name to set of configured channels.
- **Create `channel_configs.py`**: Extract per-channel configuration (hooks, permissions, role descriptions) into its own module.
- **Create `hooks/health_context.sh`**: Health-specific SessionStart hook — injects Training-State.md summary, recent workout logs, Medications.md, current Oura scores.
- **Modify `cron/jobs.json`**: Route each job's webhook to the appropriate channel via `notify.url_env` (already supported by dispatcher).
- **Add to `.env`**: `DISCORD_WEBHOOK_HEALTH`, `DISCORD_WEBHOOK_BRIEFINGS`, `DISCORD_WEBHOOK_PROJECTS`.

### 1.2 Wire Recent Summaries into SessionStart

`hooks/recent_summaries.sh` exists but is not referenced in `CHANNEL_SETTINGS`. Add it to SessionStart hooks so ATLAS gets the last 3 daily summaries as context every session.

- **Modify `bot.py`**: Add `recent_summaries.sh` to SessionStart hooks array.

---

## Phase 2: Proactive Intelligence

**Goal**: Make ATLAS surface insights, alerts, and nudges without being asked. Build the "silent unless noteworthy" pattern into the dispatcher.

### 2.1 Dispatcher: `suppress_if_contains` Feature

Add a first-class feature to `cron/dispatcher.py`: if a job's `notify` config includes `suppress_if_contains: "NO_ALERT"`, skip the webhook send when the output contains that string. This makes "run analysis, only notify if something is worth flagging" reusable across all proactive jobs.

- **Modify `cron/dispatcher.py`**: In `send_webhook()`, check for suppression string before sending.

### 2.2 Health Pattern Monitor

Daily cron job (10:30 AM, after Oura sync) that checks 7-14 day health trends. Alerts only when noteworthy:
- HRV declining 3+ days
- Sleep score < 70 for 3+ days
- Readiness < 65 for 2+ days
- Sleep timing inconsistency > 1hr from baseline

**New files**:
- `cron/jobs.json`: Add `health_pattern_monitor` job (sonnet model, routes to `#health`)
- `.claude/skills/health-pattern-monitor.md`: Skill with alert thresholds and output format

### 2.3 Decision Follow-Up Tracker

Weekly cron job (Wednesday 7 PM) that reads Decision-Log.md, finds decisions older than 7 days with no outcome recorded, and posts follow-up prompts.

- **Modify `cron/jobs.json`**: Add `decision_followup` job (sonnet, routes to `#projects`)

### 2.4 Opportunity Surfacer

Runs Sunday + Wednesday 8 PM. Checks next 3 days of calendar for free blocks > 90 min, cross-references against task list and stale projects, suggests specific uses for free time.

- **Modify `cron/jobs.json`**: Add `opportunity_surfacer` job (sonnet, routes to `#briefings`)

### 2.5 Enhanced Project Accountability

Upgrade existing `stale_project_detector` to also scan for uncompleted tasks older than 14 days within project directories. Route output to `#projects` channel.

- **Modify `cron/jobs.json`**: Update prompt and webhook routing for `stale_project_detector`

---

## Phase 3: Integration Expansion

**Goal**: Add Garmin, web research, and financial tracking.

### 3.1 Garmin Connect MCP Server (Use Existing)

Use the community [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp) server — 95+ tools, 100% test pass rate, Python-based, installable via `uvx`. No need to build custom.

**Setup**:
1. One-time auth: `uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth` (handles MFA)
2. Add to Claude Code MCP config (`.claude/settings.local.json` or project-level):
   ```json
   "garmin": {
     "command": "uvx",
     "args": ["--python", "3.12", "--from", "git+https://github.com/Taxuspt/garmin_mcp", "garmin-mcp"]
   }
   ```
3. Token stored at `~/.garminconnect`, refreshes automatically. Re-auth every ~6 months.

**Key tools available**: `get_activities`, `get_body_composition`, `get_training_status`, `get_heart_rate`, `get_steps`, `get_sleep`, `get_stress`, plus 85+ more covering devices, gear, challenges, workouts.

**After integration works**:
- Update `.claude/skills/log-workout.md` to auto-fetch latest Garmin activity instead of requiring manual data entry
- Create `hooks/garmin_workout_data.sh` (PostToolUse hook after workout log writes)

### 3.2 Web Research Tools

MCP server at `mcp-servers/web-research/` for:
- `search_web(query)` — Web search via SerpAPI or Brave Search
- `fetch_article(url)` — Extract article content
- `clip_to_vault(url, title, tags)` — Save structured article to `vault/Resources/Articles/`

**New skill**: `.claude/skills/clip-article.md`

### 3.3 Financial Tracking (Vault-Based Start)

Start manual, automate later:
- Create vault structure: `Areas/Finance/Budget.md`, `Transactions/YYYY-MM.md`
- **New skill**: `.claude/skills/log-expense.md` — Parse "spent $45 at Costco groceries" into structured entries
- **New cron job**: `monthly_finance_review` — End-of-month spending vs budget analysis

---

## Phase 4: Synthesis + Polish

**Goal**: Long-arc pattern detection, mobile push, latency optimization.

### 4.1 Weekly Review

Sunday 8 PM cron job (opus) that reads all daily summaries, workout logs, task changes, Oura trends from the past 7 days. Produces structured weekly review.

**Output**: `vault/Daily/YYYY-WXX-weekly-review.md`
**Sections**: Week summary, health & training trends, project progress, task scorecard, patterns detected, next week focus.

- **Create**: `.claude/skills/weekly-review.md`
- **Modify**: `cron/jobs.json` (add `weekly_review`)

### 4.2 Monthly Synthesis

1st of month, 8 PM. Reads all weekly reviews, generates 30-day trend report.

**Output**: `vault/Daily/YYYY-MM-monthly-review.md`
**Sections**: Health trajectory, project scorecard, decision audit, task velocity trends, cross-domain patterns.

- **Create**: `.claude/skills/monthly-synthesis.md`
- **Modify**: `cron/jobs.json` (add `monthly_synthesis`)

### 4.3 Mobile Push Notifications (Priority Levels)

Discord mobile already delivers notifications. The problem is noise — morning briefings buzz the same as health alerts.

**Solution**: Add `priority` field to job `notify` config. When `priority: "high"`, prepend `<@USER_ID>` to webhook messages (triggers mobile push notification). Routine briefings remain standard webhook messages (no push).

- **Modify `cron/dispatcher.py`**: Priority-based user mentions
- **Add to `.env`**: `DISCORD_USER_ID`

### 4.4 Smart Model Routing

Auto-detect query complexity to reduce latency for simple interactions:
- Short commands, quick lookups, logging → Sonnet (faster)
- Complex analysis, planning, multi-step tasks → Opus

**Modify `bot.py`**: Add `classify_query_complexity()` function. If no explicit model override, auto-route based on query patterns.

### 4.5 Vault Knowledge Index

Weekly cron job that scans the vault and maintains `vault/System/vault-index.md` — a condensed listing of every file with one-line description, last modified date, and tags. A truncated version (50 most recent files) is injected via SessionStart hook.

- **Create**: `cron/vault_index.sh`, `hooks/vault_index.sh`
- **Modify**: `cron/jobs.json` (add `vault_index_update`)

---

## Implementation Order (Recommended)

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| 1 | Wire recent_summaries into SessionStart (1.2) | 15 min | High — immediate context improvement |
| 2 | Dispatcher suppress_if_contains (2.1) | 30 min | Enables all proactive jobs |
| 3 | Health pattern monitor (2.2) | 2-3 hrs | High — #1 proactivity request |
| 4 | Garmin MCP server (3.1) | 1-2 hrs | High — just install + configure existing server |
| 5 | Multi-channel setup (1.1) | 4-6 hrs | Medium — organizes everything |
| 6 | Weekly review (4.1) | 2-3 hrs | High — pattern detection foundation |
| 7 | Decision follow-up (2.3) | 1-2 hrs | Medium — accountability |
| 8 | Opportunity surfacer (2.4) | 1-2 hrs | Medium — calendar intelligence |
| 9 | Mobile push priorities (4.3) | 1 hr | Medium — notification UX |
| 10 | Smart model routing (4.4) | 1-2 hrs | Medium — latency reduction |
| 11 | Web research MCP (3.2) | 1-2 days | Medium — reference library |
| 12 | Financial tracking (3.3) | 3-4 hrs | Lower — start with vault-based |
| 13 | Monthly synthesis (4.2) | 2-3 hrs | Medium — needs weekly reviews first |
| 14 | Vault index (4.5) | 2-3 hrs | Medium — retrieval improvement |

---

## Verification

After each feature:
1. **Cron jobs**: Run with `python cron/dispatcher.py --run-now JOB_ID` and verify output
2. **Multi-channel**: Send test messages in each channel, verify correct hooks fire
3. **MCP servers**: Test tools individually via Claude Code CLI before integrating
4. **Skills**: Run skills manually via Claude Code before adding to cron
5. **Webhooks**: Verify messages route to correct Discord channels
6. **Mobile push**: Test with `priority: "high"` job and confirm phone notification

---

## Key Files (Most Modified)

- `bot.py` — Multi-channel routing, hook wiring, model routing
- `cron/dispatcher.py` — suppress_if_contains, priority mentions
- `cron/jobs.json` — All new cron job definitions
- `.env.example` — New webhook URLs, user ID
- `channel_configs.py` (new) — Per-channel configuration
