# NOTES

**Video (12 minutes(explaination of length in the first 30 seconds)):** https://www.loom.com/share/3668b148cb5f4628bd34b8765d69b255

## 1. Assumptions about the data
Not repeated, because the README gives them: Monday to Sunday weeks, the in-progress week is the one predicted, a breach is over 55 hours, pay 1.5x and 2x. Full list: `docs/assumptions.md`; results and drawbacks: `docs/RESULTS.md`.
- **Greater-portion rule:** I used it to decide which day, and so which week and pay rate, a shift's hours lie in.  The rule was assumed from "Basic Conditions of Employment Act". It matters: it raises breach-weeks from 66 (counting by clock-in date) to 87.
- **Hours come from my own calculation, not the client's summary.** `weekly_summary.csv` is exported from a system I cannot verify, so I doubted it and did not use it as the truth. I judged hours from my own calculation on the recorded clock-in and clock-out times in `shifts.csv`, and used the summary only as a check. The check showed it equals a plain count of the shifts by clock-in date exactly, so it adds no information, and it differs from my hours in 122 of 2,124 employee-weeks because it counts a missing clock-out as 0, double-counts overlapping shifts, does not merge duplicate IDs and assigns weeks by clock-in date.
- **Clock-out time:** a clock-out before the clock-in means an overnight shift (+24h), and `shift_pattern` validates it: a 6pm to 6am shift for a night-pattern employee is confirmed and counted as overnight, while an overnight shift for anyone not on the night pattern is flagged for review (hours still counted). The data has none: every overnight shift is a night-pattern employee's, and no day-pattern employee works one. No meal break is deducted.
- **Missing clock-outs** (184 of 8,863 shifts) are excluded and flagged, not guessed. Guessing them would add about 18 breach-weeks, so excluding understates breaches.
- **Duplicates and double dipping:** employee IDs sharing an ID number, bank account or tax number are one person. They and anyone with overlapping shifts this week are predicted like everyone else and also escalated as possible fraud, not proven. Duplicate people: E1126/E1127, E1097/E1098, E1035/E1036, E1090/E1091, E1193/E1194. Overlapping shifts: E1099, E1104, E1202, E1111, E1152, E1140, E1213, E1100, E1143. The model flags six of these 14 (E1099 and the duplicates), which are false alarms if their hours are not real.
- **Cost:** priced as if these checks ran first, the client pays R141k (4.0%) less than its own counting over 9 weeks (my assumption of the pay rules under Basic Conditions of Employment Act).
- **`will_breach`** is 1 at a risk of 0.25 or more, where precision and recall balance (table in section 3).

## 2. How the note-sorting was checked
No language model: the notes are about 60 repeated sentences with typos and translations, and I had no independent labels to train on. The 9 categories, decided by reading the sentences:

| Category | What it means | Example | Notes | Pile |
|---|---|---|---|---|
| `client_requested` | The client, its centre manager or site manager asked for the extra hours (approval recorded or not) | "client asked us to stay for the delivery, ok'd by centre mgmt" | 401 | client |
| `client_unconfirmed` | The client asked but the note says office approval is not known | "client says stay till 6am, dont know if office approved" | 36 | client |
| `relief_no_show` | The next shift or relief did not arrive, or arrived late | "Next shift guard did not pitch. Had to cover." | 309 | operational |
| `colleague_no_show` | A colleague did not come in and the writer covered | "covering Molefe post, no show no call" | 205 | operational |
| `late_handover` | The previous shift handed over late (keys, paperwork, OB book) | "handover late agn, keys missing" | 212 | operational |
| `equipment_failure` | A machine, lift, generator or gate motor failed | "gate motor failed, manned it by hand till 06:00" | 195 | operational |
| `colleague_sick_or_leave` | A colleague was sick, on family leave or at the clinic | "worked through, Wyk at the clinic" | 194 | absence cover |
| `stood_in_unspecified` | The writer covered for someone, no reason given | "stood in for Fourie" | 130 | absence cover |
| `nothing_useful` | Blank or filler | "ntr", "all fine", "." | 435 | none |

