# Deploying the dashboard (Streamlit Community Cloud, free)

The app is `app.py` at the repo root. It needs only `requirements.txt` (including `rapidfuzz`, used by the notes sorting in `src/notes.py`) and the bundled `data/` folder.

## One-time setup (about 10 minutes)

1. **Make the repo reachable.** `MistryDev09/JemTechnical` is **public** (the assessment needs it public, or shared with `southafricanrob`).
   - Note: `data/payroll_details.csv` (synthetic bank and tax numbers) is part of the repo as supplied.
2. **Push the code.** Push to the `github` remote only (`origin` is the assessors' repo): `git push github main`.
3. **Create a free Streamlit account** at https://share.streamlit.io and sign in with the GitHub account `MistryDev09`. Allow it to read your repositories.
4. **Create the app:** New app > repository `MistryDev09/JemTechnical`, branch `main`, main file path `app.py`. Under Advanced settings choose **Python 3.12**. Pick a short URL, for example `jem-overtime-watch`. Deploy. The first build takes a few minutes.

## Before you submit the URL

- Open the URL on a laptop and on your phone. You should see "Data up to Wed 12 Aug 2026", 9 people at 50%+ risk, and drop-downs for 30 to 50% (7 people), 20 to 30% (7) and 0 to 20% (185). Each box has a "Why the hours happened" button, and the 50%+ boxes have Resolve next to it.
- On the phone, check the tiles and cards fit the screen and the "Load or update data" section opens.
- Upload a test file, for example a `shifts.csv` with the missing column removed. You should see a clear error.
- Free apps go to sleep after a period with no visitors (commonly around 12 hours; check the Streamlit docs). A visitor then sees a "wake up" button that takes about a minute. **Open the URL shortly before you send it.**
- Optional: ask for a scheduled GitHub Action that visits the app regularly to keep it awake.

## Run it on your laptop

```
pip install -r requirements.txt
streamlit run app.py
```

Regenerate `predictions.csv` from the bundled data: `python -m src.pipeline data predictions.csv` (213 rows, 23 flagged IDs; duplicate and double-dipping people are predicted like everyone else and also escalated).

To run the notebooks and the tests: `pip install -r requirements-dev.txt`, then `pytest tests`. The notebooks are in `notebooks/` and find the repo root themselves.
