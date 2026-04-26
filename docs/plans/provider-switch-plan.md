# Provider Switch Plan

## Goal

Add a provider switch so ATLAS can run on either Claude Code or Codex as the agent harness, while keeping bot behavior effectively identical from the Discord user's perspective.

The switch can be operational rather than conversational. A CLI or environment-variable toggle is acceptable.

## Success Criteria

- One configuration switch selects `claude` or `codex`.
- Discord behavior stays the same:
  - same prompts
  - same persistent context
  - same skills
  - same hooks or equivalent behavior
  - same channel session continuity
  - same attachment handling
- same cron job outputs
- Provider-specific implementation details do not leak into normal user interaction.
- Claude remains fully supported during the transition.
- Restoring the current working Claude setup is fast and low-risk.
- No migration phase requires destructive replacement of the current Claude path before Codex parity is proven.

## Rollback Requirement

Rollback is a hard requirement, not a nice-to-have.

The migration should be designed so that:

- Claude remains the default working provider until Codex has been validated.
- switching back to Claude requires only config rollback, not code archaeology
- existing Claude config, skills, prompts, and session behavior remain recoverable
- no phase leaves the repo in a state where Codex must work for ATLAS to function

## Rollback Strategy

### Baseline rule

Treat the current Claude-backed setup as the production baseline.

That means:

- `ATLAS_AGENT_PROVIDER=claude` remains the default until final cutover
- all refactors must preserve the Claude path first
- Codex support is additive until explicitly promoted

### Operational rollback target

The desired rollback path is:

1. set `ATLAS_AGENT_PROVIDER=claude`
2. restart bot and cron
3. ATLAS resumes using the existing Claude-backed implementation path

That rollback should not require:

- manual file reconstruction
- rebuilding skills by hand
- restoring deleted Claude config
- recovering from partially migrated session state

### Code rollback target

Each phase should be safe to revert by:

- one small commit revert
- or one isolated feature-flag change

Avoid large mixed commits that combine:

- provider abstraction
- session layout migration
- hook rewrites
- docs
- test renames

Those should land in separate commits so rollback is clean.

### Data rollback target

Do not delete or overwrite the current Claude-specific assets during early phases.

Preserve:

- repo-local `.claude/skills`
- current Claude settings generation logic
- current Claude session bootstrap behavior
- current vault prompt and context paths
- current shell scripts until replacements are proven

Any new generated Codex assets should be additive, not destructive.

## Deployment Safety Rules

### 1. Claude stays first-class during the whole migration

Do not create an intermediate state where Claude is "legacy" but Codex is not yet proven.

### 2. Provider switch must be feature-flagged

All runtime selection should be behind:

- `ATLAS_AGENT_PROVIDER`

Do not infer provider from machine state.

### 3. Preserve current Claude command path until final validation

Even after introducing a shared wrapper, the Claude adapter should produce the same effective subprocess behavior as today.

### 4. No destructive move of `.claude` assets early

If skills, hooks, or config are normalized, do it by generation or duplication first.

Do not remove the current Claude assets until:

- Codex parity is validated
- Claude still works from the new generated source
- rollback has been tested

### 5. Session migration must be backward-compatible

If session layout changes, the Claude adapter must still be able to operate against existing live channel sessions or recreate the expected Claude state automatically.

### 6. Cutover only after explicit validation

Do not flip the default provider to Codex until the validation checklist is complete.

## Current State

ATLAS is currently Claude-specific in multiple places, not just one subprocess call.

### Main integration points

- [bot.py](/home/jmooney/atlas-bot/bot.py:1)
  - creates per-channel `.claude/settings.json`
  - creates per-channel `.claude/settings.local.json`
  - symlinks `.claude/skills`
  - runs `claude --continue` for chat sessions
  - stores per-channel model in `model.txt`
- [cron/dispatcher.py](/home/jmooney/atlas-bot/cron/dispatcher.py:1)
  - runs `claude --print`
  - passes Claude-style `allowedTools`
- [cron/task_triage.sh](/home/jmooney/atlas-bot/cron/task_triage.sh:1)
  - calls `claude` directly
- [cron/context_drift.sh](/home/jmooney/atlas-bot/cron/context_drift.sh:1)
  - calls `claude` directly
