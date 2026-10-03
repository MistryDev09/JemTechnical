"""The current set of files: load the bundled data, apply uploads (overwrite or append per file), hash for caching."""
import hashlib
from pathlib import Path

import pandas as pd

from .validate import USED_KINDS, SPECS, check_file, read_csv_any, identify_file

BUNDLED_DIR = Path(__file__).resolve().parent.parent / "data"
KEYS = {kind: [SPECS[kind]["key"]] for kind in USED_KINDS}


def load_bundled(folder=BUNDLED_DIR):
    """Read every recognised, used CSV in the folder. A bundled file that fails validation raises."""
    bundle = {}
    for path in sorted(Path(folder).glob("*.csv")):
        try:
            kind, _ = identify_file(read_csv_any(path).columns, path.name)
        except ValueError:
            continue
        if kind is None or kind not in USED_KINDS:
            continue
        report = check_file(path.name, path)
        if not report.ok:
            raise ValueError(f"Bundled file {path.name} is invalid: {' '.join(report.errors)}")
        bundle[kind] = report.data
    return bundle


def apply_upload(current, uploads):
    """Return a new bundle. `uploads` is a list of (kind, DataFrame, mode), mode 'overwrite' or 'append'.

    Overwrite replaces that whole file; the other files stay. Append merges by the file's key and a row
    with an existing key updates it.
    """
    new = {k: v.copy() for k, v in current.items()}
    for kind, df, mode in uploads:
        if kind not in KEYS:
            raise ValueError(f"{kind} cannot be loaded")
        if mode == "append" and kind in new and len(new[kind]):
            combined = pd.concat([new[kind], df], ignore_index=True)
            new[kind] = combined.drop_duplicates(subset=KEYS[kind], keep="last").reset_index(drop=True)
        else:
            new[kind] = df.reset_index(drop=True)
    return new


def content_hash(bundle):
    """Stable fingerprint of the current files, used as a cache key."""
    h = hashlib.sha256()
    for kind in sorted(bundle):
        df = bundle[kind]
        h.update(kind.encode())
        h.update("|".join(map(str, df.columns)).encode())
        h.update(pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes())
    return h.hexdigest()
