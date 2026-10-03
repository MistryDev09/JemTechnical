import pandas as pd
import pytest

from src.notes import CATEGORY_LABELS, PILE, classify, classify_notes, normalise

# the classifier is meant to be edited, so these tests guard what must keep working


@pytest.mark.parametrize("text, expected", [
    ("relief no show AGAIN", "relief_no_show"),
    ("relif no show agn", "relief_no_show"),
    ("Next shift guard did not pitch. Had to cover.", "relief_no_show"),
    ("Nexxt shift guuard did not pitch. Had to cover.", "relief_no_show"),
    ("aflos het nie opgedaag nie, moes aanbly", "relief_no_show"),
    ("next shift akafikanga, ngihlale kuze kube 06h00", "relief_no_show"),
    ("hanodver late again, keys missing", "late_handover"),
    ("oorhandiging was laat, gewag vir sleutels", "late_handover"),
    ("masjien is stukkend, alles met die hand gedoen", "equipment_failure"),
    ("gate motor faled, manned it by hand till 06h00", "equipment_failure"),
    ("covering Molefe post, no sow no call", "colleague_no_show"),
    ("ungcobo akezanga namhlanje, ngimele yena", "colleague_no_show"),
    ("Naidoo off sikc again, covered", "colleague_sick_or_leave"),
    ("gedek vir Sibiya, siek gemeld", "colleague_sick_or_leave"),
    ("worked through, Wyk at the clinic", "colleague_sick_or_leave"),
    ("stood in for Fourie", "stood_in_unspecified"),
    ("client says stay till 6am, dont know if office approved", "client_unconfirmed"),
    ("stocktake ran over, client asked us to remain, they know they pay for it", "client_requested"),
    ("klient het ekstra ure gevra vir stocktake", "client_requested"),
    ("Centre manager requested additional cover for stocktake", "client_requested"),
    ("ok", "nothing_useful"), ("-", "nothing_useful"), ("", "nothing_useful"), ("n/a", "nothing_useful"), ("sharp", "nothing_useful"),
    ("all quiet", "nothing_useful"), ("akukho lutho", "nothing_useful"),
])
def test_known_sentences_and_typos(text, expected):
    assert classify(text) == expected


def test_a_failure_beats_a_client_cue():
    # the supervisor says the client signed, but the real reason is a failure
    assert classify("client signed for the extra hours but real reason is relief no show agn") == "relief_no_show"


def test_an_unreadable_note_is_unknown_not_a_category():
    assert classify("the purple elephant visited the loading bay") == "unknown"


def test_every_category_has_a_label_and_a_pile():
    cats = {"client_requested", "client_unconfirmed", "relief_no_show", "colleague_no_show", "late_handover", "equipment_failure",
            "colleague_sick_or_leave", "stood_in_unspecified", "nothing_useful", "unknown"}
    assert cats <= set(CATEGORY_LABELS) and cats <= set(PILE)


def test_classify_notes_keeps_rows_and_columns():
    notes = pd.DataFrame({"shift_id": ["S1", "S2", "S3"], "note": ["relief no show", "ok", "relief no show"], "logged_by": ["a", "b", "c"]})
    out = classify_notes(notes)
    assert list(out.columns) == ["shift_id", "category", "note"] and list(out.shift_id) == ["S1", "S2", "S3"]
    assert list(out.category) == ["relief_no_show", "nothing_useful", "relief_no_show"] and list(out.note) == list(notes.note)


def test_normalise_drops_accents_and_punctuation():
    assert normalise("  Kliënt  het EKSTRA ure!! ") == "klient het ekstra ure"


def test_accuracy_on_the_blind_hand_labelled_sample_has_not_dropped():
    # evaluation/labels/notes_blind_sample.csv was hand-labelled before the rules were written; if an edit to the
    # rules breaks this, the sorting has got worse
    blind = pd.read_csv("evaluation/labels/notes_blind_sample.csv", keep_default_na=False)
    pred = classify_notes(blind[["shift_id", "note"]])
    accuracy = (pred.category.values == blind.category.values).mean()
    assert accuracy >= 0.97, f"accuracy on the blind sample fell to {accuracy:.3f}"


def test_the_committed_note_classifications_file_matches_the_rules():
    notes = pd.read_csv("data/shift_notes.csv", keep_default_na=False)
    saved = pd.read_csv("note_classifications.csv", keep_default_na=False)
    assert (classify_notes(notes).category.values == saved.category.values).all(), "re-run shift_classification.ipynb to refresh note_classifications.csv"
