# Second Brain Librarian Spec

## Goal

Turn ATLAS into an active librarian for the vault, not just a chat interface over it.

The librarian should:

- maintain a lightweight, queryable map of the vault
- surface orphaned, stale, and unresolved notes
- suggest links, synthesis targets, and cleanup work
- make note recall and open-loop review fast from Discord

## Product Outcomes

After this ships, the user should be able to:

- ask "what changed in my notes this week?"
- ask "what open loops am I carrying?"
- ask "what notes are orphaned or going stale?"
- get periodic librarian digests without noise
- trust that ATLAS has a current view of the vault structure

## Scope

### In Scope

- vault indexing
- librarian digest job
- note-quality heuristics
- Discord recall commands
- session hook for a small librarian context block

### Out of Scope

- semantic vector search
- full-text search service
- automatic file renames or large-scale vault rewrites
- fully autonomous note editing without explicit user review

## Architecture

### 1. Vault Index Builder

Add a Python indexer that scans the vault and writes both machine-readable and human-readable outputs.

**New file**

- `cron/vault_index.py`

**Inputs**

- `VAULT_PATH`
- markdown files under the vault

**Exclusions**

- `.obsidian/`
- `Archive/`
- `Templates/`
- generated system files such as existing index outputs

**Outputs**

- `{vault_path}/System/vault-index.json`
- `{vault_path}/System/vault-index.md`

### 2. Librarian Review Skill

Add a skill that reads the index plus recent notes and produces a concise digest.

**New file**

- `.claude/skills/second-brain-librarian.md`

**Inputs**

- `vault-index.json`
- recent daily notes
- recent weekly reviews
- selected project notes
- `ATLAS-Context.md`

**Output sections**

- Orphan Notes
- Open Loops
- Stale But Active Notes
- Link Opportunities
- Synthesis Candidates
- Recommended Next Actions

### 3. Librarian Cron Jobs

Add two jobs:

- `vault_index_refresh`
- `librarian_digest`

**Index refresh**

- cadence: daily at 2:15 AM Pacific
- implementation: shell command running `python3 {bot_dir}/cron/vault_index.py`
- notify: silent on success, webhook on failure

**Librarian digest**

- cadence: Monday and Friday at 7:45 AM Pacific
- model: `sonnet`
- allowed tools: `Read`, `Skill`, `Glob`
- notify: webhook
- target channel: current default webhook channel

### 4. Discord Recall Commands

Add explicit librarian commands to the bot.

**Initial commands**

- `!recall <query>`
- `!open-loops`
- `!recent-notes`
- `!orphan-notes`
- `!librarian`

These should not bypass Claude. They should wrap prompt templates that steer Claude against the index and relevant note files.

### 5. Session Context Hook

Add a small hook that injects a compact librarian snapshot at session start.

**New file**

- `hooks/librarian_context.sh`

**Hook output**

- 5 most recent notes
- 5 open loops
- 5 stale notes needing attention

Keep it brief. This is support context, not a full report.

## Index Schema

`vault-index.json` should contain one object per note.

```json
{
  "generated_at": "2026-04-12T00:00:00Z",
  "vault_path": "/path/to/vault",
  "notes": [
    {
      "path": "Projects/ATLAS/Plan.md",
      "title": "ATLAS Plan",
      "folder": "Projects/ATLAS",
      "tags": ["atlas", "planning"],
      "wikilinks_out": ["Decision-Log", "Roadmap"],
      "wikilinks_in_count": 3,
      "task_open_count": 4,
      "decision_count": 1,
      "word_count": 842,
      "last_modified": "2026-04-11T19:12:00Z",
      "created_at": "2026-03-01T12:10:00Z",
      "summary": "Planning note for ATLAS architecture and feature sequencing.",
      "status": {
        "is_orphan": false,
        "is_stale": false,
        "has_open_loops": true,
        "needs_review": true
      }
    }
  ]
}
```

## Heuristics

The first version should stay deterministic and cheap.

### Orphan Note

A note is orphaned if all are true:

- `wikilinks_in_count == 0`
- not in `Daily/`
- not in `Inbox/`
- not created in the last 7 days

### Stale Note

A note is stale if:

- last modified more than 30 days ago
- and it still has open tasks, unresolved decisions, or belongs to an active project area

### Open Loop

Count as an open loop if any of these are present:

- unchecked markdown tasks
- heading named `Open Questions`, `Unresolved`, or `Next Actions`
- heading named `Waiting On` or `TBD`
- strings like `TODO`, `TBD`, `follow up`, `waiting on`

### Link Opportunity

Suggest a link when:

- two notes share 2 or more uncommon tags or wikilinks
- or a recent note references a project/entity that exists elsewhere but is not linked

### Synthesis Candidate

