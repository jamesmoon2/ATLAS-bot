# Log Cardio Skill

Log a completed cardio session (Peloton, ruck, run) with Garmin data.

## Instructions

1. **Get Today's Date** — Determine the session date

2. **Fetch Garmin Activity Data**

   - Use `mcp__garmin__get_activities_fordate` with today's date
   - Use `mcp__garmin__get_activity` with the activity_id for full details
   - Look for activity types: indoor_cycling, walking, running, hiking

3. **Extract Key Metrics**

   - Duration
   - Avg HR, Max HR
   - Calories
   - Training Effect (aerobic/anaerobic)
   - Training Load
   - Distance (if applicable)
   - For Peloton: output, power, cadence from screenshot if provided

4. **Create Workout Log** at `/home/jmooney/vault/Areas/Health/Workout-Logs/[YYYY-MM-DD].md`

5. **Update `/home/jmooney/vault/Areas/Health/Training-State.md`** — Mark the cardio session complete

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
