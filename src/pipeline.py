"""End to end: from the current files to what the dashboard shows. Only parts with their information are filled in.

Run from the command line to regenerate predictions.csv:  python -m src.pipeline data predictions.csv
"""
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .forecast import CAP, MIN_WEEKS, forecast
from .hours import attribute_hours, data_cutoff, parse_shifts, quality_report
from .integrity import add_person_key, find_duplicate_people, find_overlaps
from .notes import classify_notes
from .validate import cross_check

HIGH_RISK = 0.5      # shown as a card with a Resolve button
WATCH_RISK = 0.3     # 30% to 50%: shown in the first drop-down
MID_RISK = 0.2       # 20% to 30%: second drop-down; below 20% is the last one
KINDS = ("shifts", "employees", "sites", "public_holidays", "shift_notes", "payroll_details")
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class Result:
    status: str                          # model | week_complete | not_enough_history | no_shifts
    message: str = ""
    available: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    cutoff: pd.Timestamp | None = None
    week_start: pd.Timestamp | None = None
    week_end: pd.Timestamp | None = None
    predicted_days: list = field(default_factory=list)
    people: pd.DataFrame | None = None           # one row per person (merged duplicates together)
    sites: pd.DataFrame | None = None            # by-site summary
    predictions: pd.DataFrame | None = None      # employee_id, will_breach, risk_score
    duplicates: pd.DataFrame | None = None
    overlaps: pd.DataFrame | None = None
    overlaps_current: pd.DataFrame | None = None
    open_shifts: pd.DataFrame | None = None
    quality: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)
    site_labels: dict = field(default_factory=dict)
    n_weeks: int = 0
    reasons: pd.DataFrame | None = None          # supervisor notes joined to a person: person_key, shift_date, site_id, category, note, this_week
    note_classes: pd.DataFrame | None = None     # shift_id, category, note for every note (the note_classifications.csv columns)


def _has(bundle, kind):
    return kind in bundle and bundle[kind] is not None and len(bundle[kind]) > 0


def _label(site_id, names):
    return f"{site_id} {names[site_id]}" if site_id in names else str(site_id)


