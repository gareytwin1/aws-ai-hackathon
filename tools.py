import json
import pandas as pd
from strands import tool
import data_loader as dl


@tool
def scan_for_anomalies(time_start: str = "", time_end: str = "") -> str:
    """Scan SCADA data for anomalies in a time window. Returns events where mass_balance_deficit
    exceeds normal thresholds or pressure is outside operating envelope. If no time range given,
    scans the full dataset for all flagged events.

    Args:
        time_start: ISO datetime start of window (e.g. '2025-12-12T23:00'). Empty string for full scan.
        time_end: ISO datetime end of window (e.g. '2025-12-13T01:00'). Empty string for full scan.
    """
    df = dl.scada()

    if time_start and time_end:
        mask = (df["timestamp"] >= pd.to_datetime(time_start)) & (df["timestamp"] <= pd.to_datetime(time_end))
        df = df[mask]

    anomalies = df[df["event_flag"] != "normal"].copy()

    if anomalies.empty:
        deficit_threshold = 0.15
        high_deficit = df[df["mass_balance_deficit_mmscfd"] > deficit_threshold]
        if high_deficit.empty:
            return json.dumps({"status": "no_anomalies", "rows_scanned": len(df)})
        anomalies = high_deficit

    results = []
    for _, row in anomalies.iterrows():
        envelope = dl.OPERATING_ENVELOPES.get(row["station_id"], {})
        pressure_status = "normal"
        if envelope:
            if row["pressure_psi"] < envelope["pressure_min"]:
                pressure_status = f"BELOW envelope (min={envelope['pressure_min']})"
            elif row["pressure_psi"] > envelope["pressure_max"]:
                pressure_status = f"ABOVE envelope (max={envelope['pressure_max']})"

        results.append({
            "timestamp": str(row["timestamp"]),
            "station_id": row["station_id"],
            "station_type": row["station_type"],
            "event_flag": row["event_flag"],
            "pressure_psi": round(row["pressure_psi"], 2),
            "pressure_status": pressure_status,
            "flow_mmscfd": round(row["flow_mmscfd"], 3),
            "mass_balance_deficit_mmscfd": round(row["mass_balance_deficit_mmscfd"], 4),
            "temperature_f": round(row["temperature_f"], 1),
            "compressor_status": row["compressor_status"],
            "valve_position_pct": round(row["valve_position_pct"], 1),
            "line_pack_mmscf": round(row["line_pack_mmscf"], 3),
        })

    summary = {"total_anomalies": len(results), "rows_scanned": len(df)}
    flag_counts = {}
    for r in results:
        flag_counts[r["event_flag"]] = flag_counts.get(r["event_flag"], 0) + 1
    summary["event_flag_counts"] = flag_counts

    if len(results) > 50:
        summary["note"] = f"Showing first 50 of {len(results)} anomalies. Narrow time window for details."
        results = results[:50]

    return json.dumps({"summary": summary, "anomalies": results}, default=str)


