"""Report and escalate by email: build a pre-filled mailto link. Nothing is sent by the app itself.

The text never contains bank or tax values; it only says what kind of evidence was found.
"""
from urllib.parse import quote

import pandas as pd

ESCALATION_EMAIL = "sitenumbersandnames@gmail.com"     # for now; change here when the real address is known
MAX_LINK = 1800                                         # keep the link short enough for most email apps


def _when(start, end):
    text = f"{start:%a %d %b %H:%M}-{end:%H:%M}"
    return text + (f" ({end:%a})" if end.date() != start.date() else "")


def _name(value, fallback):
    return value if isinstance(value, str) and value else fallback


def duplicate_line(names, employee_ids, evidence, severity):
    who = " / ".join(n for n in names if isinstance(n, str)) or " / ".join(employee_ids)
    return f"Possible duplicate record: {who} (employee IDs {', '.join(employee_ids)}). Evidence: {evidence}. Severity: {severity}."


def overlap_line(person, site_a, a_start, a_end, site_b, b_start, b_end, hours, severity, different_province):
    province = ", different provinces" if different_province else ""
    return (f"Overlapping shifts: {person} worked {site_a} {_when(a_start, a_end)} and {site_b} {_when(b_start, b_end)} "
            f"({hours:.2f} h overlap{province}; {severity}).")


def mailto(subject, lines, address=ESCALATION_EMAIL, max_len=MAX_LINK):
    """A mailto link with the subject and one line per item. Long lists are cut with a note."""
    head = f"mailto:{address}?subject={quote(subject, safe='')}&body="
    kept = []
    for i, line in enumerate(lines):
        trial = quote("\n".join(kept + [line]), safe="")
        if kept and len(head) + len(trial) > max_len:
            kept.append(f"(+{len(lines) - i} more not included here, see the dashboard.)")
            break
        kept.append(line)
    return head + quote("\n".join(kept), safe="")
