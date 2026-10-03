"""Input handling: recognise each uploaded CSV, check its columns and values, and return a cleaned copy.

A file with a problem is rejected on its own (errors); row-level problems are applied and reported
(warnings). Files are recognised by their column headers, so a renamed export still works.
Only the columns the dashboard needs are kept, so nothing else (for example pay rates) is retained.
"""
import io
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .hours import parse_shifts

# kind -> required columns (file is rejected without them), optional columns (used when present), key
SPECS = {
    "shifts": dict(
        required=["shift_id", "employee_id", "site_id", "shift_date", "clock_in_time", "clock_out_time"],
        optional=[], key="shift_id"),
    "employees": dict(
        required=["employee_id", "full_name", "id_number"],
        optional=["role", "primary_site_id", "shift_pattern", "contract_ordinary_hours", "employment_type"],
        key="employee_id"),
    "sites": dict(required=["site_id", "site_name", "province"], optional=[], key="site_id"),
    "public_holidays": dict(required=["date"], optional=["name"], key="date"),
    "shift_notes": dict(required=["shift_id", "note"], optional=["logged_by"], key="shift_id"),
    # only these three payroll columns are ever read; the others in the file are ignored
    "payroll_details": dict(
        required=["employee_id", "account_number", "tax_number"],
        optional=["full_name", "id_number", "bank_name", "branch_code", "account_type", "hourly_rate", "pay_frequency"],
        key="employee_id", keep=["employee_id", "account_number", "tax_number"]),
    "weekly_summary": dict(
        required=["employee_id", "week_starting", "total_hours", "overtime_hours", "breached"],
        optional=[], key="employee_id", unused=True),
}
USED_KINDS = [k for k, s in SPECS.items() if not s.get("unused")]
FILE_NAMES = {k: f"{k}.csv" for k in SPECS}
VALID_PATTERNS = {"day", "night"}


@dataclass
class FileReport:
    filename: str
    kind: str | None = None
    rows: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    data: pd.DataFrame | None = None

    @property
    def ok(self):
        return not self.errors and self.data is not None