@tool
def get_event_details(timestamp: str, station_id: str = "", segment_id: str = "", window_minutes: int = 60) -> str:
    """Get detailed SCADA readings around a specific event, plus corroborating context
    (weather, valve status, compressor activity). Use this to investigate a specific anomaly.

    Args:
        timestamp: ISO datetime of the event center (e.g. '2025-12-12T23:48')
        station_id: Station to focus on (e.g. 'ST-02'). If empty, returns all stations.
        segment_id: Segment to look up (e.g. 'SEG-02'). Used for valve/integrity context.
        window_minutes: Minutes before and after the event to include. Default 60.
    """
    center = pd.to_datetime(timestamp)
    delta = pd.Timedelta(minutes=window_minutes)

    df = dl.scada()
    mask = (df["timestamp"] >= center - delta) & (df["timestamp"] <= center + delta)
    if station_id:
        mask = mask & (df["station_id"] == station_id)
    window = df[mask].copy()

    readings = []
    for _, row in window.iterrows():
        readings.append({
            "timestamp": str(row["timestamp"]),
            "station_id": row["station_id"],
            "pressure_psi": round(row["pressure_psi"], 2),
            "flow_mmscfd": round(row["flow_mmscfd"], 3),
            "mass_balance_deficit_mmscfd": round(row["mass_balance_deficit_mmscfd"], 4),
            "temperature_f": round(row["temperature_f"], 1),
            "compressor_status": row["compressor_status"],
            "compressor_speed_rpm": row["compressor_speed_rpm"],
            "valve_position_pct": round(row["valve_position_pct"], 1),
            "line_pack_mmscf": round(row["line_pack_mmscf"], 3),
            "event_flag": row["event_flag"],
        })

    weather_df = dl.weather()
    w_mask = (weather_df["timestamp"] >= center - delta) & (weather_df["timestamp"] <= center + delta)
    weather_data = []
    for _, row in weather_df[w_mask].iterrows():
        weather_data.append({
            "timestamp": str(row["timestamp"]),
            "ambient_temp_f": round(row["ambient_temp_f"], 1),
            "wind_speed_mph": round(row["wind_speed_mph"], 1),
            "precipitation_in": round(row["precipitation_in"], 2),
            "ground_temp_f": round(row["ground_temp_f"], 1),
            "frost_heave_risk": row["frost_heave_risk"],
        })

    valve_data = []
    if segment_id:
        v_df = dl.valve_status()
        v_mask = v_df["segment_id"] == segment_id
        date_mask = v_df["date"] == center.normalize()
        valve_rows = v_df[v_mask & date_mask]
        for _, row in valve_rows.iterrows():
            valve_data.append({
                "valve_id": row["valve_id"],
                "segment_id": row["segment_id"],
                "position_pct": row["position_pct"],
                "state": row["state"],
                "response_time_sec": row["response_time_sec"],
                "leak_test_result": row["leak_test_result"],
            })

    all_stations_at_event = df[
        (df["timestamp"] >= center - pd.Timedelta(minutes=5)) &
        (df["timestamp"] <= center + pd.Timedelta(minutes=5))
    ]
    cross_station = []
    for _, row in all_stations_at_event.iterrows():
        cross_station.append({
            "station_id": row["station_id"],
            "pressure_psi": round(row["pressure_psi"], 2),
            "mass_balance_deficit_mmscfd": round(row["mass_balance_deficit_mmscfd"], 4),
            "flow_mmscfd": round(row["flow_mmscfd"], 3),
        })

    if len(readings) > 100:
        step = max(1, len(readings) // 100)
        readings = readings[::step]

    return json.dumps({
        "event_center": str(center),
        "window_minutes": window_minutes,
        "scada_readings": readings,
        "weather_context": weather_data,
        "valve_context": valve_data,
        "cross_station_snapshot": cross_station,
        "source_file": "scada_timeseries.csv, weather_conditions.csv, valve_status.csv",
    }, default=str)


@tool
def check_segment_integrity(segment_id: str) -> str:
    """Check integrity history for a pipeline segment: ILI inspection results,
    cathodic protection readings, and right-of-way encroachment records.
    Use this to assess if a segment has pre-existing vulnerabilities.

    Args:
        segment_id: Segment ID (e.g. 'SEG-02')
    """
    meta = dl.pipeline_metadata()
    seg_meta = meta[meta["segment_id"] == segment_id]
    metadata = {}
    if not seg_meta.empty:
        row = seg_meta.iloc[0]
        metadata = {
            "segment_id": segment_id,
            "from_station": row["from_station"],
            "to_station": row["to_station"],
            "length_miles": row["length_miles"],
            "diameter_in": row["diameter_in"],
            "wall_thickness_in": row["wall_thickness_in"],
            "material_grade": row["material_grade"],
            "maop_psi": row["maop_psi"],
            "elevation_start_ft": row["elevation_start_ft"],
            "elevation_end_ft": row["elevation_end_ft"],
        }

    insp = dl.inspection_history()
    seg_insp = insp[insp["segment_id"] == segment_id]
    inspections = []
    for _, row in seg_insp.iterrows():
        inspections.append({
            "inspection_id": row["inspection_id"],
            "date": str(row.get("date", "")),
            "inspection_type": row.get("inspection_type", ""),
            "result": row.get("result", ""),
            "anomaly_count": int(row.get("anomaly_count", 0)),
            "max_depth_pct_wt": row.get("max_depth_pct_wt", None),
            "anomaly_type": row.get("anomaly_type", ""),
        })

    cp = dl.cathodic_protection()
    seg_cp = cp[cp["segment_id"] == segment_id]
    cp_summary = {}
    if not seg_cp.empty:
        cp_summary = {
            "total_readings": len(seg_cp),
            "criteria_met_pct": round(100 * (seg_cp["criteria_met"] == "Pass").mean(), 1),
            "avg_pipe_to_soil_v": round(seg_cp["pipe_to_soil_v"].mean(), 3),
            "min_pipe_to_soil_v": round(seg_cp["pipe_to_soil_v"].min(), 3),
            "recent_failures": len(seg_cp[(seg_cp["criteria_met"] == "Fail")]),
        }

    enc = dl.row_encroachment()
    seg_enc = enc[enc["segment_id"] == segment_id]
    encroachments = []
    for _, row in seg_enc.iterrows():
        encroachments.append({
            "encroachment_id": row["encroachment_id"],
            "mile_marker": row["mile_marker"],
            "encroachment_type": row["encroachment_type"],
            "status": row["status"],
            "risk_level": row["risk_level"],
            "distance_from_pipe_ft": row["distance_from_pipe_ft"],
        })

    return json.dumps({
        "segment_metadata": metadata,
        "inspection_history": inspections,
        "cathodic_protection_summary": cp_summary,
        "encroachment_records": encroachments,
        "source_files": "pipeline_segment_metadata.csv, inspection_history.csv, cathodic_protection.csv, row_encroachment.csv",
    }, default=str)


@tool
def get_operating_envelope(station_id: str = "") -> str:
    """Get the normal operating envelope for a station or all stations,
    including pressure/flow ranges, leak classification thresholds,
    false-positive signatures, and the escalation ladder.

    Args:
        station_id: Station ID (e.g. 'ST-02'). Empty string returns all stations.
    """
    if station_id:
        envelope = dl.OPERATING_ENVELOPES.get(station_id, {})
        envelopes = {station_id: envelope} if envelope else {}
    else:
        envelopes = dl.OPERATING_ENVELOPES

    false_positive_signatures = {
        "compressor_start": {
            "stations": "ST-01, ST-04 (compressor stations)",
            "pressure_effect": "+15-25 psi locally",
            "flow_effect": "+0.3-0.5 MMSCFD spike",
            "duration": "settles in 5-15 minutes",
            "key_discriminator": "mass_balance_deficit stays near zero",
        },
        "valve_change": {
            "pressure_effect": "+/-8-15 psi across segment",
            "duration": "re-equilibrates in 8-20 minutes",
            "key_discriminator": "mass_balance_deficit stays near zero, both stations affected",
        },
        "temperature_line_pack": {
            "pressure_effect": "-5 to -12 psi across ALL segments equally",
            "flow_effect": "apparent deficit 0.15-0.25 MMSCFD",
            "rule_of_thumb": "every 10°F drop costs ~0.18-0.22 MMSCF per 26-mile segment",
            "key_discriminator": "affects ALL segments equally (not localized to one)",
        },
    }

    escalation_ladder = [
        "Deficit >0.15 MMSCFD sustained >10 min and unexplained → escalate to potential leak",
        "Leak rate >0.3 MMSCFD → isolate the segment",
        "Leak rate >1.0 MMSCFD → emergency shutdown (ESD)",
        "Pressure drop >50 psi in <5 min → immediate isolation regardless",
        "Pressure exceeds 850 psi (MAOP) → reduce compressor output",
        "Pressure exceeds 900 psi (design) → ESD",
    ]

    return json.dumps({
        "operating_envelopes": envelopes,
        "leak_classification": dl.LEAK_THRESHOLDS,
        "false_positive_signatures": false_positive_signatures,
        "escalation_ladder": escalation_ladder,
        "source": "pipeline_operating_procedures.md — Normal Operating Envelopes section",
    }, default=str)


@tool
def get_regulatory_requirements() -> str:
    """Get DOT PHMSA regulatory requirements for incident reporting:
    what triggers a reportable incident, notification timelines,
    NRC contact info, and required Form 7100.1 fields."""
    return json.dumps({
        "incident_triggers": [
            "Death or hospitalization injury",
            "Property damage >= $50,000 (including gas cost)",
            "Unintentional gas loss >= 3 MMSCF",
            "Operator-judged significance",
            "Uncontrolled release with fire/explosion",
            "Any emergency shutdown (ESD)",
        ],
        "notification_requirements": {
            "nrc_phone_call": "Within 1 hour of confirmed detection",
            "nrc_number": "1-800-424-8802 (24/7)",
            "phmsa_form_7100_1": "Written report within 30 days via https://portal.phmsa.dot.gov",
            "safety_related_condition_7100_2": "Within 5 days if MAOP exceeded or imminent hazard",
            "texas_rrc": "Mirrors federal requirements, plus triggers for releases near schools/hospitals or causing evacuation",
        },
        "form_7100_1_required_fields": [
            "Operator ID and pipeline system ID",
            "Incident date/time (UTC)",
            "GPS coordinates and mile marker",
            "Incident type and cause category",
            "Release volume (MCF) and leak rate",
            "Fatalities and injuries",
            "Property damage estimate",
            "Whether release reached a High Consequence Area (HCA)",
            "Isolation method and valve IDs used",
            "NRC report number",
            "Emergency response timeline",
        ],
        "volume_thresholds": {
            "at_0.5_mmscfd": "3 MMSCF threshold reached in 6 days",
            "at_2.0_mmscfd": "3 MMSCF threshold reached in 1.5 days",
            "at_5.0_mmscfd": "3 MMSCF threshold reached in 14.4 hours",
        },
        "penalties": "Up to $2.7M per violation",
        "source": "dot_phmsa_regulatory_reference.md — 49 CFR Part 191",
    }, default=str)


@tool
def list_labeled_events() -> str:
    """List all labeled events from the ground truth dataset:
    5 confirmed leaks and 15 confirmed false positives.
    Use this as a starting point for analysis."""
    leaks = dl.leak_events()
    fps = dl.false_positive_events()

    leak_list = []
    for _, row in leaks.iterrows():
        leak_list.append({
            "event_id": row["event_id"],
            "onset_timestamp": str(row["onset_timestamp"]),
            "mile_marker": row["true_leak_location_mile_marker"],
            "affected_segment": row["affected_segment"],
            "leak_rate_mmscfd": row["leak_rate_mmscfd"],
            "severity": row["severity"],
            "detection_lag_minutes": row["detection_lag_minutes"],
        })

    fp_list = []
    for _, row in fps.iterrows():
        fp_list.append({
            "event_id": row["event_id"],
            "timestamp": str(row["timestamp"]),
            "station_id": row["station_id"],
            "fp_type": row["fp_type"],
            "pressure_drop_psi": row["pressure_drop_psi"],
            "duration_minutes": row["duration_minutes"],
            "explanation": row["explanation"],
        })

    return json.dumps({
        "confirmed_leaks": leak_list,
        "confirmed_false_positives": fp_list,
        "source_files": "labeled_leak_events.csv, labeled_false_positive_events.csv",
    }, default=str)


@tool
def get_gas_composition(station_id: str = "", date: str = "") -> str:
    """Get gas composition data for accurate mass balance and line pack calculations.

    Args:
        station_id: Filter by station (e.g. 'ST-03'). Empty for all.
        date: Filter by date (e.g. '2025-12-15'). Empty for all.
    """
    df = dl.gas_composition()
    if station_id:
        df = df[df["station_id"] == station_id]
    if date:
        df = df[df["date"] == pd.to_datetime(date)]

    records = []
    for _, row in df.iterrows():
        records.append({
            "date": str(row["date"].date()),
            "station_id": row["station_id"],
            "methane_pct": round(row["methane_pct"], 2),
            "ethane_pct": round(row["ethane_pct"], 2),
            "heating_value_btu_scf": round(row["heating_value_btu_scf"], 1),
            "specific_gravity": round(row["specific_gravity"], 4),
            "compressibility_factor_z": round(row["compressibility_factor_z"], 4),
            "h2s_ppm": round(row["h2s_ppm"], 2),
        })

    return json.dumps({
        "gas_composition_records": records[:50],
        "total_records": len(records),
        "source_file": "gas_composition.csv",
    }, default=str)


ALL_TOOLS = [
    scan_for_anomalies,
    get_event_details,
    check_segment_integrity,
    get_operating_envelope,
    get_regulatory_requirements,
    list_labeled_events,
    get_gas_composition,
]
