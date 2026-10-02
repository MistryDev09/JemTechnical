import pandas as pd
import pytest

from src.hours import attribute_hours, data_cutoff, parse_shifts, quality_report
from src.loader import load_holidays, load_shifts

HOLIDAYS = pd.DataFrame({"date": ["2026-08-10"], "name": ["National Women's Day (observed)"]})


def shifts(*rows):
    """rows: (shift_date, clock_in, clock_out). Dates used: Mon 2026-08-03 ... Sun 2026-08-09."""
    return pd.DataFrame(
        [{"shift_id": f"S{i}", "employee_id": "E1", "site_id": "ST-01",
          "shift_date": d, "clock_in_time": a, "clock_out_time": b} for i, (d, a, b) in enumerate(rows)]
    )


def parsed(*rows):
    return parse_shifts(shifts(*rows))


def test_day_shift_is_not_overnight():
    p = parsed(("2026-08-03", "07:00", "15:15")).iloc[0]
    assert p.duration_hours == 8.25 and not p.is_overnight and not p.excluded


def test_overnight_adds_a_day():
    p = parsed(("2026-08-03", "22:00", "06:00")).iloc[0]
    assert p.duration_hours == 8 and p.is_overnight


def test_short_evening_shift_is_not_overnight():
    p = parsed(("2026-08-03", "18:00", "22:00")).iloc[0]
    assert p.duration_hours == 4 and not p.is_overnight


@pytest.mark.parametrize("clock_in,clock_out", [("07:00", None), (None, "15:00"), ("07:00", ""), ("25:99", "15:00"), ("7pm", "15:00")])
def test_empty_or_malformed_times_are_flagged_and_excluded(clock_in, clock_out):
    p = parsed(("2026-08-03", clock_in, clock_out)).iloc[0]
    assert p.excluded and pd.isna(p.duration_hours)
    assert p.invalid_clock_in or p.invalid_clock_out


def test_equal_start_and_end_is_excluded():
    p = parsed(("2026-08-03", "08:00", "08:00")).iloc[0]
    assert p.zero_duration and p.excluded


def test_over_12_hours_is_flagged_but_counted():
    p = parsed(("2026-08-03", "06:00", "19:00")).iloc[0]
    assert p.over_12h and not p.excluded and p.duration_hours == 13
    assert attribute_hours(parse_shifts(shifts(("2026-08-03", "06:00", "19:00")))).hours.sum() == 13


def test_exactly_12_hours_is_not_flagged():
    assert not parsed(("2026-08-03", "06:00", "18:00")).iloc[0].over_12h


def test_sunday_start_mostly_monday_goes_to_monday_new_week_without_sunday_rate():
    seg = attribute_hours(parsed(("2026-08-02", "19:00", "07:00")))  # 5h Sun, 7h Mon
    assert len(seg) == 1
    r = seg.iloc[0]
    assert r.attributed_date == pd.Timestamp("2026-08-03") and r.week_start == pd.Timestamp("2026-08-03")
    assert r.hours == 12 and r.multiplier == 1.0


def test_saturday_start_mostly_sunday_gets_sunday_rate():
    r = attribute_hours(parsed(("2026-08-01", "19:00", "07:00"))).iloc[0]  # 5h Sat, 7h Sun
    assert r.attributed_date == pd.Timestamp("2026-08-02") and r.is_sunday and r.multiplier == 2.0


def test_mostly_before_midnight_stays_on_start_day():
    r = attribute_hours(parsed(("2026-08-02", "14:00", "02:00"))).iloc[0]  # 10h Sun, 2h Mon
    assert r.attributed_date == pd.Timestamp("2026-08-02") and r.multiplier == 2.0 and r.hours == 12


def test_exact_tie_is_split_at_midnight():
    seg = attribute_hours(parsed(("2026-08-02", "20:00", "04:00")))  # 4h Sun, 4h Mon
    assert len(seg) == 2
    sun, mon = seg.sort_values("attributed_date").itertuples()
    assert (sun.hours, sun.multiplier, sun.week_start) == (4, 2.0, pd.Timestamp("2026-07-27"))
    assert (mon.hours, mon.multiplier, mon.week_start) == (4, 1.0, pd.Timestamp("2026-08-03"))


def test_public_holiday_attribution_including_sunday_start():
    seg = attribute_hours(parsed(("2026-08-09", "19:00", "07:00"), ("2026-08-10", "08:00", "16:00")), HOLIDAYS)
    assert (seg.attributed_date == pd.Timestamp("2026-08-10")).all()  # Sunday start moves to the holiday
    assert (seg.multiplier == 2.0).all() and seg.is_public_holiday.all()


def test_weekday_is_normal_rate():
    assert attribute_hours(parsed(("2026-08-04", "08:00", "16:00")), HOLIDAYS).iloc[0].multiplier == 1.0


def test_hours_are_conserved_across_attribution():
    p = parsed(("2026-08-02", "20:00", "04:00"), ("2026-08-04", "22:00", "06:00"), ("2026-08-05", "07:00", "15:00"))
    assert attribute_hours(p).hours.sum() == p.duration_hours.sum()


def test_data_cutoff_uses_clock_in_date_not_attributed_date():
    p = parsed(("2026-08-11", "08:00", "16:00"), ("2026-08-12", "19:00", "07:00"))  # Wed shift attributed to Thu
    assert data_cutoff(p) == pd.Timestamp("2026-08-12")
    assert attribute_hours(p).attributed_date.max() == pd.Timestamp("2026-08-13")


def test_real_data_matches_earlier_findings():
    p = parse_shifts(load_shifts("data/shifts.csv"))
    report = quality_report(p)
    assert report["shifts"] == 8863 and report["overnight"] == 1010
    assert report["invalid_clock_out"] == 184 and report["excluded"] == 184
    assert report["over_12h_flagged"] == 1279
    assert data_cutoff(p) == pd.Timestamp("2026-08-12")
    seg = attribute_hours(p, load_holidays("data/public_holidays.csv"))
    assert len(seg) == 8863 - 184 + 47  # 47 exact-tie overnight shifts are split in two
    assert seg.hours.sum() == pytest.approx(p.duration_hours.sum())
