"""Check of the note sorting against a hand-labelled sample.

Shared helpers for `shift_classification.ipynb`: text normalisation, collapsing the notes to templates,
drawing the blind samples to hand-label, and scoring a classifier against those labels.
Nothing here classifies a note; the classifiers live in the notebook.
"""
import difflib
import re

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from src.notes import normalise   # one normaliser for the classifier, the dashboard and this check

SEED = 0
N_RANDOM, N_MINORITY, N_TYPO = 120, 40, 45
COMMON_MIN_ROWS = 10           # a spelling used in at least this many rows counts as a common spelling
MINORITY_MAX_ROWS = 30          # a template cluster with fewer rows than this counts as a minority template
CLUSTER_DISTANCE = 1.0          # average-linkage cut on char n-gram TF-IDF; gives about 68 clusters on the bundled notes


def surname_set(employees):
    return {normalise(n.split()[-1]) for n in employees["full_name"]}


def mask(norm_text, surnames):
    """Replace known surnames (also with the isiZulu u prefix) by NAME and numbers and times by #, so the same sentence with another name is one template."""
    # isiZulu writes a person as u + surname ("uMavuso"), so a leading u is allowed
    words = ["NAME" if (w in surnames or (w.startswith("u") and w[1:] in surnames)) else w for w in norm_text.split()]
    text = " ".join(words)
    text = re.sub(r"\b(\d+(h\d*|am)?|six|seven|five)\b", "#", text)      # 6, 06h00, 0h600, 6am, six: all a time or a count
    return re.sub(r"(#\s*)+", "# ", text).strip()


def template_clusters(masked, distance=CLUSTER_DISTANCE):
    """Group the masked notes (typo variants of the same sentence) into templates.

    Returns a Series indexed like `masked` with a cluster id (-1 for empty notes) and the most frequent member of each
    cluster, which is used as its template text.
    """
    counts = masked[masked.str.len() > 0].value_counts().rename_axis("masked").reset_index(name="n")
    x = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit_transform(counts["masked"]).toarray()
    counts["cluster"] = AgglomerativeClustering(n_clusters=None, distance_threshold=distance, metric="euclidean",
                                                linkage="average").fit_predict(x)
    ids = masked.map(counts.set_index("masked")["cluster"]).fillna(-1).astype(int)
    template = counts.sort_values("n", ascending=False).groupby("cluster")["masked"].first()
    return ids, template


def draw_blind_samples(notes, masked, clusters, template, seed=SEED):
    """Three samples of rows to hand-label before any classifier is run: random, minority templates, typo-dense.

    `notes` has shift_id and note; `masked` and `clusters` are aligned with it. Rows never appear in two samples.
    """
    rng = np.random.default_rng(seed)
    idx = np.arange(len(notes))
    random_rows = rng.choice(idx, N_RANDOM, replace=False)

    size = clusters.map(clusters.value_counts())
    minority_pool = np.setdiff1d(idx[(clusters >= 0) & (size < MINORITY_MAX_ROWS)], random_rows)
    minority_rows = rng.choice(minority_pool, N_MINORITY, replace=False)

    # typo-dense: rare spellings that are least like any common spelling of a sentence
    freq = masked.value_counts()
    common = [m for m, n in freq.items() if n >= COMMON_MIN_ROWS and m]
    cache = {}
    def similarity_to_common(m):
        if freq[m] >= COMMON_MIN_ROWS or not m:
            return 1.0
        if m not in cache:
            cache[m] = max(difflib.SequenceMatcher(None, m, c).ratio() for c in common)
        return cache[m]
    similarity = np.array([similarity_to_common(m) for m in masked])
    taken = set(random_rows) | set(minority_rows)
    order = [i for i in np.argsort(similarity + rng.random(len(similarity)) * 1e-6) if i not in taken]
    typo_rows = np.array(order[:N_TYPO])

    out = pd.concat([notes.iloc[rows][["shift_id", "note"]].assign(sample=name)
                     for name, rows in [("random", random_rows), ("minority_template", minority_rows), ("typo_dense", typo_rows)]])
    return out.reset_index(drop=True)


def accuracy_table(labels, predictions, by="sample"):
    """Share of rows where the predicted category equals the hand label, per sample and overall."""
    d = labels.merge(predictions, on="shift_id", suffixes=("_hand", "_pred"))
    d["ok"] = d["category_hand"] == d["category_pred"]
    t = d.groupby(by)["ok"].agg(rows="size", correct="sum")
    t["accuracy"] = t["correct"] / t["rows"]
    t.loc["all"] = [len(d), int(d["ok"].sum()), d["ok"].mean()]
    return t, d
