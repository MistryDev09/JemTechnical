# Assumptions

## 1. Assumptions I made

- Shifts with no clock-out time are excluded from the hours calculation. They are flagged, and open shifts in the in-progress week are shown in the dashboard.
- A shift is overnight if its clock-out time is earlier than its clock-in time, and its duration is the time between them across midnight (+24h). This uses the times only, not `shift_pattern`.
- Shifts with an empty or invalid clock-in or clock-out time (or identical clock-in and clock-out) are flagged and excluded from hours.
- Shifts longer than 12 hours are flagged, because the maximum working day under South African law is 12 hours. They are still counted in the hours totals.
- Greater-portion rule (as per South African law, supplied by me; the source was not independently verified): a shift that spans a calendar day boundary is attributed whole to the day on which the greater portion of the shift was worked.
  - If the portions are exactly equal, the shift is split at midnight: the earlier day's hours stay with that day (and its week), and the later day's hours go to the later day.
  - The attributed day decides the week (Monday to Sunday) and the pay rate. A shift moved to a Monday loses the Sunday 2x premium, and a shift moved to a Sunday gets it.
- The same attribution rule applies to public holidays: a shift attributed to a public holiday earns the holiday 2x rate, even if it started the day before.
- Duplicate employee IDs are flagged as potential fraud and escalated for review.
  - Two or more employee IDs are treated as one person if they share an ID number, a bank account or a tax number.
  - Severity is "Escalate" if a bank account or tax number is shared, and "Review" if only the ID number is shared. Currently 5 people (10 employee IDs) are flagged, all "Escalate": E1035/E1036, E1090/E1091, E1097/E1098, E1126/E1127, E1193/E1194.
  - The flags are indicators for escalation, not a finding of guilt. They are worded as "potential".
- Overlapping shifts (one person with two records at the same time, for example at two sites) still have all their recorded hours counted, and are flagged as "Potential fraud: two sites at once". They are marked High severity when the two sites are in different provinces, otherwise Medium. Currently 195 overlapping pairs (126 within one employee ID, 69 between the two IDs of a duplicate person).
- Hours are combined across all employee IDs of one person for weekly totals and breach risk, because splitting hours across two IDs hides a breach.
- In `predictions.csv`, both employee IDs of a merged person get the same `will_breach` and `risk_score`.
- Only the bank account and tax number columns of `payroll_details.csv` are read, in memory, to compare for duplicates. Their values are never written to any output, dashboard, export or notebook.

## 2. Assumptions inferred

_None recorded yet._

## 3. Assumptions not yet decided

### Time and week definition
- Which week is "in progress": derived from the last date in `shifts.csv` (Wed 2026-08-12, so the week starting Mon 2026-08-10), not from today's date.
- A later export may not end on a Wednesday, so the cutoff day should not be hardcoded.
- Weeks run Monday to Sunday.

### Breach definition
- A breach means more than 10 hours of overtime in the week, i.e. more than 55 total hours (45 ordinary plus 10 overtime). Strictly greater than, not greater than or equal to.
- Whether Sunday and public-holiday hours (paid at 2x) count toward the 10-hour overtime cap.
- Monday 2026-08-10 is a public holiday (National Women's Day, observed) and falls inside the in-progress week.
- Whether unpaid breaks should be deducted from shift durations (the data has no break information).

### Data quality
- 184 shifts have no clock-out time. Beyond excluding them, it's undecided whether to impute a typical shift length instead. `weekly_summary.csv` counts them as zero, which understates hours.
- Two shifts' worth of missing clock-outs this week belong to employees (E1182, E1094) who have no other usable shift, so they would show 0 hours.
- The greater-portion rule has a large effect. Counting by the week of the clock-in date gives 66 per-ID breach-weeks, and the greater-portion attribution gives 87, because it moves whole long shifts into the next week. If the checker's ground truth counts by clock-in date, our weekly totals will differ for some people.
- Whether every employee in `employees.csv` must be predicted, including the 6 with no shifts and anyone no longer working.
- `weekly_summary.csv` is not fully trusted: it matches a recomputation from `shifts.csv` exactly, but that includes its errors (missing clock-outs counted as 0, overlaps double-counted).
- Hours for an employee are totalled across all sites, not per site.

### Prediction
- No roster exists for Thursday to Sunday, so how remaining hours are projected is undecided.
- The naive baseline for comparison (e.g. "breaches if already over, or on pace to be").
- Which metric to optimise (breach is rare, about 3.4% of employee-weeks, so accuracy is misleading).
- How to evaluate honestly: test forward in time, not with random splits, since the same person appears across weeks.
- How `risk_score` (0 to 1) is derived and what threshold turns it into `will_breach`.

### Supervisor notes
- Notes cover only some shifts, so conclusions about where overtime is concentrated come from a subset.
- Overtime is a weekly figure but notes attach to single shifts, so a rule is needed to attribute weekly overtime hours to shifts.
- The categories ("client asked for" vs "operational failure" vs "nothing useful") are not yet defined.
- Notes where the stated reason conflicts with the real one (e.g. "client signed for the extra hrs but real reason is relief no show again") need a rule for which reason wins.
- Notes in isiZulu and Afrikaans, typos and filler (".", "-", "ok") need handling; whether to use an LLM, rules, or both is undecided.
- How the note-sorting will be checked given there is no answer sheet.

### Sensitive data
- `payroll_details.csv` contains bank and tax details. It is only used to detect duplicate people (see above), and its values must stay out of the dashboard, outputs and video. The file itself is already in `data/` in the repo as supplied, so whether to remove it before making the repo public is undecided. `hourly_rate` is not used.

### Submission
- The README says the repo must contain "four files" but lists three. The fourth is unclear.
- How new weekly exports will be loaded without a developer (upload vs drop folder).
