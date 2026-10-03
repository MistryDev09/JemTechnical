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
    at = AppTest.from_file(APP, default_timeout=180).run()
    text = page_text(at)
    popovers = [b for b in at.get("popover") if b.proto.popover.label == "Why the hours happened"]
    assert len(popovers) == 9 + 7 + 7                                   # full boxes: a pop-up; the Resolve button is in the same box
    assert text.count("<summary>Why the hours happened</summary>") == 185     # compact boxes: opens in place
    assert "This week (" in text and "No note this week. Last 4 weeks (" in text and "Nothing useful this week. Last 4 weeks (" in text


def test_there_is_no_why_control_without_notes():
    at = AppTest.from_file(APP, default_timeout=180).run()
    bundle = dict(at.session_state["bundle"])
    bundle.pop("shift_notes")
    at.session_state["bundle"] = bundle
    at.run()
    assert not at.exception and "Why the hours happened" not in page_text(at)


def test_cards_show_the_usual_shifts_and_hours_still_to_come_and_no_explanatory_text():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert "usual shifts left this week" in text and "usual hours still to come" in text
    assert "<b>2.1</b><span>usual shifts left this week" in text and "<b>20.2</b><span>usual hours still to come" in text     # Lerato Motaung
    assert "Usually works about" not in text and "Has already worked a usual number of shifts" not in text and 'class="note"' not in text


def test_the_two_records_flag_links_to_that_person_under_escalations():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert 'href="#esc-E1126"' in text and 'id="esc-E1126"' in text
    assert text.count('class="tag esc" href="#esc-') == 5


def test_people_also_escalated_for_overlapping_shifts_have_a_tag_that_links_to_the_overlap():
    text = page_text(AppTest.from_file(APP, default_timeout=180).run())
    assert text.count("Also escalated: overlapping shifts") == 9                  # the nine double-dipping people
    assert 'href="#esc-overlap-E1099"' in text and 'id="esc-overlap-E1099"' in text
    assert "Also escalated: duplicate person" not in text                          # duplicates already carry the 2 records link


def test_pattern_mismatch_block_is_hidden_on_the_bundled_data_and_shown_when_there_are_some():
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert "not on the night pattern" not in page_text(at)
    emp = at.session_state["bundle"]["employees"].copy()
    emp.loc[emp.employee_id == "E1004", "shift_pattern"] = "day"
    at.session_state["bundle"] = {**at.session_state["bundle"], "employees": emp}
    at.run()
    text = page_text(at)
    assert not at.exception and "not on the night pattern (for review)" in text
    assert any("36 in all the data, 2 this week" in c.value for c in at.caption)
    assert "Pattern: day" in text and "still counted" in text
    assert len([b for b in at.button if b.key and b.key.startswith("resolve_pattern_")]) == 2
    assert any(b.label == "Escalate all (20)" for b in at.button)             # 18 records + the 2 mismatches this week


def test_the_app_reloads_src_when_it_changed_after_a_deploy(monkeypatch):
    import sys

    import src.pipeline as pipeline

    AppTest.from_file(APP, default_timeout=180).run()                  # first load records the fingerprint of src/
    original_run = pipeline.run
    monkeypatch.setattr(pipeline, "run", lambda bundle: (_ for _ in ()).throw(RuntimeError("stale src module")))
    monkeypatch.setattr(sys, "_jem_src_fingerprint", "an older version of src/")     # as if src/ changed since it was imported
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception and "Lerato Motaung" in page_text(at)       # the stale module was reloaded, so the real run() was used
    assert sys.modules["src.pipeline"].run is not None and original_run is not None


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
