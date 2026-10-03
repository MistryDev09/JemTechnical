# Requirements

Requirements for the final project only. Status is split into Done and Not done.

## Done

- [x] Data files read into pandas (`data_modeling.ipynb`)
- [x] Shift hours computed, overnight shifts handled (clock-out before clock-in adds 24h), shifts with no clock-out excluded (notebook only)
- [x] First-pass list of people averaging over 45 hours a week, and a first small projection for the in-progress week (notebook only, not final)
- [x] Shift hours attributed to a day and week with the greater-portion rule, including Sunday and public-holiday rates (`src/hours.py`, tested)
- [x] Duplicate employee IDs (shared ID number, bank account or tax number) detected, severity Escalate or Review, hours combined per person (`src/integrity.py`, tested)
- [x] Overlapping shifts detected and flagged as potential fraud, hours still counted (`src/integrity.py`, tested)
- [x] Prediction model built and evaluated in `data_modeling.ipynb`: logistic regression beats the naive baselines on forward-in-time folds (PR-AUC 0.43 vs 0.33 for the best baseline), with leakage checks and sensitivity runs (notebook only, not yet in the app)
- [x] Provisional `predictions.csv` with the exact columns, one row for each of the 213 employee IDs, both IDs of a merged person equal
- [x] Model moved from the notebook into `src/` (forecast, pipeline, validation, dataset) with tests; the in-progress week and weekday come from the data
- [x] Flagged-list length decided: keep the F2 threshold (46 people this week), revisit later if a better approach comes up
- [x] Missing clock-outs and Sunday/holiday hours decided (excluded and flagged; Sunday and holiday hours count normally toward the cap)

## Not done

### The answer (must be correct)
- [ ] Review `predictions.csv` (it is now reproduced exactly by `python -m src.pipeline data predictions.csv`)

### Dashboard
- [ ] Deployed on a public URL that works on a phone (the app is built and checked locally at laptop and phone width; see DEPLOY.md)
- [x] Shows who goes over the 10-hour overtime cap by Sunday, ranked by risk, with hours so far, hours left and sites (built, runs locally)
- [ ] Says what to do about each person or site, specific to the data (partly: each person shows hours left and how many usual shifts that allows; no site-level advice yet)
- [ ] Shows why the hours happened, based on the supervisors' notes

### Escalations (dashboard)
- [x] Show duplicate people flagged for escalation (both IDs, evidence "same ID number / bank account / tax number", severity), never showing bank or tax values
- [x] Show overlapping shifts flagged as potential fraud (person, sites, overlap hours, High if different provinces)
- [x] Wording is "potential" and "for review", not an accusation

### Supervisor notes
- [ ] Taxonomy of reasons for extra hours, including a "nothing useful" category
- [ ] Overtime split into hours the client asked for versus hours caused by operational failures, and where that split is concentrated
- [ ] Self-designed check of the sorting (hand-labelled sample and/or two methods compared), including where the sorting was wrong
- [ ] `note_classifications.csv` with one row per note in `shift_notes.csv`, exactly the columns `shift_id,category,note`

### Loading new data
- [x] Upload of any of the files in the dashboard, overwrite or append per file, with file, column and value checks and clear messages
- [x] Everything reprocesses end to end with no developer and no hardcoded dates, weekdays or employee IDs (cutoff weekday taken from the data)
- [x] Regenerated `predictions.csv` available to download after an upload
- [ ] `note_classifications.csv` available to download (waits for the notes feature)

### Repo and submission
- [ ] `NOTES.md`, half a page: assumptions, how the note-sorting was checked and what it found, what a trained model would learn that this approach does not, and how to test it on about 200 people without fooling yourself
- [ ] Public repo (or invite `southafricanrob`) containing the required files; confirm with the client what the "four files" are, since the README lists three
- [ ] Video, 5 minutes, camera on and screen shared: what was unexpected, baseline and metric (and why), where the output is not trusted, what to do next, and one number explained step by step for a non-technical person
- [ ] Three links sent: dashboard, repo, video

### Constraints
- [ ] Free tiers only, no paid API key, runs on a normal laptop
- [ ] Every assumption written down
- [ ] Bank and tax details in `payroll_details.csv` kept out of the dashboard, outputs and video
