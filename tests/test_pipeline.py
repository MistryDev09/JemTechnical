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


def test_reproduces_the_notebook_predictions(full):
    expected = pd.read_csv("predictions.csv")
    got = full.predictions
    assert list(got.columns) == ["employee_id", "will_breach", "risk_score"]
    assert (got.employee_id.values == expected.employee_id.values).all()
    assert (got.will_breach.values == expected.will_breach.values).all()
    assert (got.risk_score - expected.risk_score).abs().max() < 1e-9
    assert len(got) == 213 and int(got.will_breach.sum()) == 51


def test_the_week_and_days_are_derived_from_the_data(full):
    assert full.status == "model" and full.cutoff == pd.Timestamp("2026-08-12")
    assert full.week_start == pd.Timestamp("2026-08-10") and full.week_end == pd.Timestamp("2026-08-16")
    assert full.predicted_days == ["Thursday", "Friday", "Saturday", "Sunday"]
    assert full.model["method"] == "Logistic regression" and "night_pattern" in full.model["features"]


def test_people_sites_and_flags(full):
    p = full.people
    assert len(p) == 208 and int((p.level.isin(["High", "Flagged"])).sum()) == 46
    merged = p[p.employee_ids.apply(len) > 1]
    assert len(merged) == 5 and merged.sites_worked.apply(len).min() >= 1
    assert set(full.sites.site_id) == {f"ST-0{i}" for i in range(1, 7)}
    assert full.sites.flagged.sum() >= 46                      # a person counts at every site worked
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
