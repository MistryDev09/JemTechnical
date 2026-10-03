"""Sorting of the supervisors' notes into reasons for the extra hours.

This is the one place to change the sorting. The dashboard, `shift_classification.ipynb` and
`note_classifications.csv` all use it, so an edit here shows up in all three.

How it works: the note is normalised (lowercase, no accents or punctuation, no spell-correction because that
mangles Afrikaans and isiZulu) and matched against ordered keyword rules. A keyword matches if the note contains
something close to it, so typos still hit. The first rule that matches wins, so put the more important rule first:
a failure cue (relief, handover, equipment) beats a client cue.
"""
import re
import unicodedata

import pandas as pd
from rapidfuzz import fuzz, process
from rapidfuzz.distance import OSA, Levenshtein

# --- the categories (the keys are what note_classifications.csv contains) ------------------------------------

CATEGORY_LABELS = {
    "client_requested": "Client asked for it",
    "client_unconfirmed": "Client asked, approval unknown",
    "relief_no_show": "Relief did not arrive or was late",
    "colleague_no_show": "Colleague did not come in",
    "late_handover": "Late handover",
    "equipment_failure": "Equipment or site failure",
    "colleague_sick_or_leave": "Colleague sick or on leave",
    "stood_in_unspecified": "Covered for someone, no reason given",
    "nothing_useful": "Nothing useful in the note",
    "unknown": "Unclear",
}

PILE = {
    "client_requested": "client",
    "client_unconfirmed": "client",
    "relief_no_show": "operational",
    "colleague_no_show": "operational",
    "late_handover": "operational",
    "equipment_failure": "operational",
    "colleague_sick_or_leave": "absence",
    "stood_in_unspecified": "absence",
    "nothing_useful": "none",
    "unknown": "none",
}

PILE_LABELS = {"client": "Client asked", "operational": "Operational failure", "absence": "Absence cover", "none": "No information"}

# --- the rules (edit here) ------------------------------------------------------------------------------------

# a short note that is one of these (or close to it) says nothing useful
NOTHING = ["ok", "fine", "all fine", "all good", "all quiet", "quiet shift", "ntr", "n a", "na", "sharp", "nothing to report",
           "no incidents", "no issues on site", "as per normal", "niks om te rapporteer nie", "akukho lutho"]

# (category, keywords); the first rule that matches wins. Keywords are English, Afrikaans or isiZulu, lowercase, no punctuation.
RULES = [
    ("relief_no_show",          ["relief", "aflos", "replacement", "akafikanga", "next shift guard"]),
    ("late_handover",           ["handover", "hand over", "oorhandiging"]),
    ("equipment_failure",       ["machine", "masjien", "scrubber", "generator", "lift", "gate motor", "out of order", "kaput", "stukkend", "broke down"]),
    ("colleague_sick_or_leave", ["sick", "siek", "family responsibility", "clinic", "leave", "booked off"]),
    ("colleague_no_show",       ["no show", "didnt come", "did not come", "absent", "akezanga"]),
    ("client_unconfirmed",      ["dont know if office approved"]),
    ("client_requested",        ["client", "klient", "centre manager", "centre management", "site manager", "site mgr", "centre mgr",
                                 "requested", "approved", "signed off", "stocktake"]),
    ("stood_in_unspecified",    ["stood in", "covered for", "covering", "took shift", "shift as well"]),
]

# --- the matcher ----------------------------------------------------------------------------------------------


def normalise(text):
    """Lowercase, drop accents and punctuation, collapse spaces."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _word_in(word, tokens):
    # a word matches a token exactly, or with one typo (insert, delete, swap, change) if the word has 5+ letters,
    # or, if it has 4 letters, with one letter dropped, added or swapped with its neighbour (not changed).
    # Words of 3 letters or fewer must match exactly.
    if not tokens:
        return False
    if word in tokens:
        return True
    if len(word) <= 3:
        return False
    for t in tokens:
        if abs(len(t) - len(word)) > 2:
            continue
        if len(word) == 4:
            if OSA.distance(word, t) == 1 and (len(t) != 4 or Levenshtein.distance(word, t) == 2):
                return True
        elif OSA.normalized_similarity(word, t) >= 0.8:
            return True
    return False


def _has(text, keyword, tokens):
    # a phrase matches if every one of its words is found, or the whole phrase is found with a few typos
    return all(_word_in(w, tokens) for w in keyword.split()) or (" " in keyword and fuzz.partial_ratio(keyword, text) >= 90)


def _is_nothing(text):
    if text == "":
        return True
    return len(text.split()) <= 6 and process.extractOne(text, NOTHING, scorer=fuzz.ratio, score_cutoff=85) is not None


def classify_text(norm_text, rules=None):
    """Category of one already-normalised note. Anything no rule matches is 'unknown', never silently a category."""
    if _is_nothing(norm_text):
        return "nothing_useful"
    tokens = norm_text.split()
    for category, keywords in (rules or RULES):
        if any(_has(norm_text, k, tokens) for k in keywords):
            return category
    return "unknown"


def classify(text, rules=None):
    return classify_text(normalise(text), rules)


def classify_notes(notes, rules=None):
    """notes has shift_id and note. Returns shift_id, category, note (the columns of note_classifications.csv).

    Each distinct normalised text is classified once, so the cost is the number of distinct sentences, not rows.
    """
    norm = notes["note"].map(normalise)
    by_text = {t: classify_text(t, rules) for t in norm.unique()}
    return pd.DataFrame({"shift_id": notes["shift_id"].to_numpy(), "category": norm.map(by_text).to_numpy(),
                         "note": notes["note"].to_numpy()})
