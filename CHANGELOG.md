# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Cron dispatcher system with 12 scheduled jobs (`cron/dispatcher.py`, `cron/jobs.json`)
- Model switching per channel (`!model sonnet|opus`, defaults to opus)
- Attachment support for images and PDFs via Discord uploads
- MCP integrations: Oura Ring, Google Calendar, Gmail, Weather
- Claude skills system (6 skills: morning-briefing, daily-summary, log-workout, log-cardio, log-medication, weekly-training-planner)
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
- `run_cron.sh` entry point called every minute via system crontab
- systemd service and logrotate configs (`etc/`)
- `DISCORD_CHANNEL_ID` and `CONTEXT_PATH` environment variables

### Changed

- Default model switched from sonnet to opus
- Session reset now clears Claude's internal storage (`~/.claude/projects/`)
- State saved before job execution to prevent duplicate cron runs
- Calendar context hook expanded to full 7-day ISO date table
- Hooks now span three event types: SessionStart, PreToolUse, PostToolUse
- `DISCORD_WEBHOOK_URL` used for cron job notifications (was daily digest)

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