- [cron/session_archive.sh](/home/jmooney/atlas-bot/cron/session_archive.sh:1)
  - archives and clears `~/.claude/projects`

### Prompt, context, skills, and hooks

- System prompt path is [vault/System/claude.md](/home/jmooney/vault/System/claude.md:1)
- Persistent runtime context is [vault/System/ATLAS-Context.md](/home/jmooney/vault/System/ATLAS-Context.md:1)
- Claude skills live in [/home/jmooney/atlas-bot/.claude/skills](/home/jmooney/atlas-bot/.claude/skills)
- Session hook wiring is embedded in [bot.py](/home/jmooney/atlas-bot/bot.py:98)
- Cron Claude permissions live in [cron/.claude/settings.local.json](/home/jmooney/atlas-bot/cron/.claude/settings.local.json:1)

### Tests tied to Claude assumptions

- [tests/test_bot_claude.py](/home/jmooney/atlas-bot/tests/test_bot_claude.py:1)
- [tests/test_bot_sessions.py](/home/jmooney/atlas-bot/tests/test_bot_sessions.py:1)
- [tests/test_dispatcher_execution.py](/home/jmooney/atlas-bot/tests/test_dispatcher_execution.py:1)
- [tests/test_bot_model.py](/home/jmooney/atlas-bot/tests/test_bot_model.py:1)

## Key Constraint

The implementation should preserve ATLAS behavior, not just add a second CLI.

That means the correct abstraction boundary is:

- ATLAS behavior is canonical
- Claude and Codex are adapters behind that behavior

Not:

- duplicate one Claude implementation
- duplicate one Codex implementation
- try to keep them manually in sync

## Important Capability Findings

### Claude

Claude already matches the current implementation model:

- per-directory session persistence
- `.claude` settings
- repo-local `.claude/skills`
- session hooks
- `--continue`

### Codex

Codex has the core pieces needed for parity:

- non-interactive execution via `codex exec`
- non-interactive resume via `codex exec resume`
- `AGENTS.md`-based instruction loading
- repo-scoped skills under `.agents/skills`
- hooks via `.codex/hooks.json`
- MCP server config via `.codex/config.toml`

But Codex does not match Claude one-to-one.

Most importantly:

- Codex native `PreToolUse` and `PostToolUse` currently only support `Bash` interception.
- They do not natively intercept MCP calls, `Write`, or other non-Bash tools the way the current Claude workflow expects.

That is the main parity problem.

## Design Decision

Build a provider-neutral ATLAS runner and move any behavior that cannot be expressed in both harnesses into ATLAS-owned orchestration.

## Proposed Architecture

### 1. Introduce a provider abstraction

Add a shared execution layer, for example:

- `agent_runner.py`
- `providers/base.py`
- `providers/claude.py`
- `providers/codex.py`

Minimum interface:

- `ensure_session(channel_id) -> session metadata`
- `run_message(channel_id, prompt, attachments) -> response`
- `run_job(job) -> (output, success)`
- `reset_session(channel_id) -> bool`
- `archive_session(channel_id) -> archive metadata`

Everything that currently shells out to `claude` should go through this layer.

### 2. Add one explicit provider switch

Use a single operational setting:

- `ATLAS_AGENT_PROVIDER=claude`
- `ATLAS_AGENT_PROVIDER=codex`

Recommended UX:

- change env var
- restart bot and cron service

Do not expose provider switching as a Discord command.

### 3. Define one canonical instruction bundle

Today the prompt lives in `claude.md`, but the content is mostly provider-neutral.

Canonical ATLAS instruction sources should be:

- system prompt
- persistent context
- generated session context
- skills

Provider adapters should render those into the provider-specific format they need.

### 4. Generate provider-specific assets instead of maintaining both by hand

Do not hand-maintain:

- `.claude/skills/*.md`
- `.agents/skills/*/SKILL.md`

in parallel.

Instead:

- create one canonical ATLAS skill source format
- generate Claude skill files
- generate Codex skill directories

Same principle for:

- session config
- hooks config
- MCP config
- instruction files

### 5. Isolate provider-private state from ATLAS session state

ATLAS should own:

- per-channel session directories
- attachments
- provider selection
- model/profile selection
- ATLAS-visible session metadata

