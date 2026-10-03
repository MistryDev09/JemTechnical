import numpy as np
import pandas as pd
import pytest

from src.dataset import load_bundled
from src.forecast import MIN_WEEKS, build_table, test_indices as fold_indices
from src.hours import attribute_hours, parse_shifts
from src.integrity import add_person_key, find_duplicate_people
from src.pipeline import run


@pytest.fixture(scope="module")
def bundle():
    return load_bundled()


def truncated(bundle, last_date):
    out = dict(bundle)
    out["shifts"] = bundle["shifts"][pd.to_datetime(bundle["shifts"]["shift_date"]) <= pd.Timestamp(last_date)]
    return out


def test_fold_count_follows_the_number_of_weeks():
    assert fold_indices(10) == [4, 5, 6, 7, 8]       # the notebook's five test weeks
    assert fold_indices(MIN_WEEKS) == [4]            # the smallest case: one test week
    assert fold_indices(14) == [8, 9, 10, 11, 12]    # always the last five complete weeks


def test_features_use_only_what_was_known_at_the_cutoff(bundle):
    shifts = parse_shifts(bundle["shifts"])
    people = find_duplicate_people(bundle["employees"], bundle["payroll_details"])
    seg = add_person_key(attribute_hours(shifts, bundle["public_holidays"]), people)
    seg = seg.merge(shifts[["shift_id", "shift_date"]], on="shift_id")[["shift_id", "person_key", "shift_date", "week_start", "hours"]]
    weeks = pd.date_range(seg.week_start.min(), pd.Timestamp("2026-08-10"), freq="7D")
    persons = sorted(seg.person_key.unique())
    table = build_table(seg, persons, weeks, 2)
    rng = np.random.default_rng(0)
    for r in table[table.week_start < weeks[-1]].sample(30, random_state=1).itertuples():
        mine = seg[(seg.person_key == r.person_key) & (seg.week_start == r.week_start)]
        known = mine[mine.shift_date <= r.week_start + pd.Timedelta(days=2)]
        assert known.hours.sum() == pytest.approx(r.hours_so_far)
        prior = seg[(seg.person_key == r.person_key) & (seg.week_start < r.week_start)]
        assert prior.hours.sum() / r.n_prior_weeks == pytest.approx(r.avg_weekly_hours_prior)
    assert table.loc[table.week_start == weeks[-1], "breach"].isna().all()


@pytest.mark.parametrize("last_date,weekday,days,week", [
    ("2026-08-10", "Monday", ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], "2026-08-10"),
    ("2026-08-07", "Friday", ["Saturday", "Sunday"], "2026-08-03")])
def test_the_weekday_comes_from_the_data(bundle, last_date, weekday, days, week):
    res = run(truncated(bundle, last_date))
    assert res.status == "model"
    assert res.cutoff.day_name() == weekday and res.predicted_days == days
    assert res.week_start == pd.Timestamp(week)
    assert len(res.predictions) == 213 and res.predictions.will_breach.isin([0, 1]).all()


def test_a_file_ending_on_sunday_shows_who_went_over_instead_of_predicting(bundle):
    res = run(truncated(bundle, "2026-08-09"))
    assert res.status == "week_complete" and res.predictions is None and res.predicted_days == []
    assert res.week_start == pd.Timestamp("2026-08-03")
    over = res.people[res.people.level == "Over"]
    assert (over.hours_so_far > 55).all() and len(over) > 0


def test_too_little_history_gives_no_prediction_but_still_shows_hours(bundle):
    short = run(truncated(bundle, "2026-07-08"))         # 5 weeks including the one in progress
    assert short.status == "not_enough_history" and "6" in short.message
    assert short.predictions is None and short.people["hours_so_far"].max() > 0
    smallest = run(truncated(bundle, "2026-07-15"))      # exactly 6 weeks: one test week
    assert smallest.status in {"model", "not_enough_history"} and smallest.n_weeks == 6
