import pandas as pd
import pytest

from src.hours import attribute_hours, parse_shifts
from src.integrity import add_person_key, find_cross_province_days, find_duplicate_people, find_overlaps, find_pattern_mismatches
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


def _segments(*rows):
    seg = attribute_hours(shifts(*rows))
    return seg.assign(person_key=seg["employee_id"])


def test_two_provinces_on_one_day_is_flagged_even_without_a_time_overlap():
    seg = _segments(("E1", "ST-01", "2026-08-11", "06:00", "10:00"), ("E1", "ST-04", "2026-08-11", "14:00", "18:00"))
    out = find_cross_province_days(seg, SITES)
    assert list(out.person_key) == ["E1"] and out.sites.iloc[0] == 2


def test_two_sites_in_the_same_province_on_one_day_are_not_flagged():
    seg = _segments(("E1", "ST-01", "2026-08-11", "06:00", "10:00"), ("E1", "ST-02", "2026-08-11", "14:00", "18:00"))
    assert find_cross_province_days(seg, SITES).empty


def test_two_provinces_on_different_days_are_not_flagged():
    seg = _segments(("E1", "ST-01", "2026-08-11", "06:00", "14:00"), ("E1", "ST-04", "2026-08-12", "06:00", "14:00"))
    assert find_cross_province_days(seg, SITES).empty


def test_no_province_information_gives_no_flags():
    seg = _segments(("E1", "ST-01", "2026-08-11", "06:00", "10:00"), ("E1", "ST-04", "2026-08-11", "14:00", "18:00"))
    assert find_cross_province_days(seg, SITES.drop(columns="province")).empty and find_cross_province_days(seg, None).empty


def _patterns(**by_employee):
    return pd.DataFrame({"employee_id": list(by_employee), "shift_pattern": list(by_employee.values())})


NIGHT = ("E1", "ST-01", "2026-08-11", "18:00", "06:00")
DAY = ("E1", "ST-01", "2026-08-11", "06:00", "15:00")


def test_overnight_shift_for_a_night_pattern_employee_is_confirmed_not_flagged():
    assert find_pattern_mismatches(shifts(NIGHT), _patterns(E1="night")).empty


def test_overnight_shift_for_a_day_pattern_employee_is_flagged_and_keeps_its_hours():
    out = find_pattern_mismatches(shifts(NIGHT), _patterns(E1="day"))
    assert list(out.shift_id) == ["S0"] and out.shift_pattern.iloc[0] == "day" and out.hours.iloc[0] == 12
    # flagging never changes the hours that are counted
    seg = attribute_hours(shifts(NIGHT))
    assert seg.hours.sum() == 12


def test_a_day_shift_is_not_flagged_for_either_pattern_and_the_reverse_case_is_not_flagged():
    assert find_pattern_mismatches(shifts(DAY), _patterns(E1="day")).empty
    assert find_pattern_mismatches(shifts(DAY), _patterns(E1="night")).empty          # night pattern, not overnight: deliberately not flagged


def test_pattern_check_ignores_case_spaces_missing_patterns_and_a_missing_employees_file():
    assert len(find_pattern_mismatches(shifts(NIGHT), _patterns(E1=" Day "))) == 1
    assert find_pattern_mismatches(shifts(NIGHT), _patterns(E1=None)).empty
    assert find_pattern_mismatches(shifts(NIGHT), pd.DataFrame({"employee_id": ["E2"], "shift_pattern": ["day"]})).empty
    assert find_pattern_mismatches(shifts(NIGHT), None).empty
    assert find_pattern_mismatches(shifts(NIGHT), pd.DataFrame({"employee_id": ["E1"]})).empty


def test_a_shift_with_no_clock_out_is_never_judged_or_made_up():
    s = shifts(("E1", "ST-01", "2026-08-11", "18:00", ""))
    assert s.excluded.all() and find_pattern_mismatches(s, _patterns(E1="day")).empty
