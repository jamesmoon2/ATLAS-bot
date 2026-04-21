# Weekly Training Planner Skill

Plan and schedule the upcoming training week based on recovery data and program state.

## Instructions

1. **Get Current Date and Week** — Use the `**Current Time:**` value provided in the prompt as the authoritative reference for determining which training week is upcoming

2. **Fetch Recovery Data**

   - Use `mcp__oura__get_daily_sleep` for past 7 days
   - Use `mcp__oura__get_daily_readiness` for past 7 days
   - Use `mcp__oura__analyze_health_trends` for patterns
   - Use `mcp__whoop__get_daily_sleep` for past 7 days
   - Use `mcp__whoop__get_daily_recovery` for past 7 days
   - Use `mcp__whoop__get_daily_cycle` for past 7 days

3. **Read Current State**

   - Read `/home/jmooney/vault/Areas/Health/Training-State.md` for program phase, current week, completed sessions
   - Read recent workout logs from `/home/jmooney/vault/Areas/Health/Workout-Logs/` for performance trends
   - Analyze the last 2-4 comparable sessions for each planned strength movement (or the closest successful variant) using reps achieved, RPE, pain notes, swaps/skips, and recovery context
   - Pull working-weight baselines from those successful sessions plus the `Key Lifts` section in `Training-State.md`
   - Use the last successful logged load as a baseline input, not an automatic prescription
   - If a movement is not loaded with a number, label it explicitly as `BW` or `Band` rather than leaving the load blank

4. **Check Calendar**

   - Use the Google Calendar events search/list tool available in the active provider for the upcoming week
   - Identify conflicts or busy days

5. **Generate Training Plan**

   - Follow the program template from `/home/jmooney/vault/Areas/Health/Training-State.md`
   - Adjust based on recovery data
   - Account for calendar conflicts
   - For each strength movement, make an explicit coaching decision to progress, hold, or regress the load
   - Progress only when recent comparable sessions support it: target reps were achieved with acceptable effort, technique stayed clean, and no injury flag worsened
   - Hold when the trend is mixed, the progression was planned but not yet validated, or recovery suggests caution
   - Regress when recovery is poor, pain is elevated, technique degraded, or a deload / recovery week calls for backing off
   - Week 4 deloads should usually hold or slightly reduce loads while cutting volume; do not force progression during deloads unless the recent data makes underloading obvious
   - Preserve proven substitutions that better fit injury management, such as back hypers replacing RDLs when low-back tolerance is the limiter

6. **Create/Update Calendar Events**
   - Use the Google Calendar event creation tool available in the active provider for each workout
   - Include workout details in event description
   - For every strength session, include weights for every prescribed movement in the event description
   - Strength event loads must reflect the progression analysis above, not blind last-log copy; do not omit weights for any lifting movement
   - Add concise coach notes when the decision is meaningful, for example why a lift is holding steady, why a progression was deferred, or when a small regression is the right call
   - Use the Google Calendar event summary `Workout: [Type]`
   - Use `timezone_str` / event timezone `America/Los_Angeles` for every created workout event
   - Strength sessions use colorId `11` (red)
   - Cardio sessions use colorId `7` (cyan)
   - Saturday Mobility/Core/Rehab uses colorId `6` (orange)

## Output Format

```markdown
# Week [X] Training Plan ([date range])

## Recovery Assessment

| Metric         | 7-Day Avg | Trend | Status          |
| -------------- | --------- | ----- | --------------- |
| Sleep          | X         | ↑/↓/→ | Good/Fair/Poor  |
| Readiness      | X         | ↑/↓/→ | Good/Fair/Poor  |
| HRV            | X         | ↑/↓/→ | Normal/Low/High |
| WHOOP Recovery | X         | ↑/↓/→ | Good/Fair/Poor  |
| WHOOP Strain   | X         | ↑/↓/→ | Low/Normal/High |

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
- **Strength Description Rule:** Every lifting line must include sets/reps and a prescribed load, for example `DB Bench Press: 2 x 8-10 @ 90 lbs`, `Ring Pull-ups: 1-2 easy sets @ BW`, or `Band Face Pulls: 2 x 12-15 @ Band`
- **Strength Coach Notes:** Add 1-3 short bullets explaining the load decision when useful, such as `Hold row at 70 lbs because 80 was planned but never validated before deload week`

## Notes

- Do not ask the user for program details until after reading `/home/jmooney/vault/Areas/Health/Training-State.md`
- Don't schedule workouts on days with early conflicts
- Saturday is **Mobility, Core & Rehab**, not a rest day
- Week 4 is always deload (-30% volume)
- Sunday is the default rest day
- Never create a weightlifting calendar event with missing loads
- Treat strength load selection like a high-level coaching decision, not data transcription
- This is an unattended scheduled job: do not ask the user follow-up questions
