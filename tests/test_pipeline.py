import pandas as pd
import pytest

from src.dataset import load_bundled
from src.export import predictions_csv
from src.pipeline import run


@pytest.fixture(scope="module")
def bundle():
    return load_bundled()


@pytest.fixture(scope="module")
def full(bundle):
    return run(bundle)


def test_predictions_csv_is_what_the_pipeline_produces(full):
    expected = pd.read_csv("predictions.csv")
    got = full.predictions
    assert list(got.columns) == ["employee_id", "will_breach", "risk_score"]
    assert (got.employee_id.values == expected.employee_id.values).all()
    assert (got.will_breach.values == expected.will_breach.values).all()
    assert (got.risk_score - expected.risk_score).abs().max() < 1e-9
    assert len(got) == 213 and int(got.will_breach.sum()) == 23


DUPLICATE_PEOPLE = {"E1035", "E1090", "E1097", "E1126", "E1193"}
DOUBLE_DIPPING = {"E1099", "E1100", "E1104", "E1111", "E1140", "E1143", "E1152", "E1202", "E1213"}


def test_duplicate_and_double_dipping_people_are_flagged_by_the_model_and_also_escalated(full):
    esc = full.escalated.set_index("person_key")
    assert set(esc.index) == DUPLICATE_PEOPLE | DOUBLE_DIPPING
    assert set(esc[esc.also_escalated_for == "duplicate person"].index) == DUPLICATE_PEOPLE
    pred = full.predictions.set_index("employee_id")
    # they are predicted like everyone else: a high score is flagged, a low score is not
    assert pred.loc["E1126", "will_breach"] == 1 and pred.loc["E1127", "will_breach"] == 1 and pred.loc["E1126", "risk_score"] > 0.9
    assert pred.loc["E1099", "will_breach"] == 1 and pred.loc["E1100", "will_breach"] == 0
    # every flag is the model's own: the file flags exactly the people the model flagged, both IDs together
    people = full.people.set_index("person_key")
    expected = {e for k, row in people.iterrows() if row.will_breach == 1 for e in row.employee_ids}
    assert set(pred[pred.will_breach == 1].index) == expected and len(expected) == 23


def test_the_people_column_says_why_someone_is_also_escalated(full):
    p = full.people.set_index("person_key")
    assert p.at["E1126", "also_escalated_for"] == "duplicate person" and p.at["E1099", "also_escalated_for"] == "overlapping shifts"
    assert (p["also_escalated_for"] != "").sum() == 14


def test_the_dashboard_levels_do_not_change_with_the_exclusion(full):
    p = full.people
    assert int(p.level.isin(["High", "Watch", "Flagged"]).sum()) == 18 and p.band.value_counts().to_dict()["High"] == 9


def test_the_week_and_days_are_derived_from_the_data(full):
    assert full.status == "model" and full.cutoff == pd.Timestamp("2026-08-12")
    assert full.week_start == pd.Timestamp("2026-08-10") and full.week_end == pd.Timestamp("2026-08-16")
    assert full.predicted_days == ["Thursday", "Friday", "Saturday", "Sunday"]
    assert full.model["method"] == "Logistic regression" and "night_pattern" in full.model["features"]


def test_people_sites_and_flags(full):
    p = full.people
    assert len(p) == 208 and int((p.level.isin(["High", "Watch", "Flagged"])).sum()) == 18
    merged = p[p.employee_ids.apply(len) > 1]
    assert len(merged) == 5 and merged.sites_worked.apply(len).min() >= 1
    assert set(full.sites.site_id) == {f"ST-0{i}" for i in range(1, 7)}
    assert full.sites.flagged.sum() >= 11                      # a person counts at every site worked
    assert (full.people.hours_left == (55 - full.people.hours_so_far).clip(lower=0)).all()


def test_both_ids_of_a_merged_person_match(full):
    pred = full.predictions.set_index("employee_id")
    for ids in full.people.employee_ids[full.people.employee_ids.apply(len) > 1]:
        assert pred.loc[ids].nunique().max() == 1


def test_escalations(full):
    d = full.duplicates
    assert len(d) == 5 and (d.severity == "Escalate").all()
    assert len(full.overlaps) == 195 and int((full.overlaps.severity == "High").sum()) == 130
    assert len(full.open_shifts) == 3


