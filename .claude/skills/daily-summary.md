# Daily Summary Skill

Generate an end-of-day summary of activities, health metrics, and session context.

## Instructions

1. **Get Current Date** — Determine today's date for the summary

2. **Fetch Health Data**

   - Steps, calories, active minutes from activity data
   - Sleep score (from last night)
   - Training readiness
   - HRV, body battery, stress
   - Any workouts completed today

3. **Review Session Context**

   - Tasks created during the day
   - Decisions made
   - Files modified
   - Conversations/topics covered
   - Unresolved items

4. **Generate Summary**

## Output Format

```markdown
# ATLAS Session Summary

**Date:** [YYYY-MM-DD] ([Day of week])

## Tasks Created

- [Task 1]
- [Task 2]
- None today

## Decisions

- **[Decision title]:** [Brief description]
- None today

## Files Modified

- `[file path]` — [what changed]

## Conversations

- **[Topic]:** [Brief summary]

## Unresolved

- **[Item]:** [Status/context]

## Health Snapshot

| Metric             | Value    | Status         |
| ------------------ | -------- | -------------- |
| Steps              | X / goal | Met/Not met    |
| Sleep Score        | X        | Good/Fair/Poor |
| Training Readiness | X/100    | Level          |
| HRV                | Xms      | Status         |
| Body Battery       | X→Y      | Trend          |
| Activities         | [type]   | Duration       |

## Activity Summary (if workout)

**[Workout Type]**
| Metric | Value |
|--------|-------|
| Duration | X:XX |
| Avg HR | X bpm |
| Training Load | X |

---

_Generated: [timestamp]_
```

## Notes

- Write summary to `/home/jmooney/vault/Daily/[YYYY-MM-DD]-atlas-summary.md`
- Keep health snapshot concise — key metrics only
- Unresolved section helps maintain continuity across sessions
