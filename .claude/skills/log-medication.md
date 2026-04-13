# Log Medication Skill

Log a medication dose to `/home/jmooney/vault/Areas/Health/Medications.md`.

## Instructions

1. **Identify the Medication** — From user input, determine which medication was taken

2. **Read `/home/jmooney/vault/Areas/Health/Medications.md`** — Find the appropriate dosing log table

3. **Add Entry** — Append a new row to the dosing log with:
   - Date (YYYY-MM-DD format)
   - Dose (from the protocol or user-specified)
   - Day number if applicable (e.g., "Day 10" for BPC-157)
   - Notes if provided

## Medication Reference

| Medication  | Dose            | Schedule         | Log Table Location                     |
| ----------- | --------------- | ---------------- | -------------------------------------- |
| Retatrutide | 2mg             | Sat PM, Wed AM   | "Dosing Log" under Retatrutide section |
| TRT + HCG   | Test + 300u HCG | Mon AM, Thu PM   | "Dosing Log" under TRT section         |
| BPC-157     | 1mg             | Daily            | "Dosing Log" under BPC-157 section     |
| Bromantane  | 50mg            | Weekday mornings | "Dosing Log" under Bromantane section  |

## Output

After logging, confirm:

```
Logged: [Medication] [dose] on [date]
```

## Notes

- Use the exact table format from each section
- For day-numbered protocols (BPC-157, Bromantane), calculate the day number from start date
- If weight is mentioned with Reta, include it in the log
- Don't ask for confirmation — just log it
