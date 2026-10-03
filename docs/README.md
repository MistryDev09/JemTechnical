# Docs

| File | What it is |
|---|---|
| [`assumptions.md`](assumptions.md) | Every assumption made, grouped as made / inferred / not yet decided |
| [`REQUIREMENTS.md`](REQUIREMENTS.md) | What the final project needs, split into done and not done |
| [`DEPLOY.md`](DEPLOY.md) | Putting the dashboard on Streamlit Community Cloud, and running it locally |

Two files stay at the repo root because the assessment asks for them there: `README.md` (the brief) and `NOTES.md` (the short write-up), next to `predictions.csv` and `note_classifications.csv`.

## Where things are

| Folder | Contents |
|---|---|
| `app.py`, `requirements.txt`, `.streamlit/` | The dashboard. They stay at the root because Streamlit Cloud deploys `app.py` from there |
| `src/` | The code the dashboard uses: hours, duplicates and overlaps, the model, the notes sorting (`notes.py` is the one place to edit the rules), validation, loading |
| `notebooks/` | `data_modeling.ipynb` (the breach model and its tests), `cost_analysis.ipynb` (the client's counting against ours, in money), `shift_classification.ipynb` (sorting the supervisor notes and checking it). Each finds the repo root itself, so it can be run from anywhere |
| `evaluation/` | Helpers for the notes check, and the hand labels in `evaluation/labels/` |
| `data/` | The client's files, plus `shift_notes_labelled.csv` (the supplied labels) |
| `tests/` | `pytest tests` |
