"""Shift hours: parse times, overnight fix, flags, and attribution of hours to a day and week."""
import pandas as pd

TIME_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d$"
MAX_DAY_HOURS = 12  # shifts longer than this are flagged (still counted)


def _minutes(times):
    """'HH:MM' strings to minutes since midnight; anything that is not a valid time becomes NaN."""
    valid = times.str.match(TIME_PATTERN, na=False)
    hh = pd.to_numeric(times.str[:2].where(valid), errors="coerce")
    mm = pd.to_numeric(times.str[3:5].where(valid), errors="coerce")
    return hh * 60 + mm


def parse_shifts(df):
    """Add start/end, overnight flag, duration and data-quality flags.

    Overnight is decided by the times alone: a clock-out earlier than the clock-in means the
    shift ended the next day. Shifts with an empty/invalid date or time, or with identical
    clock-in and clock-out, get no hours. Shifts over 12 hours are flagged but keep their hours.
    """
    out = df.copy()
    out["shift_date"] = pd.to_datetime(df["shift_date"], format="%Y-%m-%d", errors="coerce")
    clock_in = _minutes(df["clock_in_time"])
    clock_out = _minutes(df["clock_out_time"])

    out["invalid_date"] = out["shift_date"].isna()
    out["invalid_clock_in"] = clock_in.isna()
    out["invalid_clock_out"] = clock_out.isna()
    both = ~(out["invalid_clock_in"] | out["invalid_clock_out"])

    out["zero_duration"] = both & (clock_out == clock_in)
    out["is_overnight"] = both & (clock_out < clock_in)
    out["excluded"] = out["invalid_date"] | ~both | out["zero_duration"]

    minutes = (clock_out - clock_in).where(~out["is_overnight"], clock_out + 1440 - clock_in)
    out["duration_hours"] = (minutes / 60).where(~out["excluded"])
    out["over_12h"] = out["duration_hours"] > MAX_DAY_HOURS
    out["start"] = out["shift_date"] + pd.to_timedelta(clock_in.where(~out["excluded"]), unit="m")
    out["end"] = out["start"] + pd.to_timedelta(minutes.where(~out["excluded"]), unit="m")
    out["hours_before_midnight"] = ((1440 - clock_in) / 60).where(out["is_overnight"])
    out["hours_after_midnight"] = (clock_out / 60).where(out["is_overnight"])
    return out


def attribute_hours(shifts, holidays=None):
    """One row per attributed segment, using the greater-portion rule.

    A shift crossing midnight is attributed whole to the calendar day on which most of it was
    worked. An exact tie is split at midnight into two segments. The attributed day decides the
    week (Mon-Sun), the Sunday rate and the public-holiday rate (multiplier 2.0, otherwise 1.0).
    """
    valid = shifts[~shifts["excluded"]]
    before = valid["hours_before_midnight"]
    after = valid["hours_after_midnight"]
    next_day = valid["is_overnight"] & (after > before)
    tie = valid["is_overnight"] & (after == before)

    first = valid.copy()
    first["attributed_date"] = first["shift_date"] + pd.to_timedelta(next_day.astype(int), unit="D")
    first["hours"] = first["duration_hours"].where(~tie, before)

    second = valid[tie].copy()
    second["attributed_date"] = second["shift_date"] + pd.Timedelta(days=1)
    second["hours"] = after[tie]

    seg = pd.concat([first, second], ignore_index=True)
    seg["week_start"] = seg["attributed_date"] - pd.to_timedelta(seg["attributed_date"].dt.weekday, unit="D")
    seg["is_sunday"] = seg["attributed_date"].dt.weekday == 6
    holiday_dates = set()
    if holidays is not None:
        holiday_dates = set(pd.to_datetime(holidays["date"], format="%Y-%m-%d", errors="coerce").dropna())
    seg["is_public_holiday"] = seg["attributed_date"].isin(holiday_dates)
    seg["multiplier"] = (seg["is_sunday"] | seg["is_public_holiday"]).map({True: 2.0, False: 1.0})
    cols = ["shift_id", "employee_id", "site_id", "attributed_date", "week_start", "hours",
            "is_sunday", "is_public_holiday", "multiplier", "over_12h"]
    return seg[cols].sort_values(["employee_id", "attributed_date", "shift_id"]).reset_index(drop=True)


def data_cutoff(shifts):
    """Last clock-in date in the data. Used (not attributed dates) to find the in-progress week."""
    return shifts["shift_date"].max()


def quality_report(shifts):
    """Counts of data-quality issues, for logging and the dashboard."""
    return {
        "shifts": len(shifts),
        "overnight": int(shifts["is_overnight"].sum()),
        "over_12h_flagged": int(shifts["over_12h"].sum()),
        "invalid_date": int(shifts["invalid_date"].sum()),
        "invalid_clock_in": int(shifts["invalid_clock_in"].sum()),
        "invalid_clock_out": int(shifts["invalid_clock_out"].sum()),
        "zero_duration": int(shifts["zero_duration"].sum()),
        "excluded": int(shifts["excluded"].sum()),
    }
