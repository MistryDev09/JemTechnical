"""Integrity flags: duplicate people, overlapping shifts, two provinces on one day and shifts that do not match the shift pattern. These only report; hours are never removed.

Wording is deliberately "potential" and "for review": a flag is a reason to escalate, not a finding.
Bank account and tax number values are compared in memory and never appear in any output.
"""
import pandas as pd

OVERLAP_FLAG = "Potential fraud: two sites at once"


def find_duplicate_people(employees, payroll=None):
    """Group employee IDs that share an ID number, bank account or tax number.

    Severity is "Escalate" when a bank account or tax number is shared, "Review" when only the
    ID number is. Works without payroll (ID-number evidence only). Returns one row per group.
    """
    ids = employees[["employee_id", "full_name", "id_number"]].copy()
    if payroll is not None:
        ids = ids.merge(payroll[["employee_id", "account_number", "tax_number"]], on="employee_id", how="left")
    fields = [("id_number", "ID number"), ("account_number", "bank account"), ("tax_number", "tax number")]
    fields = [f for f in fields if f[0] in ids.columns]

    parent = {e: e for e in ids["employee_id"]}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for col, _ in fields:
        for _, group in ids.dropna(subset=[col]).groupby(col):
            members = list(group["employee_id"])
            for other in members[1:]:
                parent[find(other)] = find(members[0])

    ids["group"] = ids["employee_id"].map(find)
    rows = []
    for _, g in ids.groupby("group"):
        if len(g) < 2:
            continue
        g = g.sort_values("employee_id")
        shared = {label: bool(g[col].dropna().duplicated().any()) for col, label in fields}
        escalate = shared.get("bank account", False) or shared.get("tax number", False)
        rows.append({
            "person_key": g["employee_id"].iloc[0],
            "employee_ids": list(g["employee_id"]),
            "names": list(g["full_name"]),
            "shared_id_number": shared.get("ID number", False),
            "shared_bank_account": shared.get("bank account", False),
            "shared_tax_number": shared.get("tax number", False),
            "evidence": "; ".join(f"same {label}" for label, hit in shared.items() if hit),
            "severity": "Escalate" if escalate else "Review",
        })
    columns = ["person_key", "employee_ids", "names", "shared_id_number", "shared_bank_account",
               "shared_tax_number", "evidence", "severity"]
    return pd.DataFrame(rows, columns=columns).sort_values("person_key").reset_index(drop=True)


def add_person_key(df, people):
    """Add `person_key` so hours can be summed across all employee IDs of one person."""
    mapping = {eid: row.person_key for row in people.itertuples() for eid in row.employee_ids}
    out = df.copy()
    out["person_key"] = out["employee_id"].map(mapping).fillna(out["employee_id"])
    return out


def find_overlaps(shifts, sites, people=None):
    """Pairs of valid shifts that overlap in time for the same person (all IDs of a person together).

    `shifts` is the output of `hours.parse_shifts`. Hours stay counted; this only reports.
    Severity is High when the two sites are in different provinces, otherwise Medium.
    """
    valid = shifts[~shifts["excluded"]]
    if people is not None:
        valid = add_person_key(valid, people)
    else:
        valid = valid.assign(person_key=valid["employee_id"])
    province = sites.set_index("site_id")["province"]

    rows = []
    for person, g in valid.sort_values("start").groupby("person_key"):
        recs = g.to_dict("records")
        for i, a in enumerate(recs):
            for b in recs[i + 1:]:
                if b["start"] >= a["end"]:
                    break
                overlap = (min(a["end"], b["end"]) - b["start"]).total_seconds() / 3600
                pa, pb = province.get(a["site_id"]), province.get(b["site_id"])
                different = pd.notna(pa) and pd.notna(pb) and pa != pb
                rows.append({
                    "person_key": person,
                    "kind": "same_id" if a["employee_id"] == b["employee_id"] else "cross_id",
                    "shift_id_a": a["shift_id"], "shift_id_b": b["shift_id"],
                    "employee_id_a": a["employee_id"], "employee_id_b": b["employee_id"],
                    "site_a": a["site_id"], "site_b": b["site_id"],
                    "province_a": pa, "province_b": pb,
                    "start_a": a["start"], "end_a": a["end"], "start_b": b["start"], "end_b": b["end"],
                    "overlap_hours": overlap,
                    "different_province": different,
                    "severity": "High" if different else "Medium",
                    "flag": OVERLAP_FLAG,
                })
    columns = ["person_key", "kind", "shift_id_a", "shift_id_b", "employee_id_a", "employee_id_b",
               "site_a", "site_b", "province_a", "province_b", "start_a", "end_a", "start_b", "end_b",
               "overlap_hours", "different_province", "severity", "flag"]
    return pd.DataFrame(rows, columns=columns).sort_values(["person_key", "start_a"]).reset_index(drop=True)


def find_cross_province_days(segments, sites):
    """People with hours at two different sites in different provinces on the same (attributed) day.

    `segments` is the output of `hours.attribute_hours` with a `person_key` (see `add_person_key`); `sites` has site_id and
    province. Returns one row per person-day. Empty when there is no province information. Only reports; hours stay counted.
    """
    columns = ["person_key", "attributed_date", "week_start", "sites"]
    if sites is None or "province" not in sites or sites["province"].isna().all():
        return pd.DataFrame(columns=columns)
    province = sites.set_index("site_id")["province"]
    d = segments.assign(province=segments["site_id"].map(province)).dropna(subset=["province"])
    g = d.groupby(["person_key", "attributed_date"]).agg(week_start=("week_start", "first"), sites=("site_id", "nunique"),
                                                         provinces=("province", "nunique")).reset_index()
    return g[g["provinces"] > 1][columns].reset_index(drop=True)


def find_pattern_mismatches(shifts, employees):
    """Overnight shifts (by the times) for employees whose shift_pattern is not "night".

    `shifts` is the output of `hours.parse_shifts`. A clock-in 18:00 and clock-out 06:00 confirms a night-pattern employee; the same
    shift for a day-pattern employee is flagged for review. Hours stay counted. Shifts with no clock-out are never judged (no clock-out
    is made up), and nothing is flagged when the pattern is missing or there is no employees file. The reverse (night pattern, shift
    not overnight) is deliberately not flagged.
    """
    columns = ["shift_id", "employee_id", "site_id", "shift_date", "clock_in_time", "clock_out_time", "shift_pattern", "hours"]
    if employees is None or "shift_pattern" not in employees:
        return pd.DataFrame(columns=columns)
    pattern = employees.drop_duplicates("employee_id").set_index("employee_id")["shift_pattern"].astype("string").str.strip().str.lower()
    d = shifts[~shifts["excluded"] & shifts["is_overnight"]].copy()
    d["shift_pattern"] = d["employee_id"].map(pattern)
    d = d[d["shift_pattern"].notna() & (d["shift_pattern"] != "night")]
    d["hours"] = d["duration_hours"]
    return d[columns].sort_values(["shift_date", "employee_id"]).reset_index(drop=True)
