"""Breach forecast: who will exceed 55 hours (10 hours of overtime) by Sunday.

One row per person per week. Features are taken at the same cutoff point (an offset from Monday, taken from
the data) in every week, so the training weeks look exactly like the week being predicted. Evaluation is
always forward in time. The model is logistic regression, used only if it clearly beats the simple
baseline B3 (hours so far + the shifts the person usually still has to work); otherwise B3 is used.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CAP = 55                 # a breach is more than 45 ordinary + 10 overtime hours
MIN_WEEKS = 6            # 1 history week + 3 training weeks + 1 test week + the week in progress
MAX_FOLDS = 5
C_GRID = [0.01, 0.03, 0.1, 0.3, 1, 3, 10]
BASE_FEATS = ["hours_so_far", "shifts_so_far", "avg_weekly_hours_prior", "avg_shifts_prior",
              "share_long_shifts_prior", "prior_breaches", "night_pattern"]


@dataclass
class Forecast:
    status: str                       # model | week_complete | not_enough_history
    message: str = ""
    method: str = ""
    features: list = field(default_factory=list)
    threshold: float | None = None
    C: float | None = None
    weeks: pd.DatetimeIndex | None = None
    table: pd.DataFrame | None = None
    current: pd.DataFrame | None = None    # in-progress week, one row per person, with risk_score / will_breach
    folds: pd.DataFrame | None = None
    pooled_pr_auc: dict = field(default_factory=dict)


def build_table(seg, persons, weeks, offset, night=None):
    """Person-week table: label, hours/shifts so far at the cutoff, and history from completed prior weeks only."""
    current_week = weeks[-1]
    seg = seg.copy()
    seg["so_far"] = seg["shift_date"] <= seg["week_start"] + pd.Timedelta(days=offset)
    seg["long"] = seg["hours"] > 11
    t = pd.DataFrame(index=pd.MultiIndex.from_product([persons, weeks], names=["person_key", "week_start"]))
    g = seg.groupby(["person_key", "week_start"])
    gs = seg[seg["so_far"]].groupby(["person_key", "week_start"])
    t["final_hours"] = g["hours"].sum()
    t["shifts"] = g["shift_id"].nunique()
    t["long_shifts"] = g["long"].sum()
    t["hours_so_far"] = gs["hours"].sum()
    t["shifts_so_far"] = gs["shift_id"].nunique()
    t = t.fillna(0)
    t["breach"] = (t["final_hours"] > CAP).astype(float)
    byp = t.groupby(level=0)
    for col in ["final_hours", "shifts", "long_shifts", "breach"]:
        t["prior_" + col] = byp[col].cumsum() - t[col]          # completed prior weeks only
    n_prior = byp.cumcount()
    t["n_prior_weeks"] = n_prior
    t["avg_weekly_hours_prior"] = t["prior_final_hours"] / n_prior.replace(0, np.nan)
    t["avg_shifts_prior"] = t["prior_shifts"] / n_prior.replace(0, np.nan)
    t["share_long_shifts_prior"] = (t["prior_long_shifts"] / t["prior_shifts"].replace(0, np.nan)).fillna(0)
    t["prior_breaches"] = t["prior_breach"]
    global_len = seg["hours"].mean() if len(seg) else 9.5
    t["typical_shift_len"] = (t["prior_final_hours"] / t["prior_shifts"].replace(0, np.nan)).fillna(global_len)
    if night is not None:
        t["night_pattern"] = night.reindex(t.index.get_level_values(0)).fillna(0).to_numpy()
    t["B1"] = t["hours_so_far"]
    t["B2"] = t["hours_so_far"] * 7 / (offset + 1)
    t["B3"] = t["hours_so_far"] + (t["avg_shifts_prior"] - t["shifts_so_far"]).clip(lower=0) * t["typical_shift_len"]
    t["B4"] = t["avg_weekly_hours_prior"]
    t = t.reset_index()
    t.loc[t["week_start"] == current_week, "breach"] = np.nan        # the week being predicted has no label yet
    return t[t["n_prior_weeks"] > 0].reset_index(drop=True)          # the first week only provides history


def _ap(y, s):
    y = np.asarray(y)
    return float(average_precision_score(y, s)) if y.sum() > 0 else float("nan")


def make_model(C):
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000))


def choose_C(tbl, weeks, k, feats):
    """Pick the regularisation with an inner time-split inside the training weeks weeks[1:k] only."""
    scores = {C: [] for C in C_GRID}
    for j in range(max(2, k - 3), k):
        tr = tbl[tbl.week_start.isin(weeks[1:j])]
        te = tbl[tbl.week_start == weeks[j]]
        if tr.breach.sum() < 3 or te.breach.sum() < 1:
            continue
        for C in C_GRID:
            m = make_model(C).fit(tr[feats], tr.breach)
            scores[C].append(_ap(te.breach, m.predict_proba(te[feats])[:, 1]))
    valid = {C: np.mean(v) for C, v in scores.items() if v}
    return max(valid, key=valid.get) if valid else 1


def test_indices(n_weeks):
    """Test weeks: the last (up to 5) complete weeks, each needing at least 3 training weeks before it."""
    return list(range(max(4, (n_weeks - 1) - MAX_FOLDS), n_weeks - 1))


def rolling_cv(tbl, weeks, feats, test_idx):
    """Expanding window: train on weeks 2..k, test on the next week. Never random."""
    out = []
    for k in test_idx:
        tr = tbl[tbl.week_start.isin(weeks[1:k])]
        te = tbl[tbl.week_start == weeks[k]]
        if tr.breach.nunique() < 2:
            score = np.full(len(te), float(tr.breach.mean()) if len(tr) else 0.0)
            C = 1
        else:
            C = choose_C(tbl, weeks, k, feats)
            score = make_model(C).fit(tr[feats], tr.breach).predict_proba(te[feats])[:, 1]
        out.append(te[["person_key", "week_start", "breach"]].assign(score=score, fold=k + 1, C=C))
    return pd.concat(out)


def baseline_oof(tbl, weeks, col, test_idx):
    te = tbl[tbl.week_start.isin([weeks[k] for k in test_idx])]
    folds = {weeks[k]: k + 1 for k in test_idx}
    return te[["person_key", "week_start", "breach"]].assign(score=te[col].to_numpy(), fold=te.week_start.map(folds).to_numpy())


def f2_at(y, flag):
    tp = ((flag == 1) & (y == 1)).sum()
    fp = ((flag == 1) & (y == 0)).sum()
    fn = ((flag == 0) & (y == 1)).sum()
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return (5 * p * r / (4 * p + r) if p + r else 0.0), p, r


def best_threshold(y, s):
    """Score cut-off that maximises F2 (recall counts more than precision) on out-of-fold predictions."""
    cands = np.unique(s)
    return float(cands[int(np.argmax([f2_at(y.values, (s.values >= c).astype(int))[0] for c in cands]))])


def forecast(seg, persons, night, current_week, offset):
    """Run the forecast for the week in progress.

    seg: attributed segments with columns shift_id, person_key, shift_date, week_start, hours.
    night: person_key -> 1 if night pattern (None if unknown). offset: days after Monday the data stops.
    """
    seg = seg[seg["week_start"] <= current_week]
    weeks = pd.date_range(seg["week_start"].min(), current_week, freq="7D")
    n = len(weeks)
    feats = [f for f in BASE_FEATS if night is not None or f != "night_pattern"]
    out = Forecast(status="not_enough_history", features=feats, weeks=weeks)

    if offset == 6:
        out.status = "week_complete"
        out.message = "The data runs to Sunday, so the week is complete. These are the people who actually went over."
        return out
    if n < MIN_WEEKS:
        out.message = f"The shifts cover {n} week(s) including the week in progress. At least {MIN_WEEKS} are needed to train the model."
        return out

    table = build_table(seg, persons, weeks, offset, night)
    out.table = table
    train = table[(table.week_start > weeks[0]) & (table.week_start < current_week)]
    if train.breach.sum() < 3:
        out.message = "There are too few past weeks with a breach (fewer than 3) to train the model."
        return out

    test_idx = test_indices(n)
    oof_lr = rolling_cv(table, weeks, feats, test_idx)
    oof_b3 = baseline_oof(table, weeks, "B3", test_idx)
    lr_f = [_ap(g.breach, g.score) for _, g in oof_lr.groupby("fold")]
    b3_f = [_ap(g.breach, g.score) for _, g in oof_b3.groupby("fold")]
    pooled_lr, pooled_b3 = _ap(oof_lr.breach, oof_lr.score), _ap(oof_b3.breach, oof_b3.score)
    folds_won = sum(a > b for a, b in zip(lr_f, b3_f))
    lr_wins = bool(np.isnan(pooled_lr) or (pooled_lr > pooled_b3 and folds_won * 2 > len(lr_f)))

    final_feats = feats if lr_wins else ["B3"]
    oof_final = oof_lr if lr_wins else rolling_cv(table, weeks, ["B3"], test_idx)
    threshold = best_threshold(oof_final.breach, oof_final.score)
    C = choose_C(table, weeks, n - 1, final_feats)
    model = make_model(C).fit(train[final_feats], train.breach)
    cur = table[table.week_start == current_week].copy()
    cur["risk_score"] = model.predict_proba(cur[final_feats])[:, 1]
    cur["will_breach"] = (cur["risk_score"] >= threshold).astype(int)

    folds = pd.DataFrame({
        "test_week": [weeks[k] for k in test_idx],
        "train_weeks": [f"2-{k}" for k in test_idx],
        "test_breaches": [int(g.breach.sum()) for _, g in oof_lr.groupby("fold")],
        "pr_auc_model": lr_f, "pr_auc_b3": b3_f})
    out.status = "model"
    out.method = "Logistic regression" if lr_wins else "Projection from usual shifts (B3), calibrated"
    out.features, out.threshold, out.C, out.current, out.folds = final_feats, threshold, C, cur, folds
    out.pooled_pr_auc = {"model": pooled_lr, "b3": pooled_b3, "folds_won": folds_won, "folds": len(lr_f)}
    return out
