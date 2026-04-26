# ATLAS Multi-Channel Plan

Status: implemented. See `docs/channel-user-guide.md` for the user-facing channel guide and
`README.md` for setup/configuration.

## Goal

Make ATLAS work as a configured multi-channel Discord system instead of a single
`#atlas` channel with mention-based exceptions, without breaking existing
single-channel deployments mid-rollout.

The target channels are:

| Channel      | Role                                                                 |
| ------------ | -------------------------------------------------------------------- |
| `#atlas`     | General conversation and catch-all assistant work                    |
| `#health`    | Health, medication, workout, recovery, Oura, WHOOP, Garmin, training |
| `#projects`  | Project work, tasks, decisions, stale project scans, vault follow-up |
| `#briefings` | Read-mostly daily/weekly summaries, reports, ambient briefings       |
| `#atlas-dev` | ATLAS harness work, operational alerts, bot development              |

`#atlas-dev` is part of this rollout (resolves Open Decision #1). `#projects`
may be deprecated later if it does not prove useful, but it
should be configured now so project/task automation has a clean destination.

## Default Decisions

These decisions are committed for v1 to keep the design small. Each is
reversible later without breaking the public surface.

| Decision                          | v1 choice                                                                  | Why                                                                                          |
| --------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Where channel role context lives  | Per-session `ATLAS-Channel-Role.md` injected via a `SessionStart` hook     | Matches the existing `atlas_config.py` hook pattern; no special provider plumbing            |
| How skills are scoped per channel | Soft hint via role context only ("prefer these skills")                    | Avoids per-channel `.claude/skills/` symlink farms or `skills_dir` plumbing                  |
| Hooks across channels             | Identical `SessionStart`/`PreToolUse`/`PostToolUse` hooks for all channels | Existing hooks (`tasks_summary.sh`, etc.) take no channel arg; parameterizing has low payoff |
| Permissions across channels       | Identical permission set for all channels                                  | Same reason; revisit if a channel needs a hard restriction                                   |
| `#briefings` "read-mostly"        | Pure role-context guidance, no code-level restriction                      | Lowest risk; revisit only if the channel gets misused                                        |
| Channel identity                  | Channel ID first, channel name second                                      | Discord channel renames must not silently break activation                                   |
| Default model per channel         | Sourced from `ChannelConfig.default_model`, not a hardcoded `"opus"`       | Removes a hidden global default in `bot.py:316-323`                                          |

## What Is Needed From James

Conversational multi-channel support does not require webhooks — the bot
auto-activates in configured channels once code lands.

Cron distribution **does** require channel-specific webhooks.

### New environment variables

Webhooks (one per configured channel):

| Channel      | Webhook env var             |
| ------------ | --------------------------- |
| `#atlas`     | `DISCORD_WEBHOOK_ATLAS`     |
| `#health`    | `DISCORD_WEBHOOK_HEALTH`    |
| `#projects`  | `DISCORD_WEBHOOK_PROJECTS`  |
| `#briefings` | `DISCORD_WEBHOOK_BRIEFINGS` |
| `#atlas-dev` | `DISCORD_WEBHOOK_ATLAS_DEV` |

Optional channel-ID pins (for rename safety):

| Channel      | Channel-ID env var           |
| ------------ | ---------------------------- |
| `#atlas`     | `ATLAS_CHANNEL_ID_ATLAS`     |
| `#health`    | `ATLAS_CHANNEL_ID_HEALTH`    |
| `#projects`  | `ATLAS_CHANNEL_ID_PROJECTS`  |
| `#briefings` | `ATLAS_CHANNEL_ID_BRIEFINGS` |
| `#atlas-dev` | `ATLAS_CHANNEL_ID_ATLAS_DEV` |

Optional allowlist override (kill switch for noisy channels without a code
deploy):

```
ATLAS_CONFIGURED_CHANNELS=atlas,health,projects,briefings,atlas-dev
```

If unset, all channels declared in `channel_configs.py` are configured. If set,
only the listed channels auto-activate; others fall back to mention-only.

### Confirm exact Discord channel names

- `atlas`
- `health`
- `projects`
- `briefings`
- `atlas-dev`

### Backward compatibility

- `DISCORD_WEBHOOK_URL` continues to work as a final fallback (see §6).
- `DISCORD_CHANNEL_ID` continues to work for legacy `send_message.py` invocations.
- Existing single-channel deployments must not break after upgrade — see
  Rollout Order below.

## Current Repo State

ATLAS already has partial channel isolation:

- Session directories are keyed by Discord `channel_id`.
- Each channel already gets its own model preference via `model.txt`.
- Per-channel locks prevent concurrent runs in the same Discord channel.

Missing pieces:

- `bot.py:382` auto-activates only on a channel literally named `atlas`.
- Other channels only work when the bot is mentioned.
- `CHANNEL_SETTINGS` and `CHANNEL_PERMISSIONS` (`bot.py:70-76`) are global and
  built once at import.
- Cron jobs in `cron/jobs.json` route to `DISCORD_WEBHOOK_URL`.
- `send_message.py:23`, `cron/session_archive.sh:10`, `cron/context_drift.sh:9`,
  and `cron/task_triage.sh:9` all hard-require `DISCORD_CHANNEL_ID`.
- `get_channel_model` (`bot.py:316-323`) defaults to `"opus"` for every channel.

## Implementation Plan

### 1. Add `channel_configs.py`

Create a dedicated module with a concrete dataclass.

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ChannelConfig:
    key: str                                    # canonical channel name, e.g. "health"
    role_description: str                       # injected as role context
    webhook_env: str                            # e.g. "DISCORD_WEBHOOK_HEALTH"
    channel_id_env: str | None = None           # e.g. "ATLAS_CHANNEL_ID_HEALTH"
    default_model: str = "opus"                 # passed to resolve_model_for_provider
    auto_activate: bool = True                  # respond without @mention
    read_mostly: bool = False                   # advisory only in v1
    preferred_skills: tuple[str, ...] = ()      # surfaced in role context

CHANNEL_CONFIGS: dict[str, ChannelConfig] = {
    "atlas":      ChannelConfig(key="atlas", ...),
    "health":     ChannelConfig(key="health", ...),
    "projects":   ChannelConfig(key="projects", ...),
    "briefings":  ChannelConfig(key="briefings", read_mostly=True, ...),
    "atlas-dev":  ChannelConfig(key="atlas-dev", ...),
}

def get_channel_config(*, channel_id: int, channel_name: str) -> ChannelConfig | None:
    """Resolve by channel_id env pin first, then by name. Honors ATLAS_CONFIGURED_CHANNELS."""
    ...
```

Resolution rules:

- If `channel_id` matches any `ChannelConfig.channel_id_env` value, return it.
- Else if `channel_name.lower()` matches a `ChannelConfig.key`, return it.
- If `ATLAS_CONFIGURED_CHANNELS` is set and the resolved key is not in it,
  return `None` (treat as unconfigured).
- Otherwise return `None`.

### 2. Update Bot Activation

Replace the literal-name check in `bot.py:382`:

```python
channel_config = get_channel_config(
    channel_id=message.channel.id,
    channel_name=message.channel.name,
)
is_configured_channel = channel_config is not None and channel_config.auto_activate
```

Process messages when:

- author is not a bot, **and**
- bot is mentioned, **or** channel is configured for auto-activation.

Non-configured channels remain ignored unless mentioned. (Mention-only
behavior still works in any channel — no regression.)

### 3. Plumb Channel Config Through the Session Path

Threading goal: every session-touching function takes a `ChannelConfig | None`
(or extracts it from the channel) instead of relying on globals.

Functions affected:

- `ensure_channel_session(channel_id)` → also accept `channel_config`; use it
  to write per-session role context (see §4) and resolve the default model.
- `run_agent(channel_id, ...)` → look up `channel_config` once at entry and
  pass it through.
- `get_channel_model` / `set_channel_model` → fall back to
  `channel_config.default_model` instead of hardcoded `"opus"`.
- `run_channel_message` (in `agent_runner`) → no signature change required
  unless we surface the config in session metadata.

**Out of scope for v1:** per-channel `CHANNEL_SETTINGS` (hooks) and
`CHANNEL_PERMISSIONS`. Both stay global. Justification is in Default Decisions.

Session metadata (written to `sessions/<id>/ATLAS-Session.json` if it exists)
should include:

- `channel_id`
- `channel_name`
- `channel_key`
- `active_provider`
- `default_model`
- `updated_at`

`prepare_session_dir` rewrites this metadata on every touch — no destructive
migration needed for existing session dirs.

### 4. Channel Role Context (concrete mechanism)

For each configured channel, write `sessions/<channel_id>/ATLAS-Channel-Role.md`
during `prepare_session_dir`. Content comes from
`ChannelConfig.role_description` plus a "preferred skills" footer rendered
from `ChannelConfig.preferred_skills`.

Add one item to the `SessionStart` hooks in `atlas_config.build_channel_settings`:

```python
{"type": "command", "command": shell_command("cat", role_md_path)},
```

This requires plumbing the role file path into `build_channel_settings`
(currently it takes `system_prompt_path` and `context_path` — add a third).

Role descriptions (drafted, refine in PR):

- **`#atlas`** — General ATLAS conversation. Broad context; no specialization.
- **`#health`** — Prioritize health, training, medications, recovery, symptoms,
  supplements, Oura, WHOOP, Garmin, and workout logs. Prefer concrete logging
  and trend detection.
- **`#projects`** — Prioritize project state, tasks, decisions, stale threads,
  follow-up. Keep recommendations action-oriented and grounded in the vault.
- **`#briefings`** — Treat as read-mostly. Prefer concise reports, summaries,
  and ambient updates. Avoid turning it into a long conversational workspace
  unless James explicitly asks.
- **`#atlas-dev`** — Prioritize ATLAS harness development, repo changes,
  operational alerts, CI, test failures, MCP setup, and automation work.

### 5. Skills by Channel (soft hints only in v1)

Keep one shared physical `.claude/skills/` directory. Channel role context
(§4) names the most relevant skills as a hint to the agent.

Suggested mapping (rendered into the role context footer):

| Skill                                           | Preferred channels      |
| ----------------------------------------------- | ----------------------- |
| `morning-briefing`                              | `#briefings`, `#health` |
| `daily-summary`                                 | `#briefings`            |
| `weekly-review`                                 | `#briefings`            |
| `health-pattern-monitor`                        | `#health`               |
| `weekly-training-planner`                       | `#health`               |
| `log-workout` / `log-cardio` / `log-medication` | `#health`               |
| `second-brain-librarian`                        | `#projects`, `#atlas`   |
| `backend-concepts-lesson`                       | `#atlas-dev`, `#atlas`  |

`#atlas` keeps access to all skills as the catch-all. Hard restriction (per-
channel `skills_dir` or symlink farm) is deferred — call it out explicitly in
the PR description so we don't quietly drift past it.

### 6. Route Cron Jobs by Channel

Update `cron/jobs.json` so each job's `notify.url_env` points at a channel-
specific webhook. The dispatcher (`cron/dispatcher.py:275-298` `send_webhook`)
is updated to walk a fallback chain instead of a single env var:

```
configured url_env  →  DISCORD_WEBHOOK_ATLAS  →  DISCORD_WEBHOOK_URL
```

This guarantees that a partially-rolled deployment (some webhook env vars
unset) still delivers messages somewhere instead of silently dropping them.

Routing (commit to a single destination per job — no `if X exists else Y`):

| Job                       | Channel      | `url_env`                   |
| ------------------------- | ------------ | --------------------------- |
| `morning_briefing`        | `#briefings` | `DISCORD_WEBHOOK_BRIEFINGS` |
| `daily_summary`           | `#briefings` | `DISCORD_WEBHOOK_BRIEFINGS` |
| `weekly_review`           | `#briefings` | `DISCORD_WEBHOOK_BRIEFINGS` |
| `weekly_training_planner` | `#health`    | `DISCORD_WEBHOOK_HEALTH`    |
| `med_reminder`            | `#health`    | `DISCORD_WEBHOOK_HEALTH`    |
| `med_config_sync`         | `#health`    | `DISCORD_WEBHOOK_HEALTH`    |
| `health_pattern_monitor`  | `#health`    | `DISCORD_WEBHOOK_HEALTH`    |
| `oura_context_update`     | silent       | none                        |
| `stale_project_detector`  | `#projects`  | `DISCORD_WEBHOOK_PROJECTS`  |
| `context_drift`           | `#projects`  | `DISCORD_WEBHOOK_PROJECTS`  |
| `librarian_digest`        | `#projects`  | `DISCORD_WEBHOOK_PROJECTS`  |
| `vault_index_refresh`     | silent       | none                        |
| `mcp_health_check`        | `#atlas-dev` | `DISCORD_WEBHOOK_ATLAS_DEV` |
| `session_archive`         | `#atlas-dev` | `DISCORD_WEBHOOK_ATLAS_DEV` |

### 7. Clean Up Single-Channel Assumptions

| File                         | Issue                                                             | Concrete fix                                                                                                                                                                                                           |
| ---------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `send_message.py:23`         | Reads only `DISCORD_CHANNEL_ID`                                   | Add `--channel <name>` (resolves via `CHANNEL_CONFIGS` + guild lookup) and `--channel-id <id>`. Precedence: `--channel-id` > `--channel` > `DISCORD_CHANNEL_ID`. Positional message arg unchanged for backward compat. |
| `cron/session_archive.sh:10` | Hard-fails without `DISCORD_CHANNEL_ID`; archives one session     | Drop `DISCORD_CHANNEL_ID` requirement. Iterate `${BOT_DIR}/sessions/*/` for any dir containing `.claude/`; archive each (channel ID is in the dir name already).                                                       |
| `cron/context_drift.sh:9`    | Legacy script duplicating `jobs.json` `context_drift`             | Retire the shell script. The `jobs.json` prompt job already covers it.                                                                                                                                                 |
| `cron/task_triage.sh:9`      | Legacy script that POSTs directly to `DISCORD_WEBHOOK_URL`        | Retire or convert to a `jobs.json` prompt job routed to `#projects`.                                                                                                                                                   |
| `.env.example`               | Documents only generic webhook/channel id                         | Add the new webhook + channel-id env vars and the optional allowlist. Keep `DISCORD_WEBHOOK_URL` and `DISCORD_CHANNEL_ID` in the file marked as legacy fallback.                                                       |
| `README.md`                  | Says channel isolation exists but not configured-channel behavior | Document configured channels, env vars, fallback chain, allowlist.                                                                                                                                                     |

### 8. Tests

New / updated coverage:

- Configured-channel auto-activation for `#atlas`, `#health`, `#projects`,
  `#briefings`, `#atlas-dev`.
- Non-configured channels stay quiet unless the bot is mentioned.
- Mention still works in any channel.
- `get_channel_config` resolves by channel ID first, then by name.
- `ATLAS_CONFIGURED_CHANNELS` allowlist removes a channel from auto-activation
  without removing it from `CHANNEL_CONFIGS`.
- `prepare_session_dir` writes `ATLAS-Channel-Role.md` and `ATLAS-Session.json`
  with expected fields.
- `SessionStart` hook order includes the role file `cat` after system prompt.
- Default model per channel comes from `ChannelConfig.default_model`, not a
  hardcoded `"opus"`.
- Cron jobs route to expected `url_env` values.
- Webhook fallback chain: per-channel → `DISCORD_WEBHOOK_ATLAS` →
  `DISCORD_WEBHOOK_URL`. Add a test for each level.
- **Backward-compat:** legacy single-channel deployment (only
  `DISCORD_WEBHOOK_URL` set, no per-channel webhooks) still delivers cron
  output.
- **Backward-compat:** legacy `send_message.py "..."` (no flags, only
  `DISCORD_CHANNEL_ID`) still works.
- `session_archive.sh` archives multiple session dirs without
  `DISCORD_CHANNEL_ID` set.

### 9. Documentation

Update:

- `README.md` — configured channels, env vars, fallback chain, allowlist,
  channel-ID pinning, how to add/remove a channel.
- `.env.example` — new vars + legacy vars marked as fallback.
- `ROADMAP.md` — note multi-channel landed; flag deferred items (hard skill
  restriction, per-channel hooks/permissions).
- `CHANGELOG.md` — user-visible changes (new env vars, retired scripts).

### 10. Verification

```bash
ruff check .
pytest
```

Targeted while developing:

```bash
pytest tests/test_bot_commands.py
pytest tests/test_bot_sessions.py
pytest tests/test_dispatcher_execution.py
pytest tests/test_dispatcher_webhook.py
pytest tests/test_send_message.py
pytest tests/test_session_archive_script.py
```

Manual verification after deployment:

1. Send `help` in each configured channel — confirm response.
2. Send a normal unmentioned message in each configured channel — confirm response.
3. Send a normal unmentioned message in an unconfigured channel — confirm silence.
4. Mention ATLAS in an unconfigured channel — confirm response.
5. Run selected cron jobs with `--run-now` and confirm the message lands in
   the right channel.
6. Confirm `#health` medication reminders still support ✅ reaction logging.
7. Confirm `#briefings` gets summary/report jobs and not health/project noise.
8. Rename one Discord channel and confirm the channel-ID pin keeps the bot
   responding (only relevant if `ATLAS_CHANNEL_ID_*` is set for that channel).

## Rollout Order

To avoid breaking existing single-channel deployments mid-rollout, ship in
this sequence. Each step is independently deployable.

1. **Land `channel_configs.py` + dispatcher fallback chain.** No behavior
   change for existing deployments — `DISCORD_WEBHOOK_URL` is still the
   eventual fallback. Tests for the fallback chain land here.
2. **Update `cron/jobs.json` to use per-channel `url_env` values.** Without
   the new env vars set, every job falls through to `DISCORD_WEBHOOK_URL`, so
   single-channel deployments continue to work.
3. **Document new env vars in `.env.example` and `README.md`.** Admins (James)
   set the new webhook + channel-ID env vars in production `.env`.
4. **Switch `on_message` activation from name-equals-`atlas` to configured-
   channel detection.** This is the first user-visible behavior change.
   Verify in each channel manually.
5. **Rewrite `cron/session_archive.sh` to iterate session dirs.** Drop
   `DISCORD_CHANNEL_ID` requirement.
6. **Retire `cron/context_drift.sh` and `cron/task_triage.sh`.** They are
   already superseded by `jobs.json` entries.
7. **Update `send_message.py` with `--channel` / `--channel-id` flags.**
   Backward-compat for the positional form.

Steps 1–3 can ship in one PR; step 4 is its own PR; steps 5–7 can ship
together.

## Migration Notes

- Existing `sessions/<channel_id>/` dirs require no destructive migration.
  `prepare_session_dir` writes any missing metadata (`ATLAS-Channel-Role.md`,
  `ATLAS-Session.json`) on the next message in that channel.
- Existing `model.txt` files are honored as-is; only the **default** model
  shifts from hardcoded `"opus"` to `ChannelConfig.default_model` for new
  channels.
- Channels not declared in `CHANNEL_CONFIGS` retain mention-only behavior.
  No data is lost for ad-hoc channels.

## Open Decisions (resolved)

1. **Create `#atlas-dev` now?** Yes. Routing in §6 assumes it exists.
2. **`#briefings` strictly read-only?** No. Role-context guidance only in v1.
3. **`#atlas` keeps all skills?** Yes. Catch-all by design.
4. **Webhook fallback chain?** Per-channel → `DISCORD_WEBHOOK_ATLAS` →
   `DISCORD_WEBHOOK_URL`. Encoded in dispatcher (§6).
5. **Per-channel hooks/permissions?** Deferred. Identical across channels in
   v1; revisit if a channel needs hard restriction.
6. **Hard skill restriction?** Deferred. Soft hints via role context in v1.

## Definition of Done

- Configured channels auto-activate without mentioning the bot.
- Unconfigured channels remain quiet unless ATLAS is mentioned.
- Channel-specific role context is written to each session and surfaced via
  `SessionStart`.
- Default model per channel comes from `ChannelConfig`, not a hardcoded
  global.
- Cron jobs route to per-channel webhooks with documented fallback chain.
- Legacy single-channel deployments (`DISCORD_WEBHOOK_URL` only,
  `DISCORD_CHANNEL_ID` only) continue to work after upgrade.
- Adding or removing a configured channel requires only edits to
  `channel_configs.py` and `.env` — no other code changes.
- `cron/session_archive.sh` archives all configured session dirs without
  `DISCORD_CHANNEL_ID`.
- Legacy `cron/context_drift.sh` and `cron/task_triage.sh` are retired or
  documented as such.
- Tests cover activation, ID-vs-name resolution, allowlist, role context,
  cron routing, fallback chain, and backward-compat.
- README and `.env.example` document setup, fallback chain, and channel-ID
  pinning.
- `ruff check .` and `pytest` pass.
