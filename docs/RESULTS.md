# Results and drawbacks

What testing found, and where it falls short. Numbers come from the notebooks in `notebooks/`; the dashboard, `predictions.csv` and `note_classifications.csv` use the same code in `src/`.

## 1. The answer: who breaches by Sunday
- The model predicts the **probability that a person's total goes over 55 hours** this week, not the hours. `predictions.csv` has 213 rows; `will_breach` is 1 at a score of 0.25 or more, which flags **23 employee IDs (18 people)** this week. Duplicate people and people double dipping are predicted like everyone else and also escalated; they are named in `NOTES.md`.
- On the 5 most recent complete weeks, tested forward in time, that cut-off flags about 14 people a week for about 14 real breachers: **about 45% of flags are right and about 46% of breachers are caught**.

| Cut-off | Flagged per week | Precision | Recall | Why |
|---|---|---|---|---|
| 0.096 (first choice, F2) | 37 | 0.25 | 0.68 | catches most breachers, wrong 3 times in 4 |
| **0.25 (shipped, F1)** | **14** | **0.45** | **0.46** | balanced; the README does not say how the file is scored |
| 0.50 (dashboard list) | 5 | 0.63 | 0.25 | a "must act now" list |

## 2. Does the model beat a simple rule?
Forward-in-time folds (train on earlier weeks, test on the next), 5 test weeks, PR-AUC (higher is better, a random list scores 0.06):

| Method | PR-AUC |
|---|---|
| Hours so far (B1, B2 rank identically) | 0.309 |
| Average prior weekly hours (B4) | 0.296 |
| Hours so far + usual shifts still to come (B3, the "usual hours still to come" rule) | 0.334 |
| **Logistic regression, 7 features** | **0.430** (wins 4 of 5 folds) |

- Without the 5 duplicate people, who breach almost every week: 0.357 against 0.167 for B3, so the win is not caused by them.
- Brier score 0.048 against 0.061 for always predicting the base rate; the probabilities are roughly honest (people scored 0.4+ breach 55% of the time).
- What drives it: hours so far (dropping it costs 0.15 PR-AUC), then the person's usual weekly pattern and their past breaches. Checks that found no problem: leakage tests on 40 random person-weeks, a split by person instead of by week (0.413).

## 3. What did not help
Variants on the same folds (change in PR-AUC against the shipped model): recent weeks +0.013, weekday pattern +0.006, site features -0.014, two-stage (hours first, then the chance of crossing) -0.007, ensemble -0.002. Every interval includes zero. With about 14 breachers a week there is too little data for extra features to pay off, and the real unknown is the roster for the rest of the week, not the model.

**Accuracy rises as the week goes on:** PR-AUC is 0.39 if the data stops Monday, 0.43 Wednesday, 0.56 Friday, 0.72 Saturday.

## 4. What the data showed
- The client's `weekly_summary.csv` differs from our hours in 122 of 2,124 employee-weeks (it counts missing clock-outs as 0, double-counts overlaps and counts weeks by clock-in date).
- Counting rules change who breaches: 66 breach-weeks by clock-in date, 87 with the greater-portion rule, 114 once duplicate IDs are merged. Counting weeks by clock-in date flags 36 people instead of 46 (at the original cut-off).
- 5 duplicate people (10 IDs) share an ID number, bank account or tax number. 195 pairs of overlapping shifts, 114 person-days at two sites on one day (people who are not duplicates). 184 of 8,863 clock-outs (2%) are missing.
- Filling the missing clock-outs with the usual shift length would add about 18 breach-weeks (104 to 122) and lift PR-AUC to 0.47, so excluding them understates breaches.

## 5. Cost (`notebooks/cost_analysis.ipynb`)
Complete weeks, 213 employee IDs, pay at 1x, 1.5x above 45 hours, 2x Sunday and holidays (our reading of the README):

| Counting | Cost |
|---|---|
| Client's weekly summary alone (no day detail) | R3.08m |
| Client's way with Sunday/holiday hours from the shifts | R3.51m |
| Ours: greater-portion rule, duplicate people not paid, lower site on two-site days dropped, overlap paid once | R3.37m (4.0% lower) |

The summary understates cost by about R432k because it cannot see the Sunday/holiday premium. Of the R474k premium, R457k is Sunday/holiday and only R18k is overtime. Hours beyond 55 cost only about R2k a week, so stopping breaches saves little wages; the value is compliance.

## 6. Supervisor notes (`notebooks/shift_classification.ipynb`)
- 2,117 notes are about 60 repeated sentences; 21% say nothing useful. No language model was needed.
- **Split of the 1,682 useful notes:** 55% operational failure, 24% client asked, 19% absence cover, 2% client asked but approval unknown. It is a range: 60% if "took X's shift" counts as a no-show, 74% if all absence cover counts. Hours-weighted shares move by under 2 points. 28% of client-asked notes have no approval wording.
- **Concentration: none.** Supervisors, guards, sites and weekdays do not differ after correcting for many comparisons (SUP-03 at 68% operational is p = 0.76 corrected). It looks systemic, mainly relief and staffing.
- **Check:** rules scored 99.0% on 205 blind hand-labelled notes as first written (the honest number) and 100% after fixes (tuned). Clusters scored 100%. Your 50 hand labels agree with the rules on 50 of 50.

## 7. Drawbacks
- **No roster.** The model does not know who is scheduled Thursday to Sunday; it only learns usual shifts. This is the main limit and the cheapest fix is the scheduled shifts.
- **Small data.** About 14 breachers a week over 5 test weeks; every figure above is noisy, and precision fell from 0.32 to 0.18 across the test windows at the first cut-off as breachers got fewer. Treat the cut-off comparison as a guide.
- **Over-flagging remains.** Even the balanced cut-off is wrong more than half the time, and it misses more than half of breachers.
- **Escalated people may not be real overtime.** 6 of the 14 duplicate or double-dipping people are flagged (scores 0.67 to 0.95). If their hours are not real, those flags are false alarms; if the hours are real, they are some of the surest breachers. We cannot tell which. Only this week's overlaps count, not earlier weeks.
- **Missing clock-outs are excluded**, which understates hours and breaches (section 4).
- **The note check is narrow.** The labels and both methods share one person's judgement, the 50 labels cover only 11 distinct sentences, and 100% says nothing about new free text, which would fall to "Unclear". Notes cover only 24% of shifts and those shifts are longer (11.1 hours against 9.4), so the reasons describe long shifts.
- **The pay rule is our reading**, not payroll's, and we cannot tell which of two duplicate IDs is real, so both are not paid.
- **Dashboard.** Changes from uploads last only for the session. Resolve only shows a message; nothing is sent or tracked. Requirement 2 (what to do about each person) is only partly covered by hours left and usual shifts left. Free hosting sleeps after inactivity.