Harness-private state such as `~/.claude/projects` or `~/.codex/sessions` should be treated as implementation detail, not as the canonical source of session truth.

## Implementation Plan

### Phase 1: Centralize execution

Replace direct `claude` usage everywhere with a single ATLAS wrapper.

Targets:

- [bot.py](/home/jmooney/atlas-bot/bot.py:365)
- [cron/dispatcher.py](/home/jmooney/atlas-bot/cron/dispatcher.py:157)
- [cron/task_triage.sh](/home/jmooney/atlas-bot/cron/task_triage.sh:69)
- [cron/context_drift.sh](/home/jmooney/atlas-bot/cron/context_drift.sh:68)

Deliverables:

- provider selection env var
- centralized subprocess construction
- Claude adapter preserving current behavior exactly

This phase should be behavior-preserving.

Rollback expectation:

- if anything breaks, the wrapper still routes to Claude exactly as before
- reverting this phase should be one small commit
- no existing `.claude` assets are removed in this phase

### Phase 2: Normalize session management

Move from Claude-specific session bootstrapping to provider-aware session bootstrapping.

Current Claude session contents:

- `.claude/settings.json`
- `.claude/settings.local.json`
- `.claude/skills` symlink
- `model.txt`
- attachments

Target:

- session directory contains provider-neutral ATLAS metadata
- provider-specific config is generated into subdirectories as needed

Example shape:

```text
sessions/{channel_id}/
├── atlas/
│   ├── session.json
│   ├── provider.txt
│   ├── model.txt
│   └── generated/
├── claude/
│   └── .claude/...
├── codex/
│   └── .codex/...
└── attachments/
```

The exact directory layout can vary, but the key point is to stop letting `.claude` define the session model.

Rollback expectation:

- existing Claude session bootstrapping still works
- old session directories remain usable or are auto-translated
- no data migration should be one-way only

### Phase 3: Create a Codex adapter

Implement Codex-backed chat sessions using:

- first message: `codex exec`
- subsequent messages: `codex exec resume --last`

Run from the per-channel session directory so resume selection stays scoped correctly.

Codex adapter responsibilities:

- set bot-specific `CODEX_HOME`
- pass bot-scoped config and hooks
- load repo/bot MCP config
- write final response to stdout in a stable form

Rollback expectation:

- this phase is additive only
- Claude remains the default provider
- disabling Codex should not require code changes beyond config

### Phase 4: Isolate Codex from the user's personal environment

This is required.

The machine already has a populated `~/.codex` with:

- user config
- plugins
- personal sessions
- global skills

The bot should not inherit that implicitly.

Recommended approach:

- use a dedicated bot `CODEX_HOME`
- generate a bot-scoped `.codex/config.toml`
- explicitly set trust, hooks, MCP servers, and profiles there

This prevents surprising drift between ATLAS behavior and the operator's personal Codex setup.

Rollback expectation:

- Codex isolation changes do not affect Claude at all
- removing the dedicated `CODEX_HOME` should not change the Claude path

### Phase 5: Convert hooks to provider-neutral behavior

This is the hardest part.

#### Current hook-dependent features

- SessionStart context injection
- PreToolUse calendar date injection before Google Calendar create/update
- PostToolUse workout/Oura checklist after workout log writes

#### SessionStart

This ports cleanly.

Codex supports `SessionStart`, and hook output can add extra developer context.

#### PreToolUse calendar hook

Current Claude behavior:

- inject date guardrails specifically before calendar tool usage

Codex limitation:

- native `PreToolUse` only supports `Bash`

Recommended replacement:

- move date guardrail injection into ATLAS-owned prompt augmentation
- automatically prepend calendar date context when:
  - relevant calendar skills run
  - prompts clearly target calendar scheduling

This preserves behavior without depending on unsupported native hook coverage.

#### PostToolUse workout hook

Current Claude behavior:

- after writing a workout log, inject a structured reminder to fetch Oura data and update training state

Codex limitation:

- native `PostToolUse` only supports `Bash`

Recommended replacement:

- move this behavior into the workout-related skills themselves
- optionally add ATLAS-side follow-up logic when workout log writes are part of the requested workflow

Again, preserve the behavior at the ATLAS layer rather than depending on a provider feature mismatch.

