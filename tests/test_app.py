import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def page_text(at):
    return " ".join(m.value for m in at.markdown)


def test_bundled_data_renders_high_risk_people_sites_and_escalations():
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    text = page_text(at)
    assert "Lerato Motaung" in text
    assert re.search(r"<b>9</b><span>people at 50%\+ risk of going over", text)
    assert "Data up to Wed 12 Aug 2026" in text and "predicting Thu, Fri, Sat and Sun" in text
    assert "By site" in [s.value for s in at.subheader] and "Escalations" in [s.value for s in at.subheader]
    # only people at 50%+ are listed: no lower-risk list, no amber person cards
    assert not any("Everyone else" in e.label or "Show the other" in e.label for e in at.expander)
    assert "Kagiso Molefe" not in text and "45% risk" not in text
    # each listed person has a Resolve button
    resolve = [b for b in at.button if b.label == "Resolve"]
    assert len(resolve) == 9 and "resolve_E1126" in {b.key for b in resolve}


def test_the_two_records_flag_links_to_that_person_under_escalations():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert 'href="#esc-E1126"' in text and 'id="esc-E1126"' in text
    assert text.count('class="tag esc" href="#esc-') == 5


def test_report_and_escalate_all_open_an_email_to_the_escalation_address():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert "Escalate all (18)" in text and "sitenumbersandnames@gmail.com" in text
    assert text.count('href="mailto:sitenumbersandnames@gmail.com?subject=') >= 19      # escalate all + 5 + 13 reports
    assert text.count(">Report</a>") == 18


def test_overlaps_are_cards_not_a_table():
    at = AppTest.from_file(APP, default_timeout=180).run()
    text = page_text(at)
    assert text.count('class="legs"') == 13
    assert not any("Overlap (h)" in list(df.value.columns) for df in at.dataframe)


def test_cleared_data_shows_the_empty_state_and_no_cards():
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["bundle"] = {}
    at.session_state["source"] = "no data"
    at.session_state["messages"] = []
    at.session_state["uploader_key"] = 0
    at.run()
    assert not at.exception
    assert 'class="card ' not in page_text(at)
    assert any("No shifts are loaded" in i.value for i in at.info)