Where a note holds both a client cue and a failure cue, the failure wins ("client signed for the extra hrs but real reason is relief no show again" is operational).

I used typo-tolerant rules and, separately, clusters labelled once by reading, and checked both against 205 notes labelled by hand before the rules were written (by my AI assistant, so a consistency check, not independent). The rules scored 99.0% as first written, the honest number, and 100% after fixes, which is tuned; the clusters scored 100%. I then labelled 50 ambiguous notes myself and the rules agree on all 50, though they are only 11 distinct sentences.

It found about 55% operational failures (60% to 74% depending on how absence cover is counted) and 24% client requests, with no concentration by supervisor, guard or site, so the cause looks systemic. **Limit:** the labels and both methods share one person's judgement, so this shows consistent definitions, not correct ones, and 100% says nothing about new free text.

## 3. What the model learned, and how to test it
I trained a logistic regression (7 features) to predict the probability that a person's total goes over 55 hours. All results are forward in time: train on earlier weeks, score the next one, over the 5 latest complete weeks (16, 16, 17, 11 and 8 breachers; a random list scores a PR-AUC of 0.06).

**Which metric, and why.** PR-AUC (area under the precision-recall curve) scores how well the model ranks the real breachers near the top, looking at every cut-off at once. I use it to compare models and tune settings, because it needs no cut-off and breachers are rare (about 6% of person-weeks), where accuracy would reward "predict nobody". F1 (precision and recall combined) scores one specific cut-off, so I use it only to choose the `will_breach` cut-off: it depends on where the cut-off lands and jumps around with about 14 breachers a week, which makes it poor for comparing models. Equal weight on precision and recall is the balanced choice because the README does not say how the file is scored. The Brier score checks that the probabilities are honest.

**Against the simple rules (PR-AUC, higher is better):**

| Method | All 5 weeks | Week of 6 Jul | 13 Jul | 20 Jul | 27 Jul | 3 Aug | Without the 5 duplicate people |
|---|---|---|---|---|---|---|---|
| Hours so far (B1, B2) | 0.309 | 0.44 | 0.44 | 0.26 | 0.26 | 0.17 | 0.263 |
| Average prior weekly hours (B4) | 0.296 | 0.35 | 0.22 | 0.50 | 0.36 | 0.27 | 0.151 |
| Hours so far + usual shifts still to come (B3) | 0.334 | 0.33 | 0.25 | 0.47 | 0.38 | 0.38 | 0.167 |
| **Logistic regression** | **0.430** | 0.59 | 0.37 | 0.47 | 0.54 | 0.55 | 0.357 |

It beats B3 in 4 of 5 weeks. The Brier score is 0.048 against 0.061 for predicting the base rate, and people it scores 0.4 or more breach 55% of the time (it predicts 61%).

**What it learned:**

| Feature | Weight (standardised, 90% interval) | PR-AUC lost when it is scrambled on the test weeks |
|---|---|---|
| Hours so far | +1.13 (0.82 to 1.46) | 0.241 |
| Past breaches | +0.24 (0.08 to 0.44) | 0.120 |
| Night pattern | +0.27 (0.05 to 0.49) | 0.032 |
| Average weekly hours before | +0.38 (0.10 to 0.70) | 0.025 |
| Shifts so far | -0.12 (-0.46 to 0.23) | 0.022 |
| Average shifts per week before | +0.31 (-0.08 to 0.63) | 0.012 |
| Share of long shifts | +0.13 (-0.25 to 0.38) | -0.005 |

Dropping whole groups instead costs: hours and shifts so far 0.152, the usual weekly pattern (average hours, average shifts, long-shift share) 0.065, past breaches 0.047, night pattern 0.011.

It mostly learned the simple rule it beats: hours so far dominates, then a person's usual long weeks and past breaches. Part of its lead comes from the five duplicate people, who breach almost every week (24 of 104 training breaches), though it holds without them. One weakness: past breaches is a count that grows with history, so this week's people average 0.55 against 0.27 in training, which probably inflates scores a little.

