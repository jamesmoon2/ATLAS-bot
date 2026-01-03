# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release of ATLAS Bot
- Discord bot with Claude Code CLI integration
- Session continuity using `--continue` flag
- Channel isolation with per-channel sessions
- Configurable session hooks for context injection
- Pre-approved tool access (Read, Write, Edit, Glob, Grep, Bash)
- 10-minute timeout protection
- Daily digest script with Discord webhook support
- Environment variable configuration (no hardcoded paths)
- Comprehensive documentation with Mermaid diagrams

### Security

- Credentials stored in `.env` (gitignored)
- Session data stored locally (gitignored)
- Dangerous commands not in allow list

## [0.1.0] - 2026-01-03

### Added

- Initial public release
