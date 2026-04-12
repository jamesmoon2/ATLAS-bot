# Health Pattern Monitor Skill

Monitor health metrics for concerning patterns and alert only when action is needed.

## Instructions

1. **Fetch Today's Data**

   - Use `mcp__oura__get_daily_sleep` for last night's sleep
   - Use `mcp__oura__get_daily_readiness` for this morning's readiness
   - Use `mcp__oura__get_daily_activity` for activity data

2. **Read Baselines** from `/home/jmooney/vault/System/ATLAS-Context.md`:

   - Sleep baseline: High 80s - low 90s
   - HRV baseline: 20-40 range (lower due to TRT/Reta)
   - Note: James's HRV runs low — this is normal for him

3. **Check for Concerning Patterns**

   **Alert if ANY of these occur:**

   - Sleep score < 60 for 2+ consecutive days
   - Readiness score < 50 for 2+ consecutive days
   - HRV balance < 20 (significantly below baseline)
   - Sleep duration < 6 hours
   - Activity score < 50 with no rest day explanation

   **Do NOT alert for:**

   - Single bad night (normal variance)
   - Low scores on planned rest days
   - HRV in 20-40 range (this is James's baseline)
   - Scores that are below "excellent" but still functional

4. **Output**

   **If no concerning patterns:**
   Output exactly: `NO_ALERT`

   **If concerning pattern detected:**

   ```
   **Health Alert**

   **Pattern:** [what was detected]
   **Data:** [specific numbers]
   **Recommendation:** [actionable suggestion]
   ```

## Key Context

- James is on TRT + Retatrutide — HRV runs lower than typical population
- Training Week 3 in progress — some fatigue is expected
- Medial epicondylitis (elbow) being managed — not a health monitor concern
- Low back history — not a health monitor concern unless sleep quality affected

## Examples

**Normal (no alert):**

- Sleep 76, Readiness 65, HRV 35 → `NO_ALERT`
- Sleep 82, Readiness 71, HRV 28 → `NO_ALERT`

**Alert:**

- Sleep 52, Readiness 45, HRV 18 (second consecutive day) → Alert with recovery recommendation