Rollback expectation:

- Claude-native hook behavior should remain available until the ATLAS-owned replacement has been validated
- do not remove the old Claude hook path before proving the replacement works

### Phase 6: Make attachment handling provider-neutral

Current implementation saves files locally and tells the agent to use the Read tool.

That is fragile across providers.

Recommended approach:

- keep local attachment downloads
- for images:
  - pass native image inputs where supported
- for PDFs:
  - extract text or produce a sidecar text representation before invocation
- update prompt construction to describe attachments in an ATLAS-owned format, not a provider-specific one

This avoids relying on undocumented provider differences for PDF handling.

Rollback expectation:

- if the new attachment pipeline misbehaves, Claude can still fall back to the current local-file workflow
- do not remove existing attachment download behavior until replacement is proven

### Phase 7: Map MCP configuration explicitly

Do not depend on the operator's global config.

Create bot-scoped MCP configuration for both providers with consistent server names and tool identities.

Targets include:

- Google Calendar
- Gmail
- Oura
- Weather
- Garmin if applicable

Requirement:

- the same ATLAS prompt or skill should refer to the same tool names regardless of provider

If tool names differ, ATLAS must normalize them in generated config or generated skill text.

Rollback expectation:

- Claude MCP behavior must continue to work from repo-controlled config
- Codex MCP config should be additive, not a replacement for the Claude path

### Phase 8: Refactor archive and reset

Current reset/archive logic is Claude-specific because it manages:

- local session directory
- `~/.claude/projects`

Target behavior:

- reset means ATLAS starts a fresh conversation for that channel
- archive means ATLAS stores enough local metadata to preserve traceability

Provider-private history cleanup should be best-effort, not the definition of reset.

Recommended:

- archive ATLAS-managed session data
- archive provider-generated config used for the session
- optionally archive provider-private history if easy and safe
- do not make correctness depend on provider-private disk layout

Rollback expectation:

- keep the current Claude archive/reset path intact until the new ATLAS-owned path is validated
- do not stop archiving Claude session artifacts until replacement behavior is confirmed

### Phase 9: Update user-facing commands carefully

`!model` is currently Claude-oriented:

- valid values are `sonnet` and `opus`

This is a potential UX leak.

Options:

1. Keep it temporarily for compatibility and accept that advanced users can infer the harness.
2. Replace it with ATLAS profiles later, for example:
   - `!mode fast`
   - `!mode balanced`
   - `!mode deep`

Recommendation:

- keep current behavior during initial provider work
- plan a second pass to make model selection provider-neutral

### Phase 10: Update tests

Refactor the test suite so shared behavior is provider-neutral and subprocess construction is provider-specific.

Recommended changes:

- rename Claude-specific tests around shared behavior
- add adapter-level tests for:
  - Claude command construction
  - Codex command construction
  - session resume behavior
  - provider switching
  - hook/context generation
  - reset/archive semantics

High-value coverage:

- `bot.on_message()` behavior unchanged across providers
- dispatcher behavior unchanged across providers
- generated prompt/context parity
- skills resolve to equivalent outputs/instructions

## Risks

### 1. Hook parity is not native

This is the main technical risk.

Mitigation:

- move non-portable hook behavior into ATLAS-owned orchestration

### 2. Skill duplication drift

Maintaining `.claude/skills` and `.agents/skills` separately will drift quickly.

Mitigation:

- generate both from one source

### 3. Personal Codex config contamination

The operator's existing `~/.codex` can change behavior in ways Discord users should not see.

Mitigation:

- dedicated bot `CODEX_HOME`

### 4. MCP naming mismatch

If the same external server exposes different tool identifiers across harnesses, prompts and skills will diverge.

Mitigation:

- normalize tool naming in generated config or generated skill content

### 5. Attachment behavior mismatch

PDF and file handling may differ materially.

Mitigation:

- pre-process attachments in ATLAS instead of relying on provider magic

### 6. Reset semantics regress

If reset still depends on provider-private storage, behavior will diverge.

Mitigation:

- define reset in ATLAS terms, not provider-private terms

## Recommended File Changes

Likely additions:

