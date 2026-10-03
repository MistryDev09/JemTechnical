import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def page_text(at):
    return " ".join(m.value for m in at.markdown)


def test_bundled_data_renders_flagged_people_sites_and_escalations():
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception
    text = page_text(at)
    assert text.count('class="card ') >= 46 and "Lerato Motaung" in text
    assert re.search(r"<b>46</b><span>people predicted to go over", text)
    assert "Data up to Wed 12 Aug 2026" in text and "predicting Thu, Fri, Sat and Sun" in text
    assert "By site" in [s.value for s in at.subheader]
    assert any("Escalations" in e.label for e in at.expander)


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
