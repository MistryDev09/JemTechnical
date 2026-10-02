"""Read the 7 CSVs from a folder or uploaded files and validate expected columns."""
import pandas as pd

SHIFT_COLUMNS = ["shift_id", "employee_id", "site_id", "shift_date", "clock_in_time", "clock_out_time"]
HOLIDAY_COLUMNS = ["date", "name"]
EMPLOYEE_COLUMNS = ["employee_id", "full_name", "id_number"]
SITE_COLUMNS = ["site_id", "site_name", "province"]
PAYROLL_COLUMNS = ["employee_id", "account_number", "tax_number"]


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


def load_employees(source):
    return _read_strings(source, EMPLOYEE_COLUMNS)


def load_sites(source):
    return _read_strings(source, SITE_COLUMNS)


def load_payroll(source):
    """Read ONLY the columns needed to compare records (never hourly rate, names or other fields).

    The bank account and tax number are used in memory to detect duplicate people and must never be
    written to any output, export or dashboard.
    """
    df = pd.read_csv(source, dtype=str, usecols=lambda c: c.strip() in PAYROLL_COLUMNS)
    df.columns = df.columns.str.strip()
    missing = [c for c in PAYROLL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected column(s): {', '.join(missing)}")
    return df.apply(lambda col: col.str.strip())
