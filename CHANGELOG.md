# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `meds.json` config file for medication names, doses, schedules, and vault markers (gitignored)
- `meds.json.example` with sanitized placeholder data
- `med_config.py` shared loader with `load_meds()` and `find_med_by_content()`
- `med_config_sync` nightly cron job — Claude compares vault `Medications.md` against `meds.json` and auto-updates on drift
- Cron dispatcher system with 12 scheduled jobs (`cron/dispatcher.py`, `cron/jobs.json`)
- Model switching per channel (`!model sonnet|opus`, defaults to opus)
- Attachment support for images and PDFs via Discord uploads
- MCP integrations: Oura Ring, Google Calendar, Gmail, Weather, Garmin Connect
- Claude skills system (8 skills: morning-briefing, daily-summary, log-workout, log-cardio, log-medication, weekly-training-planner, health-pattern-monitor, weekly-review)
- Medication tracking with reaction-based dose logging (checkmark reactions on reminders)
- `send_message.py` for sending messages to Discord channels programmatically
- Nightly session archive and reset (`cron/session_archive.sh`)
- `!help` command showing all available commands
- Three new hooks: `calendar_context.sh` (PreToolUse), `recent_summaries.sh`, `workout_oura_data.sh` (PostToolUse)
- Persistent context file (`ATLAS-Context.md`) injected at session start
- Context drift detector for weekly consistency checks
- Stale project detector for vault maintenance
- MCP health check job for OAuth token validation
- Oura context updater for daily workout logs
- Health pattern monitor — daily Oura trend analysis, alerts only when noteworthy
- Weekly review — Sunday synthesis of daily summaries, health metrics, and project activity
- Weekly training planner — recovery-aware training plan generation with calendar integration
- Garmin MCP tool permissions for cron and Discord sessions
- Automatic skills symlink creation in Discord channel sessions for skill discovery
- `suppress_if_contains` feature in cron dispatcher for silent-unless-noteworthy jobs
- `run_cron.sh` entry point called every minute via system crontab
- systemd service and logrotate configs (`etc/`)
- `DISCORD_CHANNEL_ID` and `CONTEXT_PATH` environment variables
- Pre-commit hooks with ruff (lint + format), prettier, and standard checks

### Changed

- `user-profile.json` config file for location data (gitignored), with `.json.example` template
- `morning-briefing` skill reads weather coordinates from `user-profile.json` instead of hardcoding
- `log-medication` skill reads medication names, schedules, and intervals from `meds.json` instead of hardcoding
- `weekly-training-planner` skill reads program template (exercises, volume, RPE, rest periods) from Training-State.md and personal constraints (equipment, injuries, HR, schedule) from Training-Profile.md instead of hardcoding
- Medication tracking refactored from hardcoded names/schedules to config-driven (`meds.json`)
- 4 separate medication cron jobs consolidated into 1 config-driven job (`med_reminder`)
- `med_reminder.sh` reads `meds.json` via jq instead of hardcoded if/elif blocks; removed duplicate curl webhook (dispatcher handles notification)
- `morning-briefing.md` skill reads medication schedules from `meds.json` instead of hardcoded day-of-week logic
- Default model switched from sonnet to opus
- Session reset now clears Claude's internal storage (`~/.claude/projects/`)
- State saved before job execution to prevent duplicate cron runs
- Calendar context hook expanded to full 7-day ISO date table
- Hooks now span three event types: SessionStart, PreToolUse, PostToolUse
- `DISCORD_WEBHOOK_URL` used for cron job notifications (was daily digest)
- Recent daily summaries now injected into SessionStart context via `recent_summaries.sh`

### Fixed

- Cron-spawned Claude sessions now run from project root (`BOT_DIR`) so skills are discoverable
- Null `notify` field in cron jobs no longer causes `AttributeError`
- `CLAUDECODE` env var stripped to prevent nested session errors
- Hardcoded paths replaced with environment variables for portability

### Removed

- `daily_digest.py` and `run_digest.sh` (replaced by cron dispatcher and morning-briefing skill)

### Security

- Credentials stored in `.env` (gitignored)
- Session data stored locally (gitignored)
- MCP OAuth credentials stored in `mcp-servers/credentials/` (gitignored)
- Dangerous commands not in allow list

## [0.1.0] - 2026-01-03

### Added

- Initial public release
- Discord bot with Claude Code CLI integration
- Session continuity using `--continue` flag
- Channel isolation with per-channel sessions
- Configurable session hooks for context injection
- Pre-approved tool access (Read, Write, Edit, Glob, Grep, Bash)
- 10-minute timeout protection
- Daily digest script with Discord webhook support
- Environment variable configuration (no hardcoded paths)
- Comprehensive documentation with Mermaid diagrams
