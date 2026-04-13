# Second Brain Librarian Skill

Use the vault index to keep ATLAS acting like a second-brain librarian instead of a generic chat assistant.

## Goals

- identify the most important recent note changes
- surface unresolved work and waiting states
- find orphan and stale notes worth cleanup
- suggest where synthesis or cross-linking would create leverage

## Primary Inputs

1. Read `/home/jmooney/vault/System/vault-index.json` first
2. Read `/home/jmooney/vault/System/vault-index.md` for a human-readable overview if useful
3. Read any recent or relevant notes needed to confirm the index
4. Use `Glob` only to locate note families if the index is insufficient

## Working Rules

- treat `vault-index.json` as the primary map of the vault
- do not rewrite user notes unless explicitly asked
- prefer high-signal triage over exhaustive inventories
- when suggesting cleanup, be specific about why the note matters
- if a heuristic looks weak, say so instead of over-claiming

## Digest Structure

```markdown
# Second Brain Librarian

## Recent Notes

- [path] — why it matters

## Open Loops

- [path] — unresolved task, waiting state, or next action

## Orphan Notes

- [path] — why it should be linked, merged, or ignored

## Stale Notes

- [path] — why it still deserves attention

## Link Opportunities

- [note A] ↔ [note B] — suggested connection

## Recommended Actions

1. [highest-value cleanup or synthesis step]
2. [next step]
3. [next step]
```

## Quality Bar

- keep the output concise enough to read on a train
- highlight only the highest-leverage items
- distinguish urgent from merely useful
- avoid repeating the raw index unless it adds interpretation
- This is an unattended scheduled job: do not ask the user follow-up questions
