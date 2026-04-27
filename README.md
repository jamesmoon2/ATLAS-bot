# ATLAS Bot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![CI](https://github.com/jamesmoon2/ATLAS-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/jamesmoon2/ATLAS-bot/actions/workflows/ci.yml)

A Discord bot that wraps a configurable agent harness for conversational AI assistance. ATLAS can run on [Claude Code CLI](https://github.com/anthropics/claude-code) or OpenAI Codex while keeping the same prompts, skills, hooks, scheduled automation, and Discord interaction model.

## Architecture

```mermaid
flowchart TB
    subgraph Discord
        User[User]
        Channel[Discord Channel]
        Webhook[Discord Webhook]
    end

    subgraph ATLAS[ATLAS Bot]
        Bot[bot.py]
        Sessions[sessions/]
        SendMsg[send_message.py]
    end

    subgraph Cron[Cron Dispatcher]
        RunCron[run_cron.sh]
        Dispatcher[cron/dispatcher.py]
        Jobs[cron/jobs.json]
        Scripts[Shell Scripts]
    end

    subgraph CLI[Agent Harness]
        Agent[claude CLI or codex]
        Hooks[Session Hooks]
        Skills[.claude/skills/]
    end

    subgraph MCP[MCP Servers]
        Oura[Oura Ring]
        Whoop[WHOOP]
        Garmin[Garmin Connect]
        Calendar[Google Calendar]
        Gmail[Gmail]
        Weather[Weather]
    end

    subgraph FS[Local Filesystem]
        Vault[Vault/Notes]
        Files[Project Files]
    end

    User --> Channel
    Channel --> Bot
    Bot --> Agent
    Bot --> Sessions
    Agent --> Vault
    Agent --> Files
    Agent --> MCP
    Hooks --> Agent
    Skills --> Agent
    Agent --> Bot
    Bot --> Channel
    RunCron --> Dispatcher
    Dispatcher --> Jobs
    Dispatcher --> Agent
    Dispatcher --> Scripts
    Dispatcher --> Webhook
    SendMsg --> Channel
```

## Message Flow

```mermaid
sequenceDiagram
    participant U as User
    participant D as Discord
    participant B as ATLAS Bot
    participant C as Active Agent CLI
    participant F as Filesystem

    U->>D: Send message in channel
    D->>B: on_message event
    B->>B: Check channel/mention
    B->>B: Load or create session
    B->>B: Download attachments (if any)
    B->>C: active agent CLI with session continuity

    Note over C: Session hooks run on first message
    C->>F: Read system prompt + context
    C->>F: Read/write files as needed
    C->>B: Response via stdout
    B->>D: Send response
    D->>U: Display message
```

## Session Lifecycle

```mermaid
stateDiagram-v2
    [*] --> NewSession: First message in channel

    NewSession --> HooksRun: Create session dir
    HooksRun --> Active: Load system prompt and context

    Active --> Active: Process messages
    Active --> Reset: User sends reset command
    Active --> Timeout: 10 min timeout
    Active --> Archived: Nightly session archive

    Reset --> [*]: Clear session + harness storage
    Timeout --> Active: Next message resumes
    Archived --> [*]: Session saved to .archive/
```

## Features

| Feature                     | Description                                                                                    |
| --------------------------- | ---------------------------------------------------------------------------------------------- |
| **Session Continuity**      | Maintains conversation context across messages                                                 |
| **Channel Isolation**       | Each Discord channel gets its own agent session and model preference                           |
| **Configurable Hooks**      | Three hook types: `SessionStart`, `PreToolUse`, `PostToolUse`                                  |
| **Provider Switching**      | Switch the harness globally with `ATLAS_AGENT_PROVIDER=claude` or `ATLAS_AGENT_PROVIDER=codex` |
| **Model Switching**         | Switch models per channel based on the active provider                                         |
| **Attachment Support**      | Upload images and PDFs to Discord; the active harness reads them from the session directory    |
| **Scheduled Automation**    | 15 cron jobs: briefings, reminders, archival, health checks, ops watchdogs, and more           |
| **MCP Integrations**        | Oura Ring, WHOOP, Garmin, Google Calendar, Gmail, and Weather data via MCP servers             |
| **ATLAS Skills**            | Reusable skills for briefings, workout logging, training plans, health monitoring, and reviews |
| **Second Brain Librarian**  | Vault indexing, note recall, open-loop review, orphan-note detection, and twice-weekly digests |
| **Medication Tracking**     | Config-driven cron reminders (`meds.json`) with checkmark reaction logging to vault files      |
| **Nightly Session Archive** | Sessions archived and reset daily to keep context fresh                                        |
| **Tool Access**             | Pre-approved tools: Read, Write, Edit, Glob, Grep, Bash (safe subset)                          |
| **Timeout Protection**      | 10-minute timeout for long-running requests                                                    |

## Requirements

- Python 3.10+
- One configured harness:
  - [Claude Code CLI](https://github.com/anthropics/claude-code), or
  - OpenAI Codex CLI
- Discord Bot Token

## Quick Start

```bash
# Clone
git clone https://github.com/jamesmoon2/ATLAS-bot.git
cd atlas-bot

# Setup
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your values

# Run
python bot.py
```

## Configuration

### Environment Variables

| Variable                                | Description                                                      | Required |
| --------------------------------------- | ---------------------------------------------------------------- | -------- |
| `DISCORD_TOKEN`                         | Discord bot token                                                | Yes      |
| `VAULT_PATH`                            | Path to your notes/vault directory                               | Yes      |
| `SESSIONS_DIR`                          | Where to store session data                                      | No       |
| `BOT_DIR`                               | Bot installation directory                                       | No       |
| `SYSTEM_PROMPT_PATH`                    | Path to system prompt file                                       | No       |
| `CONTEXT_PATH`                          | Path to persistent context file (ATLAS-Context.md)               | No       |
| `TASKS_FILE_PATH`                       | Path to tasks file for hook injection                            | No       |
| `ATLAS_AGENT_PROVIDER`                  | Active harness: `claude` or `codex`                              | No       |
| `ATLAS_CLAUDE_MODEL`                    | Default Claude model for new channels                            | No       |
| `ATLAS_CODEX_MODEL`                     | Default Codex model for new channels                             | No       |
| `ATLAS_CODEX_REASONING_EFFORT`          | Codex reasoning effort (`low`..`xhigh`)                          | No       |
| `ATLAS_CODEX_HOME`                      | Optional bot-specific Codex profile/home                         | No       |
| `ATLAS_CODEX_CRON_TIMEOUT_MULTIPLIER`   | Multiplier for agent cron job timeouts under Codex (default `3`) | No       |
| `ATLAS_OPS_WATCHDOG_ORPHAN_MIN_SECONDS` | Minimum helper age before orphan MCP alerting (default `3600`)   | No       |
| `ATLAS_OPS_WATCHDOG_REPEAT_SECONDS`     | Repeat window for identical watchdog alerts (default `21600`)    | No       |
| `ATLAS_CHANNEL_ID_*`                    | Optional channel ID pins for configured channels                 | No       |
| `ATLAS_CONFIGURED_CHANNELS`             | Optional comma-separated auto-activation allowlist               | No       |
| `DISCORD_WEBHOOK_*`                     | Channel-specific webhook URLs for cron notifications             | No       |
| `DISCORD_CHANNEL_ID`                    | Legacy channel ID fallback for `send_message.py`                 | No       |
| `DISCORD_WEBHOOK_URL`                   | Legacy webhook fallback for cron job notifications               | No       |

### Configured Discord Channels

ATLAS auto-activates in the channels declared in `channel_configs.py`:

| Channel      | Role                                                         | Preferred Use                           |
| ------------ | ------------------------------------------------------------ | --------------------------------------- |
| `#atlas`     | General conversation and catch-all assistant work            | Cross-domain work and ad hoc questions  |
| `#health`    | Health, medications, recovery, Oura, WHOOP, Garmin, training | Logging, training plans, health changes |
| `#projects`  | Project work, tasks, decisions, stale scans, vault follow-up | Next actions and second-brain cleanup   |
| `#briefings` | Read-mostly daily/weekly summaries and ambient reports       | Scheduled reports and quick follow-ups  |
| `#atlas-dev` | ATLAS harness work, operational alerts, bot development      | CI, MCP auth, provider and bot ops      |

For production, set the matching `ATLAS_CHANNEL_ID_*` variables so Discord channel renames do not break routing. Channel names remain a bootstrap fallback for development and tests.

To temporarily disable auto-activation in one or more configured channels without a deploy, set:

```bash
ATLAS_CONFIGURED_CHANNELS=atlas,health,briefings
```

Cron notifications route to channel-specific webhooks. If a channel webhook is unset, the dispatcher falls back through:

```text
configured webhook -> DISCORD_WEBHOOK_ATLAS -> DISCORD_WEBHOOK_URL
```

See the [ATLAS Channel User Guide](docs/guides/channel-user-guide.md) for which skills and cron jobs
belong to each channel and how to use the channels day to day.

### Provider Switching

ATLAS can run on either Claude or Codex. The active provider is controlled by `ATLAS_AGENT_PROVIDER` in `.env`.

Common commands:

```bash
# Restart both services from the repo
./restart_atlas_services.sh

# Switch provider and restart immediately
./set_atlas_provider.sh codex
./set_atlas_provider.sh claude

# Change provider without restarting yet
./set_atlas_provider.sh codex --no-restart
```

Operational notes:

- Default behavior remains Claude. Leave `ATLAS_AGENT_PROVIDER=claude` for the original setup.
- `./set_atlas_provider.sh codex` switches to Codex, updates `.env`, and restarts `atlas-bot.service` and `cron.service`.
- `./set_atlas_provider.sh claude` does the inverse for a fast rollback.
- If you want Codex isolated from your personal CLI state, set `ATLAS_CODEX_HOME` to a bot-specific directory.
- A short operator guide lives in
  [docs/guides/provider-switch-user-guide.md](docs/guides/provider-switch-user-guide.md).

### Service Supervision

The canonical bot supervisor is the system-level `atlas-bot.service`. Do not run a second
`systemctl --user` `atlas-bot.service`; duplicate supervisors create two live Discord bot
connections.

Expected state:

```bash
systemctl is-enabled atlas-bot.service        # enabled
systemctl --user is-enabled atlas-bot.service # masked
pgrep -af 'bot\.py'                           # one bot.py process
```

If a user-level unit exists, retire it:

```bash
systemctl --user stop atlas-bot.service
systemctl --user disable atlas-bot.service
mv ~/.config/systemd/user/atlas-bot.service ~/.config/systemd/user/atlas-bot.service.retired
systemctl --user daemon-reload
systemctl --user mask atlas-bot.service
```

### File Structure

```
atlas-bot/
├── bot.py                    # Main Discord bot
├── atlas_diagnostics.py      # Shared bot/service/cron/MCP health checks
├── channel_configs.py        # Configured Discord channel roles and routing
├── garmin_workout_fallback.py # Repo-native Garmin workout lookup fallback
├── med_config.py             # Shared medication config loader
├── meds.json                 # Medication config (gitignored — personal health data)
├── send_message.py           # Send messages to Discord programmatically
├── run_cron.sh               # Cron entry point (called every minute)
├── cron/
│   ├── dispatcher.py         # Job scheduler and executor
│   ├── jobs.json             # Job definitions (schedules, prompts, tools)
│   ├── state/
│   │   └── last_runs.json    # Tracks last run times to prevent duplicates
│   ├── context_drift.sh      # Retired shim; context drift runs through jobs.json
│   ├── daily_summary.sh      # End-of-day summary generator
│   ├── med_reminder.sh       # Medication reminder via webhook
│   ├── ops_watchdog.py       # Silent-unless-noteworthy process hygiene checks
│   ├── session_archive.sh    # Nightly session archive and reset
│   ├── task_triage.sh        # Retired shim; project triage belongs in jobs.json
│   └── vault_index.py        # Builds machine-readable vault index
├── docs/
│   ├── guides/               # User/operator guides
│   ├── plans/                # Roadmaps and implementation plans
│   ├── setup/                # Setup walkthroughs
│   └── specs/                # Feature specs and design notes
├── examples/
│   ├── meds.json.example
│   └── user-profile.json.example
├── hooks/
│   ├── tasks_summary.sh      # SessionStart: inject due tasks
│   ├── recent_changes.sh     # SessionStart: inject recent file changes
│   ├── recent_summaries.sh   # Recent daily summary context
│   ├── librarian_context.sh  # SessionStart: inject compact vault snapshot
│   ├── calendar_context.sh   # PreToolUse: 7-day calendar for event creation
│   └── workout_oura_data.sh  # PostToolUse: fetch Oura + WHOOP data after workout log
├── mcp-servers/
│   ├── oura/                 # Custom Oura Ring MCP server
│   │   ├── mcp_server.py
│   │   └── README.md
│   ├── garmin/              # Repo-managed Garmin Connect MCP server
│   │   ├── mcp_server.py
│   │   └── README.md
│   ├── whoop/                # Repo-managed WHOOP MCP server
│   │   ├── mcp_server.py
│   │   └── README.md
│   ├── google_bot/           # Repo-managed Gmail + Google Calendar MCP server
│   │   ├── mcp_server.py
│   │   └── README.md
│   └── credentials/          # OAuth credentials (gitignored)
├── .claude/
│   └── skills/               # Reusable ATLAS skill definitions
│       ├── morning-briefing.md
│       ├── daily-summary.md
│       ├── health-pattern-monitor.md
│       ├── log-workout.md
│       ├── log-cardio.md
│       ├── log-medication.md
│       ├── second-brain-librarian.md
│       ├── backend-concepts-lesson.md
│       ├── weekly-review.md
│       └── weekly-training-planner.md
├── etc/
│   ├── systemd/
│   │   └── atlas-bot.service  # systemd unit file
│   └── logrotate.d/
│       └── atlas-bot          # Log rotation config
├── sessions/                  # Per-channel session data (gitignored)
│   └── {channel_id}/
│       ├── .claude/
│       │   ├── settings.json        # Harness session hooks config
│       │   └── settings.local.json  # Harness permissions
│       ├── AGENTS.md                # Generated Codex session instructions when Codex is active
│       ├── ATLAS-Garmin-Workout-Helper.md  # Garmin MCP/fallback instructions
│       ├── ATLAS-Channel-Role.md    # Generated channel purpose and preferred-skill context
│       ├── attachments/             # Downloaded Discord attachments
│       └── model.txt                # Channel model preference
├── logs/
│   └── cron/                  # Per-job log files (gitignored)
└── .env                       # Your configuration (gitignored)
```

### Hooks System

```mermaid
flowchart LR
    subgraph "SessionStart"
        A[System Prompt] --> B[ATLAS-Context.md]
        B --> C[Date/Time]
        C --> D[Tasks Due]
        D --> E[Recent Changes]
    end

    subgraph "PreToolUse"
        F[calendar_context.sh]
    end

    subgraph "PostToolUse"
        G[workout_oura_data.sh]
    end

    E --> H[Active harness receives full context]
    F -.->|google-calendar create/update| H
    G -.->|Write to Workout-Logs/| H
```

Hooks are defined in `bot.py` `CHANNEL_SETTINGS` and run at different stages:

**SessionStart** -- Runs on first message in a new session:

1. **System Prompt** -- Custom instructions for the active harness
2. **Persistent Context** -- `ATLAS-Context.md` with stable facts, active threads, preferences
3. **Date/Time** -- Current date and time for temporal awareness
4. **Tasks Summary** -- Overdue and due-today items from your vault
5. **Recent Changes** -- Files modified in the last 24 hours

**PreToolUse** -- Runs before specific tool calls:

- `calendar_context.sh` -- Triggered before calendar create/update tools. Injects a 7-day ISO date table so event scheduling lands on the correct dates.

**PostToolUse** -- Runs after specific tool calls:

- `workout_oura_data.sh` -- Triggered after writing to `Workout-Logs/20*.md`. Fetches Oura and WHOOP recovery data to add context to the workout log.

## Usage

### Triggering the Bot

The bot responds to:

- Any message in a configured auto-activation channel
- Direct @mentions in any channel

### Commands

| Command             | Description                                    |
| ------------------- | ---------------------------------------------- |
| `!help`             | Show available commands                        |
| `!status` / `!ops`  | Show bot, service, cron, and MCP helper health |
| `!model`            | Show the current model for the active provider |
| `!model <model>`    | Switch model for this channel                  |
| `!recall <query>`   | Search the vault like a librarian              |
| `!recent-notes`     | Summarize recently updated notes               |
| `!open-loops`       | Review unresolved tasks and waiting states     |
| `!orphan-notes`     | Find notes that need links or cleanup          |
| `!librarian`        | Generate a compact vault digest                |
| `!reset` / `!clear` | Reset the current channel's session            |

### Example Conversation

```
You: What tasks do I have due today?

ATLAS: Based on your vault, here are your tasks due today:
- [ ] Review PR for auth changes 📅 2026-02-14
- [ ] Send weekly update email 📅 2026-02-14

You: Mark the first one as done

ATLAS: I've updated the task in your vault:
- [x] Review PR for auth changes 📅 2026-02-14 ✅
```

## Scheduled Jobs

The cron dispatcher (`cron/dispatcher.py`) runs every minute via `run_cron.sh` and executes jobs defined in `cron/jobs.json`. Jobs can run the active agent harness with specific models, tools, and prompts, or execute shell scripts directly.

When `ATLAS_AGENT_PROVIDER=codex`, agent-backed cron jobs automatically get a longer timeout budget because Codex is slower in unattended runs. The default is `3x` the configured job timeout, adjustable with `ATLAS_CODEX_CRON_TIMEOUT_MULTIPLIER`. If a specific job needs custom tuning later, `cron/jobs.json` also supports explicit `timeout_seconds_by_provider` overrides.

| Job                     | Schedule        | Channel      | Description                                                |
| ----------------------- | --------------- | ------------ | ---------------------------------------------------------- |
| Morning Briefing        | 5:30 AM daily   | `#briefings` | Weather, calendar, training plan, medications, recovery    |
| Daily Summary           | 11:55 PM daily  | `#briefings` | End-of-day review, context file updates                    |
| Weekly Review           | 8:00 PM Sun     | `#briefings` | Synthesize week's data into structured review              |
| Weekly Training Planner | 12:00 PM Sun    | `#health`    | Plan next week's training based on recovery and calendar   |
| Medication Reminder     | 5 AM & 8 PM     | `#health`    | Config-driven medication reminders (reads `meds.json`)     |
| Medication Config Sync  | 1:00 AM daily   | `#health`    | Syncs `meds.json` with vault `Medications.md`              |
| Health Pattern Monitor  | 10:30 AM daily  | `#health`    | Oura + WHOOP trend analysis, alerts only when noteworthy   |
| Recovery Context Update | 10:00 AM daily  | Silent       | Backfill Oura + WHOOP data into workout logs               |
| Stale Project Detector  | 8:00 AM Sat     | `#projects`  | Scan vault for projects untouched 30+ days                 |
| Context Drift Detector  | 8:00 AM Sun     | `#projects`  | Check ATLAS-Context.md for consistency                     |
| Second Brain Librarian  | 7:45 AM Mon/Fri | `#projects`  | Reviews recent notes, open loops, orphans, and stale notes |
| Vault Index Refresh     | 2:15 AM daily   | Silent       | Rebuilds `vault-index.json` and `vault-index.md`           |
| MCP Health Check        | 6:00 AM Mon     | `#atlas-dev` | Validate auth for Calendar, Gmail, Oura, and Garmin        |
| ATLAS Ops Watchdog      | Every 15 min    | `#atlas-dev` | Alerts on duplicate bots, orphan helpers, or cron failures |
| Session Archive         | 12:05 AM daily  | `#atlas-dev` | Archive session data, reset after the nightly summary      |

All times are in `America/Los_Angeles`. The dispatcher tracks last run times in `cron/state/last_runs.json` to prevent duplicate executions. Use `--run-now JOB_ID` to manually trigger a job. The ops watchdog stores repeat-suppression state in `cron/state/ops_watchdog.json` so unchanged alerts do not post every run.

Setup:

1. Create Discord webhooks for the configured target channels
2. Add the matching `DISCORD_WEBHOOK_*` values to `.env`
3. Add system crontab entry: `* * * * * /path/to/atlas-bot/run_cron.sh`

`DISCORD_WEBHOOK_URL` still works as the legacy final fallback during rollout.

## MCP Integrations

| Server              | Purpose                                                                      |
| ------------------- | ---------------------------------------------------------------------------- |
| **Oura Ring**       | Sleep, readiness, activity, HRV, and stress data (`mcp-servers/oura/`)       |
| **WHOOP**           | Sleep performance, recovery, strain, and workout data (`mcp-servers/whoop/`) |
| **Garmin Connect**  | Activities, training status, body composition, workouts, and more            |
| **Google Calendar** | Event creation, listing, free/busy queries, scheduling                       |
| **Gmail**           | Email search, reading, sending, label and filter management                  |
| **Weather**         | Forecasts, current conditions, and alerts (NOAA + Open-Meteo)                |

See [`mcp-servers/oura/README.md`](mcp-servers/oura/README.md) for Oura server setup.
See [`mcp-servers/garmin/README.md`](mcp-servers/garmin/README.md) for Garmin server setup.
See [`mcp-servers/whoop/README.md`](mcp-servers/whoop/README.md) for WHOOP server setup.
See [`docs/setup/google-bot-account-setup.md`](docs/setup/google-bot-account-setup.md) for giving ATLAS a dedicated Google identity through the repo-managed `google_bot` MCP server.

Garmin is now repo-managed for both providers:

- Codex gets the `garmin` server through the managed config generated by `agent_runner.py`.
- Claude Code reads the same repo-owned Garmin server from `~/.mcp.json`, which `mcp-servers/garmin/oauth_setup.py` can write automatically.
- If direct `mcp__garmin__*` tools are still unavailable in a session, `garmin_workout_fallback.py` resolves repo-managed Garmin tokens first and falls back to `~/.garminconnect` for normalized workout JSON.

WHOOP is now repo-managed for both providers:

- Codex gets the `whoop` server through the managed config generated by `agent_runner.py`.
- Claude Code reads the same repo-owned WHOOP server from `~/.mcp.json`, which `mcp-servers/whoop/oauth_setup.py` can write automatically.

ATLAS now uses a repo-managed `google_bot` MCP server for Gmail plus Google Calendar so the bot's Google identity stays separate from the ChatGPT/Codex account login.

## Skills

Reusable skill definitions in `.claude/skills/` that the active harness can invoke:

| Skill                     | Preferred Channels     | Description                                                            |
| ------------------------- | ---------------------- | ---------------------------------------------------------------------- |
| `morning-briefing`        | `#atlas`, `#health`    | Daily briefing with weather, schedule, training, medications, recovery |
| `daily-summary`           | `#briefings`           | End-of-day review of activities and structured summary                 |
| `weekly-review`           | `#briefings`           | Synthesize week's data into structured review with trends and patterns |
| `health-pattern-monitor`  | `#health`              | Analyze 10-day Oura + WHOOP trends and alert only when noteworthy      |
| `weekly-training-planner` | `#health`              | Recovery-aware training plan with calendar integration                 |
| `log-workout`             | `#health`              | Parse freeform workout reports into structured vault logs              |
| `log-cardio`              | `#health`              | Parse freeform cardio session reports into structured logs             |
| `log-medication`          | `#health`              | Parse medication reports and log doses with validation                 |
| `second-brain-librarian`  | `#projects`, `#atlas`  | Review note health, recent changes, open loops, and cleanup priorities |
| `backend-concepts-lesson` | `#atlas-dev`, `#atlas` | Deliver backend architecture lessons from the learning queue           |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Run root app linter
ruff check .

# Format code
ruff format .

# Run root app tests
pytest tests

# Run all tests, including MCP server packages
pytest
```

### Pre-commit Hooks

- **Ruff** - Python linting and formatting
- **Prettier** - Markdown, JSON, YAML formatting
- **Standard hooks** - Trailing whitespace, merge conflicts, etc.

## Security Considerations

```mermaid
flowchart TB
    subgraph "What's Protected"
        A[.env - Discord token]
        B[sessions/ - Conversation history]
        C[System prompt - Your instructions]
        D[mcp-servers/credentials/ - OAuth keys]
    end

    subgraph "What's Allowed"
        E[Read any file]
        F[Write/Edit files]
        G[Safe bash commands]
    end

    subgraph "What's Blocked"
        H[rm - Delete files]
        I[chmod - Change permissions]
        J[Dangerous commands]
    end
```

- **Credentials** are stored in `.env` (gitignored)
- **Sessions** contain conversation history (gitignored)
- **OAuth keys** in `mcp-servers/credentials/` (gitignored)
- **Tool permissions** are pre-configured in `CHANNEL_PERMISSIONS`
- **Dangerous commands** like `rm`, `chmod` are not in the allow list

## Roadmap

- [ ] Real-time streaming status updates
- [ ] Interactive permission prompts via Discord buttons
- [ ] Multi-project channel mapping
- [x] Model switching (`!model` with provider-specific models)

## License

MIT

---

Built for a configurable Claude Code / Codex ATLAS workflow
