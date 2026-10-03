"""Download files: predictions.csv with exactly employee_id,will_breach,risk_score."""

COLUMNS = ["employee_id", "will_breach", "risk_score"]


def predictions_csv(result):
    """predictions.csv text for a result that has a prediction. Raises if the format would be wrong."""
    df = result.predictions
    if df is None:
        raise ValueError("There is no prediction to export.")
    if list(df.columns) != COLUMNS:
        raise ValueError(f"predictions must have exactly the columns {COLUMNS}")
    if not df["employee_id"].is_unique:
        raise ValueError("employee_id must be unique")
    if not df["will_breach"].isin([0, 1]).all():
        raise ValueError("will_breach must be 0 or 1")
    if not df["risk_score"].between(0, 1).all():
        raise ValueError("risk_score must be between 0 and 1")
    return df.to_csv(index=False)
