# Log Workout Skill

Log a completed workout with Garmin data and update `/home/jmooney/vault/Areas/Health/Training-State.md`.

## Instructions

1. **Get Today's Date** — Determine the workout date

2. **Read `ATLAS-Garmin-Workout-Helper.md` in the current session directory**

   - Follow the MCP-first / fallback-second instructions in that file
   - Never launch `garmin-mcp` manually or attempt a raw MCP stdio handshake

3. **Fetch Garmin Activity Data**

   - If direct Garmin tools are available, use `mcp__garmin__get_activities_fordate` with today's date
   - Then use `mcp__garmin__get_activity` with the selected activity_id for full details
   - If direct Garmin tools are unavailable, run the repo fallback helper from `ATLAS-Garmin-Workout-Helper.md`
   - Extract: activity id, start time, duration, avg HR, max HR, calories, aerobic/anaerobic training effect, training load, body battery impact, readiness, HRV, sleep, HR zones

4. **Read `/home/jmooney/vault/Areas/Health/Training-State.md`** — Get the scheduled workout details:

   - What exercises were planned
   - Target sets/reps/weights
   - Any modifications or cautions

5. **Create Workout Log** at `/home/jmooney/vault/Areas/Health/Workout-Logs/[YYYY-MM-DD].md`

6. **Update `/home/jmooney/vault/Areas/Health/Training-State.md`** — Update the session's status line with the current state (`Done`, `Planned`, `Skipped`, `Rest`, etc.) plus any completion details

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

- **Recent Recovery:** [Oura/WHOOP/Garmin recovery data if available]
- **Notes:** [Any relevant context]

## Notes

- [Observation 1]
- [Observation 2]

---

_Logged by ATLAS_
```

## Notes

- Always pull Garmin data — don't rely on user-reported metrics alone
- Prefer direct `mcp__garmin__*` tools when they are present in the session
- If Garmin MCP tools are missing, use the repo fallback helper and work from its normalized JSON output
- If user provides specific notes (RPE, exercise modifications), include them
- Update the relevant status entry in `/home/jmooney/vault/Areas/Health/Training-State.md` after creating the log
