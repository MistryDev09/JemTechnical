import pandas as pd
import pytest

from src.hours import parse_shifts
from src.integrity import add_person_key, find_duplicate_people, find_overlaps
from src.loader import load_employees, load_payroll, load_shifts, load_sites

SITES = pd.DataFrame({
    "site_id": ["ST-01", "ST-02", "ST-04"],
    "site_name": ["Sandton", "OR Tambo", "Century City"],
    "province": ["Gauteng", "Gauteng", "Western Cape"],
})


def employees(*rows):
    return pd.DataFrame([{"employee_id": e, "full_name": n, "id_number": i} for e, n, i in rows])


def payroll(*rows):
    return pd.DataFrame([{"employee_id": e, "account_number": a, "tax_number": t} for e, a, t in rows])


def shifts(*rows):
    """rows: (employee_id, site_id, date, clock_in, clock_out)"""
    return parse_shifts(pd.DataFrame([
        {"shift_id": f"S{i}", "employee_id": e, "site_id": s, "shift_date": d, "clock_in_time": a, "clock_out_time": b}
        for i, (e, s, d, a, b) in enumerate(rows)]))


# ---- duplicate people

def test_same_id_number_and_bank_account_is_escalate():
    emp = employees(("E1", "Lucky Sibiya", "111"), ("E2", "L. Sibiya", "111"), ("E3", "Other", "333"))
    pay = payroll(("E1", "A1", "T1"), ("E2", "A1", "T1"), ("E3", "A3", "T3"))
    people = find_duplicate_people(emp, pay)
    assert len(people) == 1
    row = people.iloc[0]
    assert row.person_key == "E1" and row.employee_ids == ["E1", "E2"]
    assert row.severity == "Escalate" and row.shared_bank_account and row.shared_tax_number and row.shared_id_number


def test_same_id_number_only_is_review():
    emp = employees(("E1", "A", "111"), ("E2", "B", "111"))
    pay = payroll(("E1", "A1", "T1"), ("E2", "A2", "T2"))
    row = find_duplicate_people(emp, pay).iloc[0]
    assert row.severity == "Review" and row.evidence == "same ID number"


def test_works_without_payroll():
    row = find_duplicate_people(employees(("E1", "A", "111"), ("E2", "B", "111"))).iloc[0]
    assert row.severity == "Review" and not row.shared_bank_account


def test_same_bank_account_different_id_number_is_grouped_and_escalated():
    emp = employees(("E1", "A", "111"), ("E2", "B", "222"))
    pay = payroll(("E1", "A1", "T1"), ("E2", "A1", "T2"))
    row = find_duplicate_people(emp, pay).iloc[0]
    assert row.employee_ids == ["E1", "E2"] and row.severity == "Escalate" and not row.shared_id_number


def test_unrelated_employees_are_not_grouped():
    emp = employees(("E1", "A", "111"), ("E2", "B", "222"))
    pay = payroll(("E1", "A1", "T1"), ("E2", "A2", "T2"))
    assert find_duplicate_people(emp, pay).empty


def test_chained_records_form_one_group():
    emp = employees(("E1", "A", "111"), ("E2", "B", "111"), ("E3", "C", "333"))
    pay = payroll(("E1", "A1", "T1"), ("E2", "A2", "T2"), ("E3", "A2", "T3"))  # E1=E2 by ID, E2=E3 by bank
    assert find_duplicate_people(emp, pay).iloc[0].employee_ids == ["E1", "E2", "E3"]


def test_add_person_key_maps_all_ids():
    people = find_duplicate_people(employees(("E1", "A", "111"), ("E2", "B", "111"), ("E3", "C", "333")))
    out = add_person_key(pd.DataFrame({"employee_id": ["E1", "E2", "E3"]}), people)
    assert out.person_key.tolist() == ["E1", "E1", "E3"]


# ---- overlaps

