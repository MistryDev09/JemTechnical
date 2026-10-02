"""Read the 7 CSVs from a folder or uploaded files and validate expected columns."""
import pandas as pd

SHIFT_COLUMNS = ["shift_id", "employee_id", "site_id", "shift_date", "clock_in_time", "clock_out_time"]
HOLIDAY_COLUMNS = ["date", "name"]


def _read_strings(source, required):
    """Read a CSV (path or file-like upload) with every column as a string, so times are never auto-parsed."""
    df = pd.read_csv(source, dtype=str)
    df.columns = df.columns.str.strip()
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected column(s): {', '.join(missing)}")
    return df.apply(lambda col: col.str.strip())


def load_shifts(source):
    return _read_strings(source, SHIFT_COLUMNS)


def load_holidays(source):
    return _read_strings(source, HOLIDAY_COLUMNS)
