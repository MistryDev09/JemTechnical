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
    assert not any("Everyone else" in e.label for e in at.expander)
    assert not any("Data checks" in e.label for e in at.expander)          # the data checks section was removed
    # a Resolve button for each person at 50%+, each duplicate and each overlap this week (9 + 5 + 13)
    resolve = [b for b in at.button if b.label == "Resolve"]
    assert len(resolve) == 27 and "resolve_E1126" in {b.key for b in resolve}


def test_people_below_50_percent_are_in_three_drop_downs_without_resolve_buttons():
    at = AppTest.from_file(APP, default_timeout=180).run()
    labels = [e.label for e in at.expander]
    assert "People at 30 to 50% risk (7)" in labels and "People at 20 to 30% risk (7)" in labels and "People at 0 to 20% risk (185)" in labels
    text = page_text(at)
    assert "Kagiso Molefe" in text and "45% risk" in text
    assert "resolve_E1121" not in {b.key for b in at.button}           # Kagiso Molefe is E1121: no button
    assert "Refilwe Nkosi" in text and "28% risk" in text               # 20 to 30% is now shown too
    assert len([b for b in at.button if b.label == "Resolve"]) == 27   # still only the 50%+ people, duplicates and overlaps


def test_every_box_has_a_why_the_hours_happened_control():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert text.count("<summary>Why the hours happened</summary>") == 9 + 7 + 7 + 185
    assert "This week (" in text and "No note this week. Last 4 weeks (" in text and "Nothing useful this week. Last 4 weeks (" in text
    assert "Late handover" in text or "Relief did not arrive or was late" in text


def test_there_is_no_why_control_without_notes():
    at = AppTest.from_file(APP, default_timeout=180).run()
    bundle = dict(at.session_state["bundle"])
    bundle.pop("shift_notes")
    at.session_state["bundle"] = bundle
    at.run()
    assert not at.exception and "Why the hours happened" not in page_text(at)


def test_cards_show_the_usual_hours_still_to_come():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert "usual hours still to come" in text
    assert "Usually works about 2.1 more shifts of 9.6 h, which is 20.2 h more this week. That is 3.9 h more than the 16.2 h left before 55." in text
    assert "That fits within the 19.0 h left" in text and "an average of 49 h a week" in text       # Mandla Sithole
    assert "Has already worked a usual number of shifts this week, so no more usual hours are expected. Any extra shift would use up the 3.2 h left before 55." in text                           # Portia Fourie


def test_the_two_records_flag_links_to_that_person_under_escalations():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert 'href="#esc-E1126"' in text and 'id="esc-E1126"' in text
    assert text.count('class="tag esc" href="#esc-') == 5


def test_there_is_no_email_pop_up_any_more():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert "mailto:" not in text and "sitenumbersandnames" not in text and ">Report</a>" not in text


def test_resolving_an_overtime_person_shows_the_message():
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert 'class="notice' not in page_text(at)
    at.button(key="resolve_E1126").click().run()
    text = page_text(at)
    assert "Sent message to supervisor: resolving an overtime person, Lerato Motaung (sent by internal tool or email)" in text
    assert 'role="status"' in text


def test_resolving_a_duplicate_shows_the_message():
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.button(key="resolve_dup_E1126").click().run()
    assert "Sent message to supervisor: resolving a duplicate, Lerato Motaung / L. Motaung (sent by internal tool or email)" in page_text(at)


def test_resolving_a_shift_overlap_shows_the_message():
    at = AppTest.from_file(APP, default_timeout=180).run()
    key = next(b.key for b in at.button if b.key and b.key.startswith("resolve_overlap_"))
    at.button(key=key).click().run()
    text = page_text(at)
    assert "Sent message to supervisor: resolving a shift overlap, " in text and "(sent by internal tool or email)" in text


def test_escalate_all_shows_one_message_and_the_message_clears_on_the_next_action():
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.button(key="escalate_all").click().run()
    assert "Sent message to supervisor: resolving all 18 escalations (sent by internal tool or email)" in page_text(at)
    at.selectbox[0].select("All sites").run()                       # any other action: the message is gone
    assert "Sent message to supervisor" not in page_text(at)


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
