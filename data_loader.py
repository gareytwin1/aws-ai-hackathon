import pandas as pd
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
REF_DIR = DATA_DIR / "reference_docs"

_cache = {}


def _load(name: str) -> pd.DataFrame:
    if name not in _cache:
        df = pd.read_csv(DATA_DIR / name)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        if "onset_timestamp" in df.columns:
            df["onset_timestamp"] = pd.to_datetime(df["onset_timestamp"])
        if "reported_date" in df.columns:
            df["reported_date"] = pd.to_datetime(df["reported_date"])
        _cache[name] = df
    return _cache[name]


def scada() -> pd.DataFrame:
    return _load("scada_timeseries.csv")


def leak_events() -> pd.DataFrame:
    return _load("labeled_leak_events.csv")


def false_positive_events() -> pd.DataFrame:
    return _load("labeled_false_positive_events.csv")


def pipeline_metadata() -> pd.DataFrame:
    return _load("pipeline_segment_metadata.csv")


def gas_composition() -> pd.DataFrame:
    return _load("gas_composition.csv")


def weather() -> pd.DataFrame:
    return _load("weather_conditions.csv")


def inspection_history() -> pd.DataFrame:
    return _load("inspection_history.csv")


def cathodic_protection() -> pd.DataFrame:
    return _load("cathodic_protection.csv")


def valve_status() -> pd.DataFrame:
    df = _load("valve_status.csv")
    if "segment_id" in df.columns:
        df = df.copy()
        df["segment_id"] = df["segment_id"].astype(str).str.zfill(2).apply(lambda x: f"SEG-{x}")
    return df


def row_encroachment() -> pd.DataFrame:
    return _load("row_encroachment.csv")


def operating_procedures() -> str:
    return (REF_DIR / "pipeline_operating_procedures.md").read_text()


def regulatory_reference() -> str:
    return (REF_DIR / "dot_phmsa_regulatory_reference.md").read_text()


OPERATING_ENVELOPES = {
    "ST-01": {"mile": 0, "pressure_min": 760, "pressure_max": 800, "flow_min": 6.0, "flow_max": 6.5},
    "ST-02": {"mile": 28, "pressure_min": 745, "pressure_max": 785, "flow_min": 5.9, "flow_max": 6.4},
    "ST-03": {"mile": 52, "pressure_min": 735, "pressure_max": 775, "flow_min": 5.9, "flow_max": 6.4},
    "ST-04": {"mile": 78, "pressure_min": 755, "pressure_max": 795, "flow_min": 5.9, "flow_max": 6.4},
    "ST-05": {"mile": 104, "pressure_min": 740, "pressure_max": 780, "flow_min": 5.8, "flow_max": 6.3},
    "ST-06": {"mile": 130, "pressure_min": 730, "pressure_max": 770, "flow_min": 5.8, "flow_max": 6.3},
    "ST-07": {"mile": 158, "pressure_min": 720, "pressure_max": 760, "flow_min": 5.7, "flow_max": 6.2},
    "ST-08": {"mile": 200, "pressure_min": 710, "pressure_max": 750, "flow_min": 5.7, "flow_max": 6.2},
}

LEAK_THRESHOLDS = {
    "seep": {"rate_min": 0, "rate_max": 0.2, "pressure_drop": "3-8 psi / 30 min", "action": "Monitor"},
    "moderate": {"rate_min": 0.2, "rate_max": 0.8, "pressure_drop": "8-20 psi / 15 min", "action": "Isolate segment"},
    "significant": {"rate_min": 0.8, "rate_max": 2.0, "pressure_drop": "20-50 psi / 10 min", "action": "Isolate segment"},
    "near_rupture": {"rate_min": 2.0, "rate_max": 999, "pressure_drop": ">50 psi / <5 min", "action": "Immediate ESD"},
}

SEGMENT_STATIONS = {
    "SEG-01": ("ST-01", "ST-02"),
    "SEG-02": ("ST-02", "ST-03"),
    "SEG-03": ("ST-03", "ST-04"),
    "SEG-04": ("ST-04", "ST-05"),
    "SEG-05": ("ST-05", "ST-06"),
    "SEG-06": ("ST-06", "ST-07"),
    "SEG-07": ("ST-07", "ST-08"),
}
