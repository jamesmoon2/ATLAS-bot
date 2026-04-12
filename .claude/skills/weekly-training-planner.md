# Weekly Training Planner Skill

Plan and schedule the upcoming training week based on recovery data and program state.

## Instructions

1. **Get Current Date and Week** — Determine which training week is upcoming

2. **Fetch Recovery Data**

   - Use `mcp__oura__get_daily_sleep` for past 7 days
   - Use `mcp__oura__get_daily_readiness` for past 7 days
   - Use `mcp__oura__analyze_health_trends` for patterns

3. **Read Current State**

   - Training-State.md for program phase, current week, completed sessions
   - Recent workout logs for performance trends

4. **Check Calendar**

   - Use `mcp__google-calendar__list-events` for the upcoming week
   - Identify conflicts or busy days

5. **Generate Training Plan**

   - Follow the program template from Training-State.md
   - Adjust based on recovery data
   - Account for calendar conflicts

6. **Create/Update Calendar Events**
   - Use `mcp__google-calendar__create-event` for each workout
   - Include workout details in event description

## Output Format

```markdown
# Week [X] Training Plan ([date range])

## Recovery Assessment

| Metric    | 7-Day Avg | Trend | Status          |
| --------- | --------- | ----- | --------------- |
| Sleep     | X         | ↑/↓/→ | Good/Fair/Poor  |
| Readiness | X         | ↑/↓/→ | Good/Fair/Poor  |
| HRV       | X         | ↑/↓/→ | Normal/Low/High |

**Assessment:** [1-2 sentences on recovery status]

## Scheduled Workouts

| Day | Date  | Workout | Time  | Notes |
| --- | ----- | ------- | ----- | ----- |
| Mon | MM/DD | [Type]  | HH:MM |       |
| Tue | MM/DD | [Type]  | HH:MM |       |
| ... |       |         |       |       |

## Adjustments

- [Any modifications based on recovery]
- [Calendar conflicts resolved]
- [Volume/intensity adjustments]

## Focus Areas

- [Priority 1 for this week]
- [Priority 2]

---

_Generated: [timestamp]_
```

## Calendar Event Format

- **Title:** `Workout: [Type]`
- **Time:** Default 5:40 AM - 6:40 AM (1 hour block)
- **Description:** Include exercise list and target RPE

## Notes

- Don't schedule workouts on days with early conflicts
- Week 4 is always deload (-30% volume)
- Respect rest days (Sat/Sun by default)
