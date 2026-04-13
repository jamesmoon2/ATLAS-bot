# Log Workout Skill

Log a completed workout with Garmin data and update `/home/jmooney/vault/Areas/Health/Training-State.md`.

## Instructions

1. **Get Today's Date** — Determine the workout date

2. **Fetch Garmin Activity Data**

   - Use `mcp__garmin__get_activities_fordate` with today's date
   - Use `mcp__garmin__get_activity` with the activity_id for full details
   - Extract: duration, avg HR, max HR, calories, training effect, training load, body battery impact

3. **Read `/home/jmooney/vault/Areas/Health/Training-State.md`** — Get the scheduled workout details:

   - What exercises were planned
   - Target sets/reps/weights
   - Any modifications or cautions

4. **Create Workout Log** at `/home/jmooney/vault/Areas/Health/Workout-Logs/[YYYY-MM-DD].md`

5. **Update `/home/jmooney/vault/Areas/Health/Training-State.md`** — Mark the session complete with ✅ and date

## Workout Log Format

```markdown
# Workout Log — [YYYY-MM-DD]

## Session Info

- **Type:** [Workout name from Training-State]
- **Week:** [X] of 4
- **Day:** [Day of week]
- **Time:** [Start time from Garmin]
- **Duration:** [MM:SS]

## Exercises

| Exercise     | Weight  | Sets × Reps | Notes |
| ------------ | ------- | ----------- | ----- |
| [Exercise 1] | [X lbs] | [3×10]      |       |
| [Exercise 2] | [X lbs] | [3×10]      |       |
| ...          |         |             |       |

## Metrics (Garmin)

| Metric              | Value   |
| ------------------- | ------- |
| Duration            | [MM:SS] |
| Avg HR              | [X] bpm |
| Max HR              | [X] bpm |
| Calories            | [X]     |
| Training Effect     | [Label] |
| Aerobic TE          | [X]     |
| Anaerobic TE        | [X]     |
| Training Load       | [X]     |
| Body Battery Impact | [X]     |

## Context

- **Recent Recovery:** [Oura/Garmin recovery data if available]
- **Notes:** [Any relevant context]

## Notes

- [Observation 1]
- [Observation 2]

---

_Logged by ATLAS_
```

## Notes

- Always pull Garmin data — don't rely on user-reported metrics alone
- If user provides specific notes (RPE, exercise modifications), include them
- Update `/home/jmooney/vault/Areas/Health/Training-State.md` checklist after creating the log