Suggest synthesis when:

- 3 or more recent notes touch the same project/topic within 14 days
- or there are multiple fragmented notes under the same folder with overlapping tags

## Concrete File Changes

### New Files

- `SECOND_BRAIN_LIBRARIAN_SPEC.md`
- `cron/vault_index.py`
- `hooks/librarian_context.sh`
- `.claude/skills/second-brain-librarian.md`
- `tests/test_vault_index.py`
- `tests/test_bot_librarian_commands.py`

### Modified Files

- `bot.py`
- `cron/jobs.json`
- `README.md`
- `CHANGELOG.md`

## `bot.py` Changes

### New command routing

Extend command handling to support:

- `!recall <query>`
- `!open-loops`
- `!recent-notes`
- `!orphan-notes`
- `!librarian`

### Prompt templates

Use a small helper instead of inlining prompt strings in `on_message()`.

Recommended new helper:

- `build_librarian_prompt(command: str, args: str) -> str`

### Help text

Update `!help` output to include the new librarian commands.

## `cron/jobs.json` Additions

### `vault_index_refresh`

```json
{
  "id": "vault_index_refresh",
  "name": "Vault Index Refresh",
  "schedule": "15 2 * * *",
  "timezone": "America/Los_Angeles",
  "enabled": true,
  "command": "python3 {bot_dir}/cron/vault_index.py",
  "notify": {
    "type": "silent"
  }
}
```

### `librarian_digest`

```json
{
  "id": "librarian_digest",
  "name": "Second Brain Librarian",
  "schedule": "45 7 * * 1,5",
  "timezone": "America/Los_Angeles",
  "enabled": true,
  "model": "sonnet",
  "timeout_seconds": 180,
  "allowed_tools": ["Read", "Glob", "Skill"],
  "prompt": "Run the second-brain-librarian skill using the latest vault index and recent notes.",
  "notify": {
    "type": "webhook",
    "url_env": "DISCORD_WEBHOOK_URL",
    "username": "ATLAS Librarian"
  }
}
```

## `vault_index.py` Behavior

### Responsibilities

- walk the vault
- parse markdown files
- collect note metadata
- build backlink counts
- compute deterministic note health flags
- emit JSON and Markdown outputs atomically

### Parsing Rules

- title: first H1, else filename stem
- tags: frontmatter tags plus inline `#tags`
- outgoing wikilinks: `[[Note]]` and `[[Note|Alias]]`
- open tasks: lines matching `- [ ]`
- decisions: headings or bullets under `Decisions`

### Markdown Output

`vault-index.md` should be optimized for human scanning.

Recommended sections:

- Index Summary
- Recent Notes
- Orphan Notes
- Stale Notes
- Notes With Open Loops
- Top Linked Notes

## Hook Design

`hooks/librarian_context.sh` should read `vault-index.json` and emit a short summary.

Example:

```markdown
## Librarian Snapshot

**Recent Notes**

- Projects/ATLAS/Plan.md
- Daily/2026-04-12.md

**Open Loops**

- Projects/Finances/Budget.md (3 tasks)
- Areas/Health/Training-State.md (2 tasks)

**Needs Review**

- Projects/Old-Idea/Notes.md (42 days stale, 1 open task)
```

If the index is missing, print a one-line fallback and exit cleanly.

## Testing Plan

### Unit Tests

Add tests for:

- title extraction
- tag extraction
- wikilink extraction
- backlink counting
- orphan detection
- stale detection
- open-loop detection
- markdown and JSON output generation

### Bot Tests

Add tests that:

- `!recall foo` routes to Claude with a recall-oriented prompt
- `!open-loops` and `!orphan-notes` return command-specific prompts
- `!help` includes librarian commands

### Integration Checks

Run:

- `pytest tests/test_bot_sessions.py tests/test_vault_index.py tests/test_bot_librarian_commands.py`
- `ruff check bot.py cron/vault_index.py tests`

## Implementation Order

### Phase 1

- land `vault_index.py`
- write `vault-index.json` and `vault-index.md`
- add unit tests

### Phase 2

- add librarian skill
- add `librarian_digest` cron job
- add `hooks/librarian_context.sh`

### Phase 3

- add Discord commands
- update help text
- add bot tests

### Phase 4

- refine heuristics based on real vault data
- evaluate whether the twice-weekly digest cadence should move up, down, or become hybrid

## Risks

- heuristic false positives on orphan or stale notes
- prompt bloat if hook output is too large
- noisy digests if cadence is too frequent
- vault-specific conventions varying more than expected

## Success Criteria

- ATLAS can answer note-recall questions faster and more consistently
- the user gets useful librarian digests without notification fatigue
- orphan notes and open loops become visible within one week of use
- no background job edits user content except generated index files
