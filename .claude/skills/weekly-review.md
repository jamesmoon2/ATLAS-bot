# Weekly Review Skill

Generate a comprehensive weekly review of training, health, and progress.

## Instructions

1. **Determine Date Range** — Use the `**Current Time:**` value provided in the prompt as the
   authoritative reference, then review the last 7 days ending on that date

2. **Fetch Health Data for the Week**

   - Use `mcp__oura__get_daily_sleep` with start_date and end_date for 7 days
   - Use `mcp__oura__get_daily_readiness` with start_date and end_date for 7 days
   - Use `mcp__oura__get_daily_activity` with start_date and end_date for 7 days
   - Use `mcp__whoop__get_daily_sleep` with start_date and end_date for 7 days
   - Use `mcp__whoop__get_daily_recovery` with start_date and end_date for 7 days
   - Use `mcp__whoop__get_daily_cycle` with start_date and end_date for 7 days

3. **Read Vault Files**

   - Read `/home/jmooney/vault/Areas/Health/Training-State.md` for workout completion
   - Read `/home/jmooney/vault/Areas/Health/Workout-Logs/` for any logged sessions
   - Read `/home/jmooney/vault/Areas/Health/Medications.md` for adherence
   - Read relevant daily notes from `/home/jmooney/vault/Daily/` if they exist

4. **Generate Weekly Review**

## Output Format

```markdown
# Weekly Review — Week [X] ([date range])

## Training Summary

| Day | Scheduled | Completed | Notes        |
| --- | --------- | --------- | ------------ |
| Mon | [workout] | ✅/❌     | [brief note] |
| Tue | [workout] | ✅/❌     |              |
| ... |           |           |              |

**Completion Rate:** X/Y sessions (Z%)

## Health Metrics

| Metric         | Week Avg | Trend | Notes |
| -------------- | -------- | ----- | ----- |
| Sleep Score    | X        | ↑/↓/→ |       |
| Readiness      | X        | ↑/↓/→ |       |
| HRV Balance    | X        | ↑/↓/→ |       |
| Activity Score | X        | ↑/↓/→ |       |
| WHOOP Sleep    | X        | ↑/↓/→ |       |
| WHOOP Recovery | X        | ↑/↓/→ |       |
| WHOOP Strain   | X        | ↑/↓/→ |       |

## Progress Markers

- **Weight:** [if tracked]
- **Key Lifts:** [any progressions]
- **Cardio:** [any improvements]

## Medication Adherence

| Medication | Scheduled | Taken   | Notes |
| ---------- | --------- | ------- | ----- |
| [med]      | X doses   | Y doses |       |

## Observations

- [Key observation 1]
- [Key observation 2]
- [Pattern noticed]

## Next Week Focus

- [Priority 1]
- [Priority 2]
- [Adjustment if needed]

---

_Generated: [timestamp]_
```

## Notes

- Write to `/home/jmooney/vault/Daily/[YYYY]-W[XX]-weekly-review.md`
- Calculate averages and trends from the data
- Be specific about what went well and what needs adjustment
- Connect training load to recovery metrics
- This is an unattended scheduled job: do not ask the user follow-up questions
