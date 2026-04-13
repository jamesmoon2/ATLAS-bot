# Morning Briefing Skill

Generate a morning briefing for James with weather, schedule, training, medications, and recovery data.

## Instructions

1. **Get Current Time** — Use the `**Current Time:**` value provided in the prompt as the
   authoritative reference for date/time

2. **Weather** — Fetch forecast for Mountlake Terrace, WA (lat: 47.7923, lon: -122.3076):

   - Use `mcp__weather__get_forecast` for today's forecast
   - Use `mcp__weather__get_alerts` for any active alerts
   - Include high/low temps, precipitation chance, wind

3. **Schedule** — Fetch today's calendar events:

   - Use the Google Calendar events search/list tool available in the active provider for the
     primary calendar
   - Time range: today 00:00 to 23:59
   - List events with times

4. **Training** — Read `/home/jmooney/vault/Areas/Health/Training-State.md`:

   - Identify today's scheduled workout from "This Week" section
   - Include exercise details from the program template
   - Note any active cautions (injuries, fatigue indicators)

5. **Medications** — Read `/home/jmooney/vault/Areas/Health/Medications.md`:

   - Check if any medications are due today based on schedules
   - List upcoming doses

6. **Recovery** — Fetch Oura data:

   - Use `mcp__oura__get_daily_sleep` for last night's sleep
   - Use `mcp__oura__get_daily_readiness` for this morning's readiness
   - Include sleep score, readiness score, HRV balance

7. **Recommendation** — Synthesize all data into a brief recommendation:
   - Should James proceed with planned training?
   - Any modifications needed based on recovery?
   - Weather considerations?

## Output Format

```markdown
# Morning Briefing — [Day], [Date]

## Weather

**Mountlake Terrace:** [conditions]. High [X]°F / Low [Y]°F, [Z]% precipitation. [Wind]. [Alerts if any]

## Schedule

- [Time]: [Event]
- [Time]: [Event]

## Training

**[Workout Name] — [Week X Day Y]**

- [Exercise]: [weight] × [sets]×[reps]
- ...
- Target RPE: [X]/10

⚠️ **Cautions:** [any active injuries or concerns]

## Medications

**[Due today or None due today]**

- Next [med]: [day/time]

## Recovery

**Last Night's Oura ([date]):**

- Sleep: [score]
- Readiness: [score]
- HRV Balance: [score]/100

## Recommendation

[2-3 sentences synthesizing all data into actionable guidance]
```

## Notes

- This is an unattended scheduled job: do not ask the user follow-up questions
