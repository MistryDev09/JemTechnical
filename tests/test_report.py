from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd

from src.dataset import load_bundled
from src.pipeline import run
from src.report import ESCALATION_EMAIL, MAX_LINK, duplicate_line, mailto, overlap_line


def test_the_address_is_the_agreed_one():
    assert ESCALATION_EMAIL == "sitenumbersandnames@gmail.com"


def test_mailto_has_address_subject_and_body():
    link = mailto("Possible duplicate: A / B", ["line one", "line two"])
    assert link.startswith("mailto:sitenumbersandnames@gmail.com?subject=")
    query = parse_qs(urlparse(link).query)
    assert query["subject"] == ["Possible duplicate: A / B"]
    assert unquote(link.split("body=")[1]) == "line one\nline two"


def test_long_lists_are_cut_with_a_note_and_stay_short():
    lines = [f"Overlapping shifts: Person {i} worked somewhere and somewhere else for a while." for i in range(80)]
    link = mailto("Escalations", lines)
    assert len(link) <= MAX_LINK + 80
    body = unquote(link.split("body=")[1])
    assert "more not included here" in body and body.startswith("Overlapping shifts: Person 0")


def test_the_first_item_is_always_kept():
    assert "x" * 50 in unquote(mailto("s", ["x" * 3000]).split("body=")[1])


def test_report_text_never_contains_bank_or_tax_values():
    bundle = load_bundled()
    banned = set(bundle["payroll_details"].account_number) | set(bundle["payroll_details"].tax_number)
    res = run(bundle)
    lines = [duplicate_line(r.names, r.employee_ids, r.evidence, r.severity) for r in res.duplicates.itertuples()]
    assert len(lines) == 5 and all("same bank account" in l or "same ID number" in l for l in lines)
    text = "\n".join(lines)
    assert not any(v in text for v in banned)


def test_overlap_line_describes_both_shifts():
    a, b = pd.Timestamp("2026-08-10 06:00"), pd.Timestamp("2026-08-10 14:15")
    c, d = pd.Timestamp("2026-08-10 08:00"), pd.Timestamp("2026-08-10 12:00")
    line = overlap_line("Pieter Van Wyk", "ST-06 Gqeberha Plant", a, b, "ST-05 Durban Point Depot", c, d, 4.0, "High", True)
    assert "Pieter Van Wyk" in line and "ST-06 Gqeberha Plant" in line and "4.00 h overlap, different provinces; High" in line
    night = overlap_line("X", "A", pd.Timestamp("2026-08-10 20:00"), pd.Timestamp("2026-08-11 06:00"), "B", c, d, 1.0, "Medium", False)
    assert "(Tue)" in night