**The cut-off for `will_breach`** (about 13.6 people really breach each week):

| Score at or above | Flagged per week | Precision | Recall | F1 |
|---|---|---|---|---|
| 0.10 | 37 | 0.25 | 0.68 | 0.36 |
| 0.20 | 17 | 0.39 | 0.50 | 0.44 |
| **0.25 (used)** | **14** | **0.45** | **0.46** | **0.45** |
| 0.30 | 11 | 0.47 | 0.40 | 0.43 |
| 0.50 | 5 | 0.63 | 0.25 | 0.36 |

**Small experiments: what the prediction is like given the day of the week.** I rebuilt the model as if the data stopped at the end of each weekday, in every training and test week alike. The later in the week, the less is unknown, and the model's lead over the simple rule shrinks because most hours are already worked.

| Data stops after | Model PR-AUC | Model + recent weeks | B3 | Precision | Recall | Flagged per week |
|---|---|---|---|---|---|---|
| Monday | 0.394 | 0.406 | 0.322 | 0.46 | 0.53 | 15.6 |
| Tuesday | 0.431 | 0.447 | 0.318 | 0.54 | 0.44 | 11.2 |
| **Wednesday (this data)** | **0.430** | 0.443 | 0.334 | 0.45 | 0.47 | 14.2 |
| Thursday | 0.490 | 0.499 | 0.361 | 0.60 | 0.47 | 10.6 |
| Friday | 0.560 | 0.562 | 0.470 | 0.46 | 0.72 | 21.2 |
| Saturday | 0.724 | 0.722 | 0.697 | 0.57 | 0.88 | 21.0 |

(Precision, recall and flags are for the model alone at that day's own F1 cut-off.) The remaining error is mostly the roster for the rest of the week, which the data does not have.

**Small experiments: could anything improve it?** Same folds; change in PR-AUC against the shipped model, with a 90% interval from resampling people. Every interval includes zero.

| Variant | PR-AUC | Change | Weeks won | Flagged per week | Precision | Recall |
|---|---|---|---|---|---|---|
| Shipped model (7 features) | 0.430 | | | 14.2 | 0.45 | 0.47 |
| + recent weeks | 0.443 | +0.013 (-0.007 to +0.031) | 4 of 5 | 9.0 | 0.62 | 0.41 |
| + weekday pattern | 0.436 | +0.006 (-0.010 to +0.023) | 4 of 5 | 10.6 | 0.53 | 0.41 |
| + site | 0.416 | -0.014 (-0.037 to +0.005) | 1 of 5 | 10.4 | 0.52 | 0.40 |
| Two stage (hours first, then the chance of crossing) | 0.422 | -0.008 (-0.045 to +0.022) | 2 of 5 | 7.2 | 0.64 | 0.34 |
| All features | 0.440 | +0.010 (-0.014 to +0.037) | 3 of 5 | 10.6 | 0.55 | 0.43 |
| Average with the B3 rule | 0.428 | -0.002 (-0.011 to +0.011) | 3 of 5 | 13.2 | 0.47 | 0.46 |

Other checks: splitting by person instead of week gives 0.413; counting weeks by clock-in date instead of the greater-portion rule flags 36 people instead of 46 (at the first cut-off); filling the 184 missing clock-outs with the person's usual shift raises PR-AUC to 0.474 (the breach labels change as well, 104 to 122). A trained notes classifier would mostly memorise the 60 sentences and match the rules here; its edge would be unseen phrasings, its risk shortcuts such as supervisor or site.

**Testing on about 200 people without fooling yourself:** split forward in time, never at random, and keep the last weeks untouched until the end. Fix the features and cut-off before looking at them: I tried about eight variants on the same five weeks, so a gain of +0.01 is noise. With about 14 breachers a week, report the uncertainty (resample people, not rows), compare with the simple rule, keep each person and duplicate ID on one side of any split, and build history from completed weeks only.
