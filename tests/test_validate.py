import io

import pandas as pd
import pytest

from src.validate import FILE_NAMES, check_file, cross_check, identify_file, read_csv_any


def csv(df):
    return df.to_csv(index=False).encode()


def shifts_df(**over):
    row = {"shift_id": "S1", "employee_id": "E1", "site_id": "ST-01", "shift_date": "2026-08-03",
           "clock_in_time": "07:00", "clock_out_time": "15:00"}
    rows = over.pop("rows", [row])
    return pd.DataFrame(rows)


@pytest.mark.parametrize("name,kind", [("shifts.csv", "shifts"), ("employees.csv", "employees"), ("sites.csv", "sites"),
                                       ("public_holidays.csv", "public_holidays"), ("shift_notes.csv", "shift_notes"),
                                       ("payroll_details.csv", "payroll_details"), ("weekly_summary.csv", "weekly_summary")])
def test_real_files_are_recognised_by_their_columns(name, kind):
    df = read_csv_any(f"data/{name}")
    assert identify_file(df.columns)[0] == kind
    assert identify_file(df.columns, "renamed_export.csv")[0] == kind     # the filename is only a hint


def test_weekly_summary_is_rejected_as_not_used():
    rep = check_file("weekly_summary.csv", "data/weekly_summary.csv")
    assert rep.kind == "weekly_summary" and not rep.ok and "not used" in rep.errors[0]


def test_unknown_file_is_rejected():
    rep = check_file("mystery.csv", csv(pd.DataFrame({"a": [1], "b": [2]})))
    assert rep.kind is None and not rep.ok and "does not match" in rep.errors[0]


def test_missing_required_column_is_an_error_naming_the_column():
    rep = check_file("shifts.csv", csv(shifts_df().drop(columns="clock_out_time")))
    assert rep.kind == "shifts" and not rep.ok and "clock_out_time" in rep.errors[0]


def test_empty_and_header_only_files_are_errors():
    assert "empty" in check_file("shifts.csv", b"").errors[0].lower()
    rep = check_file("shifts.csv", csv(shifts_df().iloc[0:0]))
    assert not rep.ok and "no rows" in rep.errors[0]


def test_header_whitespace_and_blank_cells_are_cleaned():
    text = b" shift_id , employee_id ,site_id,shift_date,clock_in_time,clock_out_time\n S1 , E1 ,ST-01,2026-08-03,07:00,\n"
    rep = check_file("shifts.csv", text)
    assert rep.ok and rep.data.loc[0, "shift_id"] == "S1" and pd.isna(rep.data.loc[0, "clock_out_time"])
    assert any("no clock-out" in w for w in rep.warnings)


def test_duplicate_and_empty_shift_ids_are_errors():
    dup = pd.concat([shifts_df(), shifts_df()])
    assert any("more than once" in e for e in check_file("shifts.csv", csv(dup)).errors)
    empty = shifts_df(); empty.loc[0, "shift_id"] = None
    assert any("empty shift_id" in e for e in check_file("shifts.csv", csv(empty)).errors)


def test_bad_times_are_warnings_not_errors():
    rep = check_file("shifts.csv", csv(shifts_df(rows=[
        {"shift_id": "S1", "employee_id": "E1", "site_id": "ST-01", "shift_date": "2026-08-03", "clock_in_time": "7pm", "clock_out_time": "15:00"},
        {"shift_id": "S2", "employee_id": "E1", "site_id": "ST-01", "shift_date": "2026-08-04", "clock_in_time": "07:00", "clock_out_time": "19:30"}])))
    assert rep.ok and any("invalid clock-in" in w for w in rep.warnings) and any("longer than 12" in w for w in rep.warnings)


def test_unreadable_dates_error_only_when_all_are_bad():
    all_bad = shifts_df(rows=[{"shift_id": "S1", "employee_id": "E1", "site_id": "A", "shift_date": "tomorrow", "clock_in_time": "07:00", "clock_out_time": "15:00"}])
    assert not check_file("shifts.csv", csv(all_bad)).ok
    some_bad = pd.concat([shifts_df(), all_bad.assign(shift_id="S2")])
    rep = check_file("shifts.csv", csv(some_bad))
    assert rep.ok and any("invalid shift_date" in w for w in rep.warnings)


def test_payroll_keeps_only_the_three_comparison_columns():
    rep = check_file("payroll_details.csv", "data/payroll_details.csv")
    assert rep.ok and list(rep.data.columns) == ["employee_id", "account_number", "tax_number"]


def test_employee_warnings():
    emp = pd.DataFrame([{"employee_id": "E1", "full_name": "A", "id_number": "1", "shift_pattern": "swing", "contract_ordinary_hours": "40"}])
    rep = check_file("employees.csv", csv(emp))
    assert rep.ok and any("other than day or night" in w for w in rep.warnings) and any("not 45" in w for w in rep.warnings)
    missing = check_file("employees.csv", csv(emp.drop(columns=["shift_pattern"])))
    assert any("night-shift feature" in w for w in missing.warnings)


def test_holiday_rows_with_bad_dates_are_dropped_with_a_warning():
    rep = check_file("public_holidays.csv", csv(pd.DataFrame({"date": ["2026-08-10", "soon"], "name": ["Women's Day", "?"]})))
    assert rep.ok and list(rep.data["date"]) == ["2026-08-10"] and rep.warnings


def test_cross_check_warns_but_never_blocks():
    bundle = {"shifts": shifts_df(), "employees": pd.DataFrame({"employee_id": ["E9"], "full_name": ["x"], "id_number": ["1"]}),
              "sites": pd.DataFrame({"site_id": ["ST-09"], "site_name": ["x"], "province": ["x"]}),
              "shift_notes": pd.DataFrame({"shift_id": ["S404"], "note": ["hi"]})}
    msgs = cross_check(bundle)
    assert any("employee ID" in m for m in msgs) and any("site ID" in m for m in msgs) and any("note" in m for m in msgs)
    assert cross_check({}) == []


def test_file_names_cover_every_kind():
    assert FILE_NAMES["shifts"] == "shifts.csv"
