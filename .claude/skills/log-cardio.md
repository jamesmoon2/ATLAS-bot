# Log Cardio Skill

Log a completed cardio session (Peloton, ruck, run) with Garmin data.

## Instructions

1. **Get Today's Date** — Determine the session date

2. **Read `ATLAS-Garmin-Workout-Helper.md` in the current session directory**

   - Follow the MCP-first / fallback-second instructions in that file
   - Never launch `garmin-mcp` manually or attempt a raw MCP stdio handshake

3. **Fetch Garmin Activity Data**

   - If direct Garmin tools are available, use `mcp__garmin__get_activities_fordate` with today's date
   - Then use `mcp__garmin__get_activity` with the selected activity_id for full details
   - If direct Garmin tools are unavailable, run the repo fallback helper from `ATLAS-Garmin-Workout-Helper.md`
   - Look for activity types: indoor_cycling, walking, running, hiking
   - Extract: activity id, start time, duration, avg HR, max HR, calories, aerobic/anaerobic training effect, training load, body battery impact, readiness, HRV, sleep, HR zones

4. **Extract Key Metrics**

   - Duration
   - Avg HR, Max HR
   - Calories
   - Training Effect (aerobic/anaerobic)
   - Training Load
   - Distance (if applicable)
   - For Peloton: output, power, cadence from screenshot if provided

5. **Create Workout Log** at `/home/jmooney/vault/Areas/Health/Workout-Logs/[YYYY-MM-DD].md`

6. **Update `/home/jmooney/vault/Areas/Health/Training-State.md`** — Mark the cardio session complete

## Cardio Log Format

```markdown
# Workout Log — [YYYY-MM-DD]

## Session Info

- **Type:** [Cardio type - Z2 Peloton/Ruck/Run]
- **Week:** [X] of 4
- **Day:** [Day of week]
- **Duration:** [MM:SS]

## Metrics (Garmin)

| Metric              | Value   |
| ------------------- | ------- |
| Duration            | [MM:SS] |
| Avg HR              | [X] bpm |
| Max HR              | [X] bpm |
| Calories            | [X]     |
| Training Effect     | [Label] |
| Aerobic TE          | [X]     |
| Training Load       | [X]     |
| Body Battery Impact | [X]     |

## Peloton Metrics (if applicable)

| Metric         | Value   |
| -------------- | ------- |
| Total Output   | [X] kJ  |
| Avg Power      | [X] W   |
| Avg Resistance | [X]%    |
| Avg Cadence    | [X] rpm |
| Distance       | [X] mi  |

## Zone 2 Validation

- **Talk Test:** [Could converse easily / At upper edge / Too hard]
- **RPE:** [X]/10
- **HR Zone Distribution:** [% in Z2]

## Notes

- [Observation]

---

_Logged by ATLAS_
```

## Notes

- Zone 2 (Attia protocol): Talk test is primary validation, not HR zones
- Garmin HR zones don't map 1:1 to metabolic zones
- Target Z2: "can speak in full sentences without reluctance", RPE 3-4/10
- Prefer direct `mcp__garmin__*` tools when they are present in the session
- If Garmin MCP tools are missing, use the repo fallback helper and work from its normalized JSON output
