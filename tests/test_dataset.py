import pandas as pd

from src.dataset import apply_upload, code_version, content_hash, load_bundled


def test_bundled_data_loads_every_used_file_and_payroll_is_minimal():
    bundle = load_bundled()
    assert set(bundle) == {"shifts", "employees", "sites", "public_holidays", "shift_notes", "payroll_details"}
    assert list(bundle["payroll_details"].columns) == ["employee_id", "account_number", "tax_number"]
    assert len(bundle["shifts"]) == 8863 and len(bundle["employees"]) == 213


def test_overwrite_replaces_only_the_uploaded_file():
    bundle = load_bundled()
    new_sites = pd.DataFrame({"site_id": ["X"], "site_name": ["X site"], "province": ["P"]})
    out = apply_upload(bundle, [("sites", new_sites, "overwrite")])
    assert list(out["sites"]["site_id"]) == ["X"]
    assert out["shifts"].equals(bundle["shifts"]) and len(bundle["sites"]) == 6      # original untouched


def test_append_adds_new_keys_and_updates_existing_ones():
    bundle = load_bundled()
    first = bundle["shifts"].iloc[0]
    updated = first.copy(); updated["clock_out_time"] = "23:45"
    new = first.copy(); new["shift_id"] = "S999999"
    out = apply_upload(bundle, [("shifts", pd.DataFrame([updated, new]), "append")])
    assert len(out["shifts"]) == len(bundle["shifts"]) + 1
    assert out["shifts"].set_index("shift_id").loc[first["shift_id"], "clock_out_time"] == "23:45"
    assert "S999999" in set(out["shifts"]["shift_id"])


def test_append_when_the_file_is_missing_just_loads_it():
    out = apply_upload({}, [("sites", pd.DataFrame({"site_id": ["A"], "site_name": ["a"], "province": ["p"]}), "append")])
    assert list(out["sites"]["site_id"]) == ["A"]


def test_each_file_has_its_own_mode():
    bundle = load_bundled()
    emp = pd.DataFrame({"employee_id": ["E9999"], "full_name": ["New Person"], "id_number": ["1"]})
    sites = pd.DataFrame({"site_id": ["ST-09"], "site_name": ["New"], "province": ["P"]})
    out = apply_upload(bundle, [("employees", emp, "append"), ("sites", sites, "overwrite")])
    assert len(out["employees"]) == 214 and list(out["sites"]["site_id"]) == ["ST-09"]


def test_content_hash_changes_with_the_data():
    bundle = load_bundled()
    assert content_hash(bundle) == content_hash({k: v.copy() for k, v in bundle.items()})
    changed = apply_upload(bundle, [("sites", bundle["sites"].iloc[:3], "overwrite")])
    assert content_hash(changed) != content_hash(bundle)


def test_code_version_changes_when_the_source_changes(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    before = code_version(tmp_path)
    assert before == code_version(tmp_path) and len(before) == 12
    (tmp_path / "a.py").write_text("x = 2\n")
    assert code_version(tmp_path) != before
    assert code_version() == code_version()                  # the real src folder is stable between calls
