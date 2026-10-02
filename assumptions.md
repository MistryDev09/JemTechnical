# Assumptions

## 1. Assumptions I made

- Shifts with no clock-out time are excluded from the hours calculation. They are flagged, and open shifts in the in-progress week are shown in the dashboard.
- A shift is overnight if its clock-out time is earlier than its clock-in time, and its duration is the time between them across midnight (+24h). This uses the times only, not `shift_pattern`.
- Shifts with an empty or invalid clock-in or clock-out time (or identical clock-in and clock-out) are flagged and excluded from hours.
- Shifts longer than 12 hours are flagged, because the maximum working day under South African law is 12 hours. They are still counted in the hours totals.
- Greater-portion rule (as per South African law, supplied by me; the source was not independently verified): a shift that spans a calendar day boundary is attributed whole to the day on which the greater portion of the shift was worked.
  - If the portions are exactly equal, the shift is split at midnight: the earlier day's hours stay with that day (and its week), and the later day's hours go to the later day.
  - The attributed day decides the week (Monday to Sunday) and the pay rate. A shift moved to a Monday loses the Sunday 2x premium, and a shift moved to a Sunday gets it.
- The greater-portion rule is in effect everywhere: hours totals, weekly breach labels, the model's features and the final predictions all use the attributed week, not the clock-in date. We treat it as the way the client's ground truth counts hours. Its effect is large and is stated so it can be explained: it raises breach-weeks from 66 (clock-in date, per employee ID, which is also what the client's `weekly_summary.csv` shows) to 87 (per ID) because it moves whole long shifts into the next week, and to 114 once duplicate IDs are merged. A clock-in-date rerun of the model is kept only as a sensitivity check (it flags 36 people instead of 46 this week, and 12 predictions differ).
- The same attribution rule applies to public holidays: a shift attributed to a public holiday earns the holiday 2x rate, even if it started the day before.
- Duplicate employee IDs are flagged as potential fraud and escalated for review.
  - Two or more employee IDs are treated as one person if they share an ID number, a bank account or a tax number.
  - Severity is "Escalate" if a bank account or tax number is shared, and "Review" if only the ID number is shared. Currently 5 people (10 employee IDs) are flagged, all "Escalate": E1035/E1036, E1090/E1091, E1097/E1098, E1126/E1127, E1193/E1194.
  - The flags are indicators for escalation, not a finding of guilt. They are worded as "potential".
- Overlapping shifts (one person with two records at the same time, for example at two sites) still have all their recorded hours counted, and are flagged as "Potential fraud: two sites at once". They are marked High severity when the two sites are in different provinces, otherwise Medium. Currently 195 overlapping pairs (126 within one employee ID, 69 between the two IDs of a duplicate person).
- Hours are combined across all employee IDs of one person for weekly totals and breach risk, because splitting hours across two IDs hides a breach.
- In `predictions.csv`, both employee IDs of a merged person get the same `will_breach` and `risk_score`.
- Only the bank account and tax number columns of `payroll_details.csv` are read, in memory, to compare for duplicates. Their values are never written to any output, dashboard, export or notebook.
- The in-progress week is derived from the last date in `shifts.csv` (currently Wed 2026-08-12, so the week starting Mon 2026-08-10), not from today's date. During testing the cutoff date can also be set by hand.
- The cutoff day is not hardcoded. A later export, or a test, may use a cutoff later in the week.
- A breach means more than 10 hours of overtime in the week, i.e. more than 55 total hours (45 ordinary plus 10 overtime). Strictly greater than, not greater than or equal to.
- Sunday and public-holiday hours count toward the 10-hour overtime cap, and are paid at 2x. They count as normal hours in the totals; the 2x is a pay rate, not extra weight toward the cap.
- Monday 2026-08-10 is a public holiday (National Women's Day, observed, from `public_holidays.csv`) and falls inside the in-progress week.
- No meal break is deducted. Shift hours are the full time between clock-in and clock-out, because any meal break is assumed to be included in the shift and paid. The data has no break information (no break field, no deduction in the client's `weekly_summary.csv`, and no break notes).
- New weekly exports are loaded by uploading the files in the dashboard (a Streamlit app on Streamlit Community Cloud), with no developer needed.
- Prediction model (built in `data_modeling.ipynb`):
  - One row per person (duplicate IDs merged) per week. The label is 1 if the person's attributed hours in a completed week are strictly over 55. Weeks 2 to 9 are used for training and week 10 (in progress) is predicted. Week 1 only provides history.
  - The cutoff is stored as an offset from Monday (currently +2 days, from the last `shift_date`), and every training week is cut at the same point. "Hours so far" means shifts clocked in on or before that point, so Sunday-start shifts attributed to Monday and Wednesday-night shifts attributed to Thursday count as already worked.
  - Model: standardised logistic regression with 7 features (hours so far, shifts so far, average weekly hours, average shifts per week, share of shifts over 11 hours, prior breaches, night pattern). History features use completed prior weeks only. Regularisation is chosen by an inner time-split inside the training weeks only.
  - Evaluation uses an expanding window over test weeks 5 to 9, never random splits. Baselines B1 to B4 are scored on the same folds. If the model does not clearly beat B3 (higher pooled PR-AUC and better in at least 3 of 5 folds), B3 is used instead.
  - Metrics: PR-AUC and precision and recall of the flagged list as the headline, and the Brier score to check that `risk_score` is an honest probability. Accuracy is not used. Results are also reported without the 5 merged people.
  - `risk_score` is the predicted probability. `will_breach` is 1 when the score reaches the threshold that maximises F2 on the out-of-fold predictions. We are sticking with F2 for now and may revisit it. It flags 46 people (51 employee IDs) this week against about 13 expected breachers, with an out-of-fold precision of about 0.25 and recall of about 0.69. A stricter F1 threshold would flag about 14 names a week but miss about half of the breachers.
  - The remaining shifts for Thursday to Sunday are not known (no roster), so the model learns them from the person's usual shifts per week and the shifts already worked.
  - Missing clock-outs stay excluded in the model. Imputing the person's median shift length is only a sensitivity run.
  - Site, role, supervisor notes, `weekly_summary.csv` and `payroll_details.csv` are not used as features.

## 2. Assumptions inferred

- Weeks run Monday to Sunday.
- Every `employee_id` in `employees.csv` gets a row in `predictions.csv`, including employees with no shifts in the in-progress week, because the README requires one row per employee.
- Hours for a person are totalled across all sites, not per site. This follows from counting overlapping records and from combining duplicate IDs.
- `weekly_summary.csv` is not used as the source of truth. Hours are recomputed from `shifts.csv`, and the summary is only used for comparison. It matches a plain recomputation exactly, but that includes its errors (missing clock-outs counted as 0, overlaps double-counted, no merging of duplicate IDs, weeks by clock-in date). Under our rules 122 of 2,124 employee-weeks differ from it.
- Employees whose only shifts this week have no clock-out (E1182, E1094) show 0 hours so far, and are listed as open shifts for review.

## 3. Assumptions not yet decided

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