def test_no_bank_or_tax_value_appears_anywhere(full, bundle):
    banned = set(bundle["payroll_details"].account_number) | set(bundle["payroll_details"].tax_number)
    text = predictions_csv(full)
    for frame in (full.people, full.sites, full.duplicates, full.overlaps, full.open_shifts):
        text += frame.astype(str).to_csv()
    assert not any(v in text for v in banned)


def test_empty_bundle_says_so():
    res = run({})
    assert res.status == "no_shifts" and res.people is None and "Load shifts.csv" in res.message


def test_shifts_only_still_predicts_by_id(bundle):
    res = run({"shifts": bundle["shifts"]})
    assert res.status == "model" and "night_pattern" not in res.model["features"]
    assert res.available["employees"] is False and res.duplicates.empty
    assert res.people.name.eq(res.people.person_key).all()
    assert res.predictions.employee_id.is_unique and len(res.predictions) == len(res.people)
    assert (res.overlaps.severity == "Medium").all()          # no sites file, so no province


def test_no_employees_but_payroll_still_finds_duplicates_by_bank_and_tax(bundle):
    res = run({"shifts": bundle["shifts"], "payroll_details": bundle["payroll_details"]})
    assert len(res.duplicates) == 5 and (res.duplicates.severity == "Escalate").all()


def test_without_payroll_duplicates_are_review_only(bundle):
    res = run({k: v for k, v in bundle.items() if k != "payroll_details"})
    assert len(res.duplicates) == 5 and (res.duplicates.severity == "Review").all()


def test_without_sites_the_dashboard_uses_site_ids(bundle):
    res = run({k: v for k, v in bundle.items() if k != "sites"})
    assert res.status == "model" and res.sites.site.eq(res.sites.site_id).all()


def test_without_holidays_hours_are_unchanged(bundle, full):
    res = run({k: v for k, v in bundle.items() if k != "public_holidays"})
    assert (res.people.set_index("person_key").hours_so_far == full.people.set_index("person_key").hours_so_far).all()


def test_usual_hours_still_to_come(full):
    p = full.people.set_index("person_key")
    assert (p.usual_hours_to_go - p.usual_shifts_left * p.usual_shift_hours).abs().max() < 1e-9
    assert p.loc["E1126", "usual_hours_to_go"] == pytest.approx(20.18, abs=0.01)       # 2.11 usual shifts x 9.56 h
    assert p.loc["E1099", "usual_hours_to_go"] == 0                                    # already worked a usual number of shifts
    assert (p.usual_shifts_left >= 0).all()


def test_the_30_to_50_percent_drop_down_level(full):
    lvl = full.people.set_index("person_key").level
    assert (lvl == "High").sum() == 9 and (lvl == "Watch").sum() == 7
    watch = full.people[full.people.level == "Watch"]
    assert watch.risk_score.between(0.3, 0.5, inclusive="left").all()


def test_dashboard_groups_by_risk(full):
    p = full.people
    assert p.band.value_counts().to_dict() == {"Low": 185, "High": 9, "Watch": 7, "Mid": 7}
    assert p[p.band == "Mid"].risk_score.between(0.2, 0.3, inclusive="left").all()
    assert p[p.band == "Low"].risk_score.lt(0.2).all() and p[p.band == "Watch"].risk_score.between(0.3, 0.5, inclusive="left").all()
    assert p[p.band == "High"].level.eq("High").all() and len(p) == 208


def test_notes_are_sorted_and_attached_to_people(full):
    r = full.reasons
    assert len(r) == 2117 and set(["person_key", "shift_date", "site_id", "category", "note", "this_week"]) <= set(r.columns)
    assert int(r.this_week.sum()) == 109 and r.person_key.nunique() == 208 and (r.category != "unknown").all()
    assert list(full.note_classes.columns) == ["shift_id", "category", "note"] and len(full.note_classes) == 2117
    merged_key = full.people[full.people.employee_ids.apply(len) > 1].person_key.iloc[0]
    assert r[r.person_key == merged_key].shape[0] > 0               # notes of both IDs land on the one person


def test_without_notes_there_are_no_reasons(bundle):
    b = {k: v for k, v in bundle.items() if k != "shift_notes"}
    res = run(b)
    assert res.reasons is None and res.note_classes is None and res.status == "model"


def test_the_will_breach_cut_off_is_the_f1_optimal_one(full):
    assert full.model["threshold"] == pytest.approx(0.2463, abs=1e-3)
    flagged = full.people[(full.people.will_breach == 1)]
    assert flagged.risk_score.min() >= full.model["threshold"] - 1e-9
