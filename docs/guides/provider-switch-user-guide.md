# Provider Switch User Guide

ATLAS can now run on either Claude Code or Codex without changing the Discord workflow.

## 1. Choose the provider

Set this in `.env`:

```bash
ATLAS_AGENT_PROVIDER=claude
```

or:

```bash
ATLAS_AGENT_PROVIDER=codex
```

Claude remains the default if the variable is unset.

## 2. Optional Codex settings

If you want Codex enabled, these defaults are supported:

```bash
ATLAS_CODEX_MODEL=gpt-5.4
ATLAS_CODEX_REASONING_EFFORT=xhigh
```

If you want the bot to use a dedicated Codex profile instead of your normal one:

```bash
ATLAS_CODEX_HOME=/path/to/bot-specific-codex-home
```

## 3. Restart the bot

After changing `.env`, restart the bot service and cron service/process so they pick up the new provider:

```bash
./restart_atlas_services.sh
```

Shortcut:

```bash
./set_atlas_provider.sh codex
```

or:

```bash
./set_atlas_provider.sh claude
```

That command updates `.env` and restarts both services automatically.

## 4. Use it in Discord

The Discord workflow does not change.

- `!model` shows the current model for the active provider.
- `!model opus` or `!model sonnet` works when the provider is Claude.
- `!model gpt-5.4` works when the provider is Codex.
- `!reset` clears the current channel session and starts fresh.

## 5. Roll back fast

If anything looks wrong:

```bash
ATLAS_AGENT_PROVIDER=claude
```

Then restart the bot and cron service/process. That restores the known-good Claude-backed setup.