def test_overlap_is_flagged_with_hours_and_province():
    s = shifts(("E1", "ST-01", "2026-08-03", "06:00", "14:00"), ("E1", "ST-04", "2026-08-03", "08:00", "12:00"))
    o = find_overlaps(s, SITES)
    assert len(o) == 1
    r = o.iloc[0]
    assert r.overlap_hours == 4 and r.kind == "same_id" and r.different_province and r.severity == "High"
    assert "Potential fraud" in r.flag


def test_same_province_overlap_is_medium():
    s = shifts(("E1", "ST-01", "2026-08-03", "06:00", "14:00"), ("E1", "ST-02", "2026-08-03", "13:00", "17:00"))
    r = find_overlaps(s, SITES).iloc[0]
    assert r.overlap_hours == 1 and not r.different_province and r.severity == "Medium"


def test_back_to_back_shifts_are_not_overlaps():
    s = shifts(("E1", "ST-01", "2026-08-03", "06:00", "14:00"), ("E1", "ST-02", "2026-08-03", "14:00", "18:00"))
    assert find_overlaps(s, SITES).empty


def test_overnight_overlap_across_midnight():
    s = shifts(("E1", "ST-01", "2026-08-03", "20:00", "06:00"), ("E1", "ST-02", "2026-08-04", "05:00", "13:00"))
    r = find_overlaps(s, SITES).iloc[0]
    assert r.overlap_hours == 1


def test_different_people_never_overlap():
    s = shifts(("E1", "ST-01", "2026-08-03", "06:00", "14:00"), ("E9", "ST-04", "2026-08-03", "08:00", "12:00"))
    assert find_overlaps(s, SITES).empty


def test_cross_id_overlap_between_duplicate_records():
    people = find_duplicate_people(employees(("E1", "A", "111"), ("E2", "B", "111")))
    s = shifts(("E1", "ST-01", "2026-08-03", "06:00", "14:00"), ("E2", "ST-04", "2026-08-03", "08:00", "16:00"))
    assert find_overlaps(s, SITES).empty  # without the person link, different IDs never overlap
    r = find_overlaps(s, SITES, people).iloc[0]
    assert r.kind == "cross_id" and r.person_key == "E1" and r.overlap_hours == 6


def test_flagging_does_not_change_hours():
    s = shifts(("E1", "ST-01", "2026-08-03", "06:00", "14:00"), ("E1", "ST-04", "2026-08-03", "08:00", "12:00"))
    before = s.copy()
    find_overlaps(s, SITES)
    pd.testing.assert_frame_equal(s, before)
    assert s.duration_hours.sum() == 12  # both records still count in full


# ---- real data

@pytest.fixture(scope="module")
def real():
    emp = load_employees("data/employees.csv")
    pay = load_payroll("data/payroll_details.csv")
    sites = load_sites("data/sites.csv")
    shifts_ = parse_shifts(load_shifts("data/shifts.csv"))
    people = find_duplicate_people(emp, pay)
    return emp, pay, sites, shifts_, people


def test_real_data_duplicates(real):
    _, _, _, _, people = real
    assert len(people) == 5
    assert set(people.person_key) == {"E1035", "E1090", "E1097", "E1126", "E1193"}
    assert (people.severity == "Escalate").all()
    assert people.shared_id_number.all() and people.shared_bank_account.all() and people.shared_tax_number.all()


def test_real_data_overlaps(real):
    _, _, sites, shifts_, people = real
    o = find_overlaps(shifts_, sites, people)
    same, cross = o[o.kind == "same_id"], o[o.kind == "cross_id"]
    assert len(same) == 126 and same.different_province.sum() == 99
    assert len(cross) == 69 and cross.different_province.sum() == 31


def test_outputs_never_contain_bank_or_tax_values(real):
    _, pay, sites, shifts_, people = real
    o = find_overlaps(shifts_, sites, people)
    banned = set(pay.account_number) | set(pay.tax_number)
    assert not ({"account_number", "tax_number"} & (set(people.columns) | set(o.columns)))
    text = people.to_csv() + o.to_csv()
    assert not any(v in text for v in banned)
