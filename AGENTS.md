# Repository Guidelines

## Project Structure & Module Organization

The main application lives at the repository root. `bot.py` runs the Discord bot, `send_message.py` sends outbound Discord messages, and `med_config.py` handles medication config loading. Scheduled automation lives in `cron/` with `dispatcher.py`, job definitions in `cron/jobs.json`, and helper shell scripts such as `daily_summary.sh`. Session hooks live in `hooks/`. Tests for the root app live in `tests/` and follow the module under test, for example `tests/test_bot_sessions.py`. A separate Python package for the Oura MCP server lives in `mcp-servers/oura/` with its own `src/` and `tests/`.

## Build, Test, and Development Commands

Set up a local environment with:

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

Run the bot locally with `python bot.py`. Run cron jobs through `./run_cron.sh`, or trigger dispatcher logic directly from `cron/dispatcher.py` when debugging. Use `ruff check .` for linting, `ruff format .` for formatting, and `pytest` for the full test suite. For targeted work, run `pytest tests/test_bot_sessions.py` or `pytest tests/test_bot_sessions.py::TestEnsureChannelSession::test_creates_channel_dir`.

## Coding Style & Naming Conventions

Target Python 3.10+. Ruff is the source of truth for style: 100-character lines, spaces for indentation, and double quotes. Keep modules and functions in `snake_case`; test files should be named `test_<area>.py`. Prefer explicit type hints on new or changed functions. Keep shell scripts executable, focused, and named for the job they perform, for example `session_archive.sh`.

## Testing Guidelines

Use `pytest` with `pytest-asyncio` in auto mode. Add tests in `tests/` or `mcp-servers/oura/tests/` beside the relevant code. Mock Discord, filesystem, and network boundaries; tests should not require secrets or live services. Use fixtures from `tests/conftest.py` and redirect file writes to `tmp_path` where possible.

## Commit & Pull Request Guidelines

Recent history follows Conventional Commits: `fix:`, `chore:`, `refactor:`, and `docs:`. Keep commit messages imperative and scoped to one change. Pull requests should describe behavior changes, list tests run, link related issues, and include screenshots only when UI or message formatting changes are relevant.

## Security & Configuration Tips

Do not commit `.env`, `meds.json`, session data, or credentials under `mcp-servers/credentials/`. Review Discord permissions and any filesystem paths exposed through bot or hook configuration before merging.