def read_csv_any(source):
    """Read an uploaded file (path, bytes or file object) with every column as text."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            if hasattr(source, "seek"):
                source.seek(0)
            df = pd.read_csv(source, dtype=str, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            raise ValueError("The file is empty.")
        except Exception as exc:
            raise ValueError(f"Could not read the file as a CSV ({type(exc).__name__}).")
    else:
        raise ValueError("Could not read the file's text encoding.")
    df.columns = [str(c).strip() for c in df.columns]
    return df.apply(lambda col: col.str.strip()).replace("", np.nan)


def identify_file(columns, filename=None):
    """Return (kind, missing_columns). kind is None if the file matches no known layout."""
    cols = set(columns)
    hint = None
    if filename:
        stem = str(filename).lower().rsplit(".", 1)[0]
        hint = stem if stem in SPECS else None
    full = []
    for kind, spec in SPECS.items():
        if set(spec["required"]) <= cols:
            full.append((len(cols & (set(spec["required"]) | set(spec["optional"]))), kind == hint, kind))
    if full:
        return max(full)[2], []
    partial = []
    for kind, spec in SPECS.items():
        req = set(spec["required"])
        share = len(cols & req) / len(req)
        if share >= 0.5 and len(cols & req) >= 2:
            partial.append((share, kind == hint, kind))
    if partial:
        kind = max(partial)[2]
        return kind, [c for c in SPECS[kind]["required"] if c not in cols]
    return None, []


def _count(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _check_key(df, key, errors):
    empty = df[key].isna()
    if empty.any():
        errors.append(f"{_count(int(empty.sum()), 'row')} with an empty {key}.")
    dups = df.loc[~empty, key]
    n_dup = int(dups[dups.duplicated()].nunique())
    if n_dup:
        errors.append(f"{_count(n_dup, key + ' value')} appear more than once.")


def _check_shifts(df, errors, warnings):
    _check_key(df, "shift_id", errors)
    missing_emp = df["employee_id"].isna()
    if missing_emp.any():
        warnings.append(f"{_count(int(missing_emp.sum()), 'shift')} with an empty employee_id were dropped.")
        df = df[~missing_emp]
    if df["site_id"].isna().any():
        warnings.append(f"{_count(int(df['site_id'].isna().sum()), 'shift')} with an empty site_id.")
    p = parse_shifts(df)
    n = len(df)
    if n and p["invalid_date"].all():
        errors.append("No shift_date could be read. Dates must look like 2026-08-12.")
        return df
    if p["invalid_date"].any():
        warnings.append(f"{_count(int(p['invalid_date'].sum()), 'shift')} with an invalid shift_date are excluded.")
    for col, flag, word in (("clock_out_time", "invalid_clock_out", "clock-out"), ("clock_in_time", "invalid_clock_in", "clock-in")):
        empty = df[col].isna().to_numpy()
        bad = (p[flag].to_numpy()) & ~empty
        if empty.any():
            warnings.append(f"{_count(int(empty.sum()), 'shift')} with no {word} time are excluded and flagged.")
        if bad.any():
            warnings.append(f"{_count(int(bad.sum()), 'shift')} with an invalid {word} time (expected HH:MM) are excluded.")
    if p["zero_duration"].any():
        warnings.append(f"{_count(int(p['zero_duration'].sum()), 'shift')} with identical clock-in and clock-out are excluded.")
    if p["over_12h"].any():
        warnings.append(f"{_count(int(p['over_12h'].sum()), 'shift')} longer than 12 hours are flagged (still counted).")
    return df


def _check_employees(df, errors, warnings):
    _check_key(df, "employee_id", errors)
    if df["id_number"].isna().any():
        warnings.append(f"{_count(int(df['id_number'].isna().sum()), 'employee')} with no id_number (cannot be matched as duplicates).")
    if "shift_pattern" in df:
        bad = df["shift_pattern"].notna() & ~df["shift_pattern"].str.lower().isin(VALID_PATTERNS)
        if bad.any():
            warnings.append(f"{_count(int(bad.sum()), 'employee')} with a shift_pattern other than day or night.")
    else:
        warnings.append("No shift_pattern column: the night-shift feature is not used.")
    if "contract_ordinary_hours" in df:
        hours = pd.to_numeric(df["contract_ordinary_hours"], errors="coerce")
        if hours.isna().any():
            warnings.append(f"{_count(int(hours.isna().sum()), 'employee')} with unreadable contract_ordinary_hours.")
        if (hours.dropna() != 45).any():
            warnings.append("Some contract hours are not 45. The 55-hour cap (45 + 10) is applied to everyone.")
    return df


def _check_sites(df, errors, warnings):
    _check_key(df, "site_id", errors)
    if df["province"].isna().any():
        warnings.append(f"{_count(int(df['province'].isna().sum()), 'site')} with no province.")
    return df


def _check_holidays(df, errors, warnings):
    parsed = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    if len(df) and parsed.isna().all():
        errors.append("No holiday date could be read. Dates must look like 2026-08-10.")
        return df
    if parsed.isna().any():
        warnings.append(f"{_count(int(parsed.isna().sum()), 'holiday row')} with an invalid date were dropped.")
    df = df[parsed.notna()].copy()
    df["date"] = parsed[parsed.notna()].dt.strftime("%Y-%m-%d")
    return df.drop_duplicates("date")


def _check_notes(df, errors, warnings):
    empty = df["shift_id"].isna()
    if empty.any():
        warnings.append(f"{_count(int(empty.sum()), 'note')} with an empty shift_id were dropped.")
        df = df[~empty]
    if df["shift_id"].duplicated().any():
        warnings.append("Some shifts have more than one note; the last one is kept.")
        df = df.drop_duplicates("shift_id", keep="last")
    return df


def _check_payroll(df, errors, warnings):
    _check_key(df, "employee_id", errors)
    if df["account_number"].isna().any() or df["tax_number"].isna().any():
        warnings.append("Some payroll rows have no bank account or tax number (they cannot be compared).")
    return df


_CHECKS = {"shifts": _check_shifts, "employees": _check_employees, "sites": _check_sites,
           "public_holidays": _check_holidays, "shift_notes": _check_notes, "payroll_details": _check_payroll}


def check_file(filename, source):
    """Recognise and validate one uploaded file. `source` is a path, bytes, file object or DataFrame."""
    report = FileReport(filename=str(filename))
    try:
        df = source.copy() if isinstance(source, pd.DataFrame) else read_csv_any(source)
    except ValueError as exc:
        report.errors.append(str(exc))
        return report
    report.rows = len(df)
    kind, missing = identify_file(df.columns, filename)
    report.kind = kind
    if kind is None:
        report.errors.append("This file does not match any expected layout (shifts, employees, sites, public_holidays, shift_notes, payroll_details).")
        return report
    spec = SPECS[kind]
    if spec.get("unused"):
        report.errors.append("weekly_summary.csv is not used by the dashboard, so it was not loaded.")
        return report
    if missing:
        report.errors.append(f"This looks like {FILE_NAMES[kind]} but is missing column(s): {', '.join(missing)}.")
        return report
    if len(df) == 0:
        report.errors.append("The file has a header but no rows.")
        return report
    keep = spec.get("keep") or [c for c in spec["required"] + spec["optional"] if c in df.columns]
    df = df[keep].copy()
    df = _CHECKS[kind](df, report.errors, report.warnings) if kind in _CHECKS else df
    if not report.errors:
        report.data = df.reset_index(drop=True)
    return report


def cross_check(bundle):
    """Warnings about mismatches between the current files. Never blocks."""
    out = []
    shifts, employees, sites = bundle.get("shifts"), bundle.get("employees"), bundle.get("sites")
    notes, payroll = bundle.get("shift_notes"), bundle.get("payroll_details")
    has = lambda d: d is not None and len(d) > 0
    if has(shifts) and has(employees):
        unknown = set(shifts["employee_id"].dropna()) - set(employees["employee_id"])
        if unknown:
            out.append(f"{_count(len(unknown), 'employee ID')} in the shifts are not in the employees file (shown by ID only).")
    if has(shifts) and has(sites):
        unknown = set(shifts["site_id"].dropna()) - set(sites["site_id"])
        if unknown:
            out.append(f"{_count(len(unknown), 'site ID')} in the shifts are not in the sites file (shown by ID only).")
    if has(employees) and has(sites) and "primary_site_id" in employees:
        unknown = set(employees["primary_site_id"].dropna()) - set(sites["site_id"])
        if unknown:
            out.append(f"{_count(len(unknown), 'primary site')} in the employees file are not in the sites file.")
    if has(notes) and has(shifts):
        unknown = set(notes["shift_id"]) - set(shifts["shift_id"])
        if unknown:
            out.append(f"{_count(len(unknown), 'note')} are for shifts that are not in the shifts file.")
    if has(payroll) and has(employees):
        unknown = set(payroll["employee_id"]) - set(employees["employee_id"])
        if unknown:
            out.append(f"{_count(len(unknown), 'payroll row')} are for employees that are not in the employees file.")
    return out
