# Assumptions

## 1. Assumptions I made

- Shifts with no clock-out time are excluded from the hours calculation.

## 2. Assumptions inferred

_None recorded yet._

## 3. Assumptions not yet decided

### Time and week definition
- Which week is "in progress": derived from the last date in `shifts.csv` (Wed 2026-08-12, so the week starting Mon 2026-08-10), not from today's date.
- A later export may not end on a Wednesday, so the cutoff day should not be hardcoded.
- Weeks run Monday to Sunday.
- Overnight shifts that cross midnight on a Sunday: which week do the hours belong to (clock-in date or split at midnight)?

### Breach definition
- A breach means more than 10 hours of overtime in the week, i.e. more than 55 total hours (45 ordinary plus 10 overtime). Strictly greater than, not greater than or equal to.
- Whether Sunday and public-holiday hours (paid at 2x) count toward the 10-hour overtime cap.
- Monday 2026-08-10 is a public holiday (National Women's Day, observed) and falls inside the in-progress week.
- Whether unpaid breaks should be deducted from shift durations (the data has no break information).

### Data quality
- 184 shifts have no clock-out time. Beyond excluding them, it's undecided whether to impute a typical shift length instead. `weekly_summary.csv` counts them as zero, which understates hours.
- Two shifts' worth of missing clock-outs this week belong to employees (E1182, E1094) who have no other usable shift, so they would show 0 hours.
- 126 same-day shift pairs have the same employee at two different sites with overlapping times, which is physically impossible. Undecided whether overlapping time is counted once (union) or summed.
- Five pairs of employee IDs share an ID number and look like one person registered twice: E1035/E1036, E1090/E1091, E1097/E1098, E1126/E1127, E1193/E1194. Undecided whether to merge them into one person for hours totals.
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
- `payroll_details.csv` contains bank and tax details. Undecided whether it is used at all (only `hourly_rate` seems relevant) and it should not be in the repo, dashboard or video.

### Submission
- The README says the repo must contain "four files" but lists three. The fourth is unclear.
- How new weekly exports will be loaded without a developer (upload vs drop folder).