- `agent_runner.py`
- `providers/base.py`
- `providers/claude.py`
- `providers/codex.py`
- `scripts/atlas-agent`
- `.codex/config.toml` or generated equivalent
- `.codex/hooks.json` or generated equivalent
- `.agents/skills/...`
- shared canonical skill source directory
- provider-neutral session metadata files

Likely edits:

- [bot.py](/home/jmooney/atlas-bot/bot.py:1)
- [cron/dispatcher.py](/home/jmooney/atlas-bot/cron/dispatcher.py:1)
- [cron/task_triage.sh](/home/jmooney/atlas-bot/cron/task_triage.sh:1)
- [cron/context_drift.sh](/home/jmooney/atlas-bot/cron/context_drift.sh:1)
- [cron/session_archive.sh](/home/jmooney/atlas-bot/cron/session_archive.sh:1)
- [.env.example](/home/jmooney/atlas-bot/.env.example:1)
- [README.md](/home/jmooney/atlas-bot/README.md:1)
- [SECURITY.md](/home/jmooney/atlas-bot/SECURITY.md:1)
- tests under [/home/jmooney/atlas-bot/tests](/home/jmooney/atlas-bot/tests)

## Rollout Strategy

### Step 1

Refactor to a provider abstraction but keep Claude as the only active backend.

### Step 2

Add Codex backend behind an env flag.

### Step 3

Run the same ATLAS workflows on both providers:

- normal chat message
- librarian command
- attachment workflow
- workout logging flow
- calendar scheduling flow
- cron prompt job
- cron direct-script job
- reset
- archive

### Step 4

Only after parity is acceptable, allow Codex in production use.

## Rollback Plan

### Fast rollback

If any migration step breaks the working setup:

1. set `ATLAS_AGENT_PROVIDER=claude`
2. restart bot
3. restart cron dispatcher environment
4. verify:
   - normal chat message works
   - `!librarian` works
   - one cron prompt job works
   - `!reset` works

This should restore service without code rollback.

### Hard rollback

If the code itself is unstable:

1. revert the most recent migration commit
2. leave provider set to `claude`
3. restart bot and cron
4. rerun the same smoke checks

This is why migration work should land in small isolated commits.

### Rollback smoke test checklist

- send a normal message in `#atlas`
- run `!help`
- run `!librarian`
- test one attachment flow
- test one cron job with `--run-now`
- test `!reset`

### What must remain restorable at all times

- current Claude subprocess behavior
- current repo-local `.claude/skills`
- current session-start context behavior
- current cron prompt jobs
- current shell-script Claude jobs
- current archive/reset behavior

If any phase would make one of those non-restorable, the phase design is wrong.

## Acceptance Checklist

- Switching `ATLAS_AGENT_PROVIDER` changes the backend without code edits.
- `bot.py` no longer shells out directly to `claude`.
- `cron/dispatcher.py` no longer shells out directly to `claude`.
- helper shell scripts no longer shell out directly to `claude`.
- system prompt and context are loaded through one canonical path.
- skills are generated from one canonical source.
- session reset no longer depends on Claude-only disk layout.
- Codex uses a bot-scoped configuration, not the operator's personal one.
- Discord-visible behavior stays stable.
- rollback to Claude is documented and tested.
- restoring the current working setup does not require reconstructing deleted Claude assets.

## Open Questions

### 1. Switching mechanism

Is an environment-variable switch plus service restart the intended operational model?

Recommended answer: yes.

### 2. User-visible model command

Should `!model sonnet|opus` remain exactly as-is?

If yes, model-family differences remain visible to advanced users.

Recommended answer: keep short-term, replace later with provider-neutral profiles.

### 3. Codex environment isolation

Should the bot use a dedicated bot-scoped Codex home/config/auth setup?

Recommended answer: yes.

## Reference Notes

Relevant source docs used for this plan:

- Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- Codex Skills: https://developers.openai.com/codex/skills
- Codex Hooks: https://developers.openai.com/codex/hooks
- Codex MCP: https://developers.openai.com/codex/mcp
- Codex Non-interactive mode: https://developers.openai.com/codex/noninteractive
- Codex CLI reference: https://developers.openai.com/codex/cli/reference
- Codex config reference: https://developers.openai.com/codex/config-reference

Installed local versions observed during analysis:

- Claude Code `2.1.96`
- Codex CLI `0.120.0`
