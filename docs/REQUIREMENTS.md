# Requirements

Requirements for the final project only. Status is split into Done and Not done.

## Done

- [x] Data files read into pandas (`notebooks/data_modeling.ipynb`)
- [x] Shift hours computed, overnight shifts handled (clock-out before clock-in adds 24h), shifts with no clock-out excluded (notebook only)
- [x] First-pass list of people averaging over 45 hours a week, and a first small projection for the in-progress week (notebook only, not final)
- [x] Shift hours attributed to a day and week with the greater-portion rule, including Sunday and public-holiday rates (`src/hours.py`, tested)
- [x] Duplicate employee IDs (shared ID number, bank account or tax number) detected, severity Escalate or Review, hours combined per person (`src/integrity.py`, tested)
- [x] Overlapping shifts detected and flagged as potential fraud, hours still counted (`src/integrity.py`, tested)
- [x] Prediction model built and evaluated in `notebooks/data_modeling.ipynb`: logistic regression beats the naive baselines on forward-in-time folds (PR-AUC 0.43 vs 0.33 for the best baseline), with leakage checks and sensitivity runs (notebook only, not yet in the app)
- [x] `predictions.csv` with the exact columns, one row for each of the 213 employee IDs, both IDs of a merged person equal (written by `src/pipeline.py`)
- [x] Model moved from the notebook into `src/` (forecast, pipeline, validation, dataset) with tests; the in-progress week and weekday come from the data
- [x] Flagged-list length decided: the F1-optimal cut-off (about 0.25), so `will_breach` flags about as many people as actually breach (23 employee IDs, 18 people, this week)
- [x] Missing clock-outs and Sunday/holiday hours decided (excluded and flagged; Sunday and holiday hours count normally toward the cap)
- [x] Improvement experiments on the model (`notebooks/data_modeling.ipynb` section 10): nothing clearly beats the shipped model
- [x] Results and drawbacks in one place: `docs/RESULTS.md`
- [x] Cost analysis notebook (`notebooks/cost_analysis.ipynb`): the client's way of counting hours against ours, in money, per employee and in total (extra, not in the README)

## Not done

### The answer (must be correct)
- [ ] Review `predictions.csv` (written by `python -m src.pipeline data predictions.csv`; 213 rows, 23 flagged IDs; duplicate and double-dipping people are flagged by the model like everyone else, tagged "Also escalated" on the dashboard and named in `NOTES.md`)

### Dashboard
- [ ] Deployed on a public URL that works on a phone (the app is built and checked locally at laptop and phone width; see docs/DEPLOY.md)
- [x] Shows who goes over the 10-hour overtime cap by Sunday, ranked by risk, with hours so far, hours left and sites (built, runs locally)
- [x] The list shows people at 50% risk or higher, each with a Resolve button inside the box, and three drop-downs below it: 30 to 50%, 20 to 30% and 0 to 20% risk
- [x] Each box shows hours so far, shifts so far, hours left to 55, the usual shifts left this week and the usual hours still to come (usual shifts left x usual shift length)
- [ ] TODO: Resolve only shows the message at the top. Decide what resolving means (for example record who resolved it and when, and remove the item from the list) and build it
- [ ] Says what to do about each person or site, specific to the data (partly: each person shows hours left and how many usual shifts that allows; no site-level advice yet)
- [x] Shows why the hours happened, based on the supervisors' notes (a "Why the hours happened" button inside each person's box; rules in `src/notes.py`, shared with the notebook)

### Escalations (dashboard)
- [x] Show duplicate people flagged for escalation (both IDs, evidence "same ID number / bank account / tax number", severity), never showing bank or tax values
- [x] Show overlapping shifts flagged as potential fraud (person, sites, overlap hours, High if different provinces)
- [x] Wording is "potential" and "for review", not an accusation
- [x] The "2 records, see Escalations" flag on a person's card is a link that jumps to that person under Escalations
- [x] Overlapping shifts are shown as cards (person, severity, both sites and times side by side) so nothing needs sideways scrolling on a phone
- [x] Resolve buttons on each duplicate, overlap and listed person, and an Escalate all button, show a message that drops in at the top for about two seconds: "Sent message to supervisor: resolving a duplicate / an overtime person / a shift overlap (sent by internal tool or email)". The email pop-up was removed
- [ ] TODO: nothing is actually sent yet. The message at the top is a placeholder. Build the real sending (internal tool or email), decide the recipient address, and say "sent" only when it has been sent
- [ ] TODO: keep track of what has been reported (a reported or escalated state per item), so the same item is not reported twice

### Supervisor notes
- [x] Taxonomy of reasons for extra hours, including a "nothing useful" category (9 categories, 4 piles; `notebooks/shift_classification.ipynb`)
- [x] Overtime split into hours the client asked for versus hours caused by operational failures (55% operational, 24% client, reported as a range), and where it is concentrated (it is not: supervisors, guards, sites, weekdays)
- [x] Self-designed check of the sorting: blind hand-labelled sample of 205 plus two methods compared, with pre-fix and post-fix scores and where it was wrong. You hand-labelled 50 ambiguous notes (`evaluation/labels/notes_to_label_by_you.csv`): the rules agree on 50 of 50 (11 distinct sentences, a narrow check); your labels side with the rules, not the supplied file, on 10 stood-in notes
- [x] `note_classifications.csv` with one row per note in `shift_notes.csv`, exactly the columns `shift_id,category,note` (2,117 rows)

### Loading new data
- [x] Upload of any of the files in the dashboard, overwrite or append per file, with file, column and value checks and clear messages
- [x] Everything reprocesses end to end with no developer and no hardcoded dates, weekdays or employee IDs (cutoff weekday taken from the data)
- [x] Regenerated `predictions.csv` available to download after an upload
- [x] `note_classifications.csv` available to download in the dashboard (the classifier is in `src/notes.py`)

### Repo and submission
- [x] `NOTES.md`, half a page: assumptions, how the note-sorting was checked and what it found, what a trained model would learn that this approach does not, and how to test it on about 200 people without fooling yourself
- [x] Public repo containing the required files (`predictions.csv`, `note_classifications.csv`, `NOTES.md`)
- [x] The "four files" question is settled: it is the three files the README lists (`predictions.csv`, `note_classifications.csv`, `NOTES.md`)
- [ ] Video, 5 minutes, camera on and screen shared: what was unexpected, baseline and metric (and why), where the output is not trusted, what to do next, and one number explained step by step for a non-technical person
- [ ] Three links sent: dashboard, repo, video

### Constraints
- [ ] Free tiers only, no paid API key, runs on a normal laptop
- [ ] Every assumption written down
- [ ] Bank and tax details in `payroll_details.csv` kept out of the dashboard, outputs and video