def run(bundle):
    avail = {k: _has(bundle, k) for k in KINDS}
    res = Result(status="no_shifts", available=avail, warnings=cross_check(bundle))
    if not avail["shifts"]:
        res.message = "No shifts are loaded. Load shifts.csv to see this week's hours and predictions."
        return res

    sh = parse_shifts(bundle["shifts"])
    cutoff = data_cutoff(sh)
    if pd.isna(cutoff) or sh["excluded"].all():
        res.message = "None of the loaded shifts has a readable date and clock times, so there is nothing to show."
        return res

    employees = bundle["employees"] if avail["employees"] else None
    sites = bundle["sites"] if avail["sites"] else None
    payroll = bundle["payroll_details"] if avail["payroll_details"] else None
    holidays = bundle["public_holidays"] if avail["public_holidays"] else None

    # --- who is the same person (shared ID number, bank account or tax number)
    if employees is not None:
        emp_frame = employees[["employee_id", "full_name", "id_number"]]
    elif payroll is not None:
        emp_frame = pd.DataFrame({"employee_id": sorted(set(sh["employee_id"].dropna())), "full_name": np.nan, "id_number": np.nan})
    else:
        emp_frame = pd.DataFrame(columns=["employee_id", "full_name", "id_number"])
    dups = find_duplicate_people(emp_frame, payroll)
    person_of_map = {eid: row.person_key for row in dups.itertuples() for eid in row.employee_ids}
    person_of = lambda eid: person_of_map.get(eid, eid)

    # --- hours attributed to a day and week (greater-portion rule), per person
    segments = add_person_key(attribute_hours(sh, holidays), dups)
    seg = segments.merge(sh[["shift_id", "shift_date"]], on="shift_id")[["shift_id", "person_key", "shift_date", "week_start", "hours"]]
    current_week = cutoff - pd.Timedelta(days=cutoff.weekday())
    offset = cutoff.weekday()
    seg = seg[seg["week_start"] <= current_week]
    emp_ids = list(employees["employee_id"]) if employees is not None else sorted(set(sh["employee_id"].dropna()))
    persons = sorted({person_of(e) for e in emp_ids} | set(seg["person_key"]))

    night = None
    if employees is not None and "shift_pattern" in employees and employees["shift_pattern"].notna().any():
        flagged = employees.assign(person_key=employees["employee_id"].map(person_of), n=employees["shift_pattern"].str.lower().eq("night"))
        night = flagged.groupby("person_key")["n"].max().astype(int)

    fc = forecast(seg, persons, night, current_week, offset)

    # --- the week in progress, per person
    cur_seg = seg[seg["week_start"] == current_week]
    basics = cur_seg.groupby("person_key").agg(hours_so_far=("hours", "sum"), shifts_so_far=("shift_id", "nunique"))
    people = pd.DataFrame(index=pd.Index(persons, name="person_key")).join(basics).fillna({"hours_so_far": 0.0, "shifts_so_far": 0})
    usual = seg[seg["week_start"] < current_week].groupby("person_key")["hours"].mean()
    people["usual_shift_hours"] = usual.reindex(people.index).fillna(seg["hours"].mean())
    if fc.current is not None:
        people = people.join(fc.current.set_index("person_key")[["risk_score", "will_breach", "typical_shift_len", "avg_weekly_hours_prior", "prior_breaches"]])
        people["usual_shift_hours"] = people["typical_shift_len"].fillna(people["usual_shift_hours"])
        people = people.drop(columns="typical_shift_len").rename(columns={"avg_weekly_hours_prior": "avg_weekly_hours", "prior_breaches": "past_breaches"})
    else:
        people["risk_score"], people["will_breach"] = np.nan, np.nan
        people["avg_weekly_hours"], people["past_breaches"] = np.nan, np.nan
    people["hours_left"] = (CAP - people["hours_so_far"]).clip(lower=0)
    people["shifts_left"] = np.floor(people["hours_left"] / people["usual_shift_hours"].clip(lower=1)).astype(int)    # fit under the cap
    # what the person usually still works this week: usual shifts per week minus shifts already worked, times the usual shift length
    n_prior = max(len(pd.date_range(seg["week_start"].min(), current_week, freq="7D")) - 1, 1)
    prior_counts = seg[seg["week_start"] < current_week].groupby(["person_key", "week_start"])["shift_id"].nunique().groupby(level=0).sum()
    people["usual_shifts_per_week"] = prior_counts.reindex(people.index).fillna(0) / n_prior
    people["usual_shifts_left"] = (people["usual_shifts_per_week"] - people["shifts_so_far"]).clip(lower=0)
    people["usual_hours_to_go"] = people["usual_shifts_left"] * people["usual_shift_hours"]
    over = people["hours_so_far"] > CAP
    if fc.status == "model":
        risk = people["risk_score"]
        people["level"] = np.where(over | (risk >= HIGH_RISK), "High", np.where(risk >= WATCH_RISK, "Watch", np.where(people["will_breach"] == 1, "Flagged", "Low")))
        people["will_breach"] = (people["will_breach"].fillna(0).astype(int) | over.astype(int))
    elif fc.status == "week_complete":
        people["level"] = np.where(over, "Over", "OK")
        people["will_breach"] = over.astype(int)
    else:
        people["level"] = np.where(over, "Over", "Unknown")
        people["will_breach"] = over.astype(int)
    # the groups shown on the dashboard, by score (a person already over the cap is always in the top group)
    risk = people["risk_score"].fillna(0.0)
    people["band"] = np.where(over | (risk >= HIGH_RISK), "High", np.where(risk >= WATCH_RISK, "Watch", np.where(risk >= MID_RISK, "Mid", "Low")))

    # --- names, roles, sites
    site_names = dict(zip(sites["site_id"], sites["site_name"])) if sites is not None else {}
    ids_by_person = {}
    for e in sorted(set(emp_ids) | set(sh["employee_id"].dropna())):
        ids_by_person.setdefault(person_of(e), []).append(e)
    info = employees.set_index("employee_id") if employees is not None else None

    def describe(key):
        ids = ids_by_person.get(key, [key])
        names = [str(info.at[i, "full_name"]) for i in ids if info is not None and i in info.index and pd.notna(info.at[i, "full_name"])]
        names = sorted(names, key=len, reverse=True)
        roles = [info.at[i, "role"] for i in ids if info is not None and "role" in info and i in info.index and pd.notna(info.at[i, "role"])]
        prim = sorted({info.at[i, "primary_site_id"] for i in ids if info is not None and "primary_site_id" in info and i in info.index and pd.notna(info.at[i, "primary_site_id"])})
        return pd.Series({"employee_ids": ids, "name": names[0] if names else key, "also_known_as": names[1:],
                          "role": roles[0] if roles else "", "primary_sites": prim})

    people = people.join(pd.Series(people.index, index=people.index).apply(describe))
    open_mask = sh["excluded"] & ~sh["invalid_date"] & (sh["shift_date"] >= current_week) & (sh["invalid_clock_out"] | sh["invalid_clock_in"])
    cur_ids = set(cur_seg["shift_id"]) | set(sh.loc[open_mask, "shift_id"])
    worked = sh[sh["shift_id"].isin(cur_ids)].assign(person_key=lambda d: d["employee_id"].map(person_of)).groupby("person_key")["site_id"].agg(lambda s: sorted(set(s.dropna())))
    people["sites_worked"] = worked.reindex(people.index).apply(lambda v: v if isinstance(v, list) else [])
    people = people.sort_values(["will_breach", "risk_score", "hours_so_far"], ascending=False).reset_index()

    # --- by-site summary
    flagged_levels = {"High", "Flagged", "Over"}
    site_rows = []
    for site in sorted({s for lst in people["sites_worked"] for s in lst}):
        here = people[people["sites_worked"].apply(lambda lst: site in lst)]
        site_rows.append({"site_id": site, "site": _label(site, site_names), "working": len(here),
                          "flagged": int(here["level"].isin(flagged_levels).sum()),
                          "high_risk": int((here["level"].isin({"High", "Over"})).sum())})
    sites_summary = pd.DataFrame(site_rows, columns=["site_id", "site", "working", "flagged", "high_risk"])
    sites_summary = sites_summary.sort_values(["flagged", "high_risk", "working"], ascending=False).reset_index(drop=True)

    # --- integrity flags
    sites_frame = sites if sites is not None else pd.DataFrame({"site_id": sorted(set(sh["site_id"].dropna())), "province": None})
    overlaps = find_overlaps(sh, sites_frame, dups)
    overlaps_now = overlaps[overlaps["start_a"].dt.normalize() >= current_week].reset_index(drop=True)
    open_shifts = sh.loc[open_mask, ["shift_id", "employee_id", "site_id", "shift_date", "clock_in_time", "clock_out_time"]].reset_index(drop=True)

    # --- why the hours happened: the supervisors' notes, sorted into reasons and attached to the person
    reasons, note_classes = None, None
    if avail["shift_notes"]:
        note_classes = classify_notes(bundle["shift_notes"][["shift_id", "note"]].astype({"shift_id": str}).fillna({"note": ""}))
        joined = note_classes.merge(sh[["shift_id", "employee_id", "site_id", "shift_date"]], on="shift_id", how="inner")
        joined["person_key"] = joined["employee_id"].map(person_of)
        joined["this_week"] = joined["shift_date"] >= current_week
        reasons = joined.drop(columns="employee_id").sort_values("shift_date", ascending=False).reset_index(drop=True)

    # --- employee-level predictions (both IDs of a merged person get the same values)
    predictions = None
    if fc.status == "model":
        by_person = people.set_index("person_key")[["will_breach", "risk_score"]]
        pred = pd.DataFrame({"employee_id": sorted(set(emp_ids))})
        pred = pred.join(by_person, on=pred["employee_id"].map(person_of))
        predictions = pd.DataFrame({
            "employee_id": pred["employee_id"],
            "will_breach": pred["will_breach"].fillna(0).astype(int),
            "risk_score": pred["risk_score"].fillna(0.0).round(4)}).reset_index(drop=True)

    res.status, res.message = fc.status, fc.message
    res.cutoff, res.week_start, res.week_end = cutoff, current_week, current_week + pd.Timedelta(days=6)
    res.predicted_days = DAY_NAMES[offset + 1:]
    res.people, res.sites, res.predictions = people, sites_summary, predictions
    res.duplicates, res.overlaps, res.overlaps_current, res.open_shifts = dups, overlaps, overlaps_now, open_shifts
    res.quality = quality_report(sh)
    res.site_labels = {s: _label(s, site_names) for s in set(sh["site_id"].dropna()) | set(site_names) | {x for lst in people["primary_sites"] for x in lst}}
    res.n_weeks = len(fc.weeks) if fc.weeks is not None else 0
    res.reasons, res.note_classes = reasons, note_classes
    res.model = {"method": fc.method, "threshold": fc.threshold, "C": fc.C, "features": fc.features,
                 "folds": fc.folds, "pooled_pr_auc": fc.pooled_pr_auc, "min_weeks": MIN_WEEKS}
    return res


def main(argv):
    from .dataset import load_bundled
    from .export import predictions_csv
    folder = argv[1] if len(argv) > 1 else "data"
    out = argv[2] if len(argv) > 2 else "predictions.csv"
    result = run(load_bundled(folder))
    if result.status != "model":
        raise SystemExit(f"No prediction was made: {result.message}")
    with open(out, "w", newline="") as f:
        f.write(predictions_csv(result))
    flagged = int(result.predictions["will_breach"].sum())
    print(f"Wrote {out}: {len(result.predictions)} employees, {flagged} flagged (data to {result.cutoff:%a %d %b %Y}).")


if __name__ == "__main__":
    main(sys.argv)
