# Weekly Training Planner Skill

Plan and schedule the upcoming training week based on recovery data and program state.

## Instructions

1. **Get Current Date and Week** — Use the `**Current Time:**` value provided in the prompt as the authoritative reference for determining which training week is upcoming

2. **Fetch Recovery Data**

   - Use `mcp__oura__get_daily_sleep` for past 7 days
   - Use `mcp__oura__get_daily_readiness` for past 7 days
   - Use `mcp__oura__analyze_health_trends` for patterns

3. **Read Current State**

   - Read `/home/jmooney/vault/Areas/Health/Training-State.md` for program phase, current week, completed sessions
   - Read recent workout logs from `/home/jmooney/vault/Areas/Health/Workout-Logs/` for performance trends

4. **Check Calendar**

   - Use `mcp__google-calendar__list-events` for the upcoming week
   - Identify conflicts or busy days

5. **Generate Training Plan**

   - Follow the program template from `/home/jmooney/vault/Areas/Health/Training-State.md`
   - Adjust based on recovery data
   - Account for calendar conflicts

6. **Create/Update Calendar Events**
   - Use `mcp__google-calendar__create-event` for each workout
   - Include workout details in event description
   - Use the Google Calendar event summary `Workout: [Type]`
   - Use `timezone_str` / event timezone `America/Los_Angeles` for every created workout event
   - Strength sessions use colorId `11` (red)
   - Cardio sessions use colorId `7` (cyan)
   - Saturday Mobility/Core/Rehab uses colorId `6` (orange)

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

- **Summary:** `Workout: [Type]`
- **Strength Time:** Default 5:40 AM - 6:40 AM
- **Cardio Time:** Default 5:40 AM - 6:20 AM
- **Saturday Mobility/Core/Rehab:** 8:00 AM - 8:45 AM
- **Timezone:** `America/Los_Angeles`
- **Description:** Include exercise list and target RPE

## Notes

- Do not ask the user for program details until after reading `/home/jmooney/vault/Areas/Health/Training-State.md`
- Don't schedule workouts on days with early conflicts
- Saturday is **Mobility, Core & Rehab**, not a rest day
- Week 4 is always deload (-30% volume)
- Sunday is the default rest day
