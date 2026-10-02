# Requirements

Requirements for the final project only. Status is split into Done and Not done.

## Done

- [x] Data files read into pandas (`data_modeling.ipynb`)
- [x] Shift hours computed, overnight shifts handled (clock-out before clock-in adds 24h), shifts with no clock-out excluded (notebook only)
- [x] First-pass list of people averaging over 45 hours a week, and a first small projection for the in-progress week (notebook only, not final)

## Not done

### The answer (must be correct)
- [ ] Derive the in-progress week from the last date in the data, not today's date, with no hardcoded weekday
- [ ] Prediction for every `employee_id` in `employees.csv`: `will_breach` (0/1) and `risk_score` (0 to 1)
- [ ] Decide and handle: public-holiday hours, overlapping double-site shifts, duplicate employee IDs, missing clock-outs
- [ ] Naive baseline, a comparison against it, and a justified choice of metric
- [ ] `predictions.csv` in the repo with exactly the columns `employee_id,will_breach,risk_score`

### Dashboard
- [ ] Deployed on a public URL that works on a phone
- [ ] Shows who goes over the 10-hour overtime cap by Sunday, ranked, with hours so far and projected hours
- [ ] Says what to do about each person or site, specific to the data (not generic advice)
- [ ] Shows why the hours happened, based on the supervisors' notes

### Supervisor notes
- [ ] Taxonomy of reasons for extra hours, including a "nothing useful" category
- [ ] Overtime split into hours the client asked for versus hours caused by operational failures, and where that split is concentrated
- [ ] Self-designed check of the sorting (hand-labelled sample and/or two methods compared), including where the sorting was wrong
- [ ] `note_classifications.csv` with one row per note in `shift_notes.csv`, exactly the columns `shift_id,category,note`

### Loading new data
- [ ] Upload of a new weekly export (same files, same columns, later week) in the dashboard, with column validation and clear errors
- [ ] Everything reprocesses end to end with no developer and no hardcoded dates, weekdays or employee IDs
- [ ] Regenerated `predictions.csv` and `note_classifications.csv` available to download after an upload

### Repo and submission
- [ ] `NOTES.md`, half a page: assumptions, how the note-sorting was checked and what it found, what a trained model would learn that this approach does not, and how to test it on about 200 people without fooling yourself
- [ ] Public repo (or invite `southafricanrob`) containing the required files; confirm with the client what the "four files" are, since the README lists three
- [ ] Video, 5 minutes, camera on and screen shared: what was unexpected, baseline and metric (and why), where the output is not trusted, what to do next, and one number explained step by step for a non-technical person
- [ ] Three links sent: dashboard, repo, video

### Constraints
- [ ] Free tiers only, no paid API key, runs on a normal laptop
- [ ] Every assumption written down
- [ ] Bank and tax details in `payroll_details.csv` kept out of the dashboard, outputs and video
