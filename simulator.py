import json
import random
import math
import uuid
from datetime import datetime, timedelta
from typing import Optional
import data_loader as dl

random.seed(42)

STATION_IDS = [f"ST-0{i}" for i in range(1, 9)]
SEGMENTS = list(dl.SEGMENT_STATIONS.keys())


def _baseline_readings(station_id: str, num_points: int = 25, interval_min: int = 5):
    env = dl.OPERATING_ENVELOPES[station_id]
    p_mid = (env["pressure_min"] + env["pressure_max"]) / 2
    f_mid = (env["flow_min"] + env["flow_max"]) / 2
    readings = []
    base_time = datetime(2026, 3, 15, 12, 0, 0)
    for i in range(num_points):
        t = base_time + timedelta(minutes=i * interval_min)
        readings.append({
            "timestamp": t.isoformat(),
            "station_id": station_id,
            "pressure_psi": round(p_mid + random.gauss(0, 2), 2),
            "flow_mmscfd": round(f_mid + random.gauss(0, 0.05), 3),
            "mass_balance_deficit_mmscfd": round(random.gauss(0, 0.02), 4),
            "temperature_f": round(55 + random.gauss(0, 3), 1),
            "compressor_status": "running" if station_id in ("ST-01", "ST-04") else "standby",
            "valve_position_pct": round(72 + random.gauss(0, 2), 1),
            "line_pack_mmscf": round(6.4 + random.gauss(0, 0.05), 3),
        })
    return readings


def _inject_leak(readings: list, onset_idx: int, leak_rate: float, severity: str):
    for i in range(onset_idx, len(readings)):
        elapsed = i - onset_idx
        ramp = min(1.0, elapsed / 4)
        readings[i]["pressure_psi"] -= ramp * (leak_rate * 15 + random.gauss(0, 1))
        readings[i]["mass_balance_deficit_mmscfd"] = round(
            ramp * leak_rate + random.gauss(0, 0.02), 4
        )
        readings[i]["flow_mmscfd"] -= ramp * leak_rate * 0.3
    return readings


def _inject_compressor_start(readings: list, onset_idx: int):
    spike_psi = random.uniform(15, 25)
    spike_flow = random.uniform(0.3, 0.5)
    decay_steps = random.randint(2, 4)
    for i in range(onset_idx, len(readings)):
        elapsed = i - onset_idx
        if elapsed <= decay_steps:
            factor = max(0, 1 - elapsed / decay_steps)
        else:
            factor = 0
        readings[i]["pressure_psi"] += factor * spike_psi + random.gauss(0, 0.3)
        readings[i]["flow_mmscfd"] += factor * spike_flow
        readings[i]["mass_balance_deficit_mmscfd"] = round(factor * random.uniform(0.01, 0.04) + random.gauss(0, 0.015), 4)
        readings[i]["compressor_status"] = "running"
    return readings


def _inject_valve_change(readings: list, onset_idx: int):
    drop_psi = random.uniform(8, 15)
    decay_steps = random.randint(3, 5)
    for i in range(onset_idx, len(readings)):
        elapsed = i - onset_idx
        if elapsed <= decay_steps:
            factor = max(0, 1 - elapsed / decay_steps)
        else:
            factor = 0
        readings[i]["pressure_psi"] -= factor * drop_psi + random.gauss(0, 0.3)
        readings[i]["valve_position_pct"] = round(readings[i]["valve_position_pct"] - 15 * factor, 1)
        readings[i]["mass_balance_deficit_mmscfd"] = round(factor * random.uniform(0.02, 0.06) + random.gauss(0, 0.015), 4)
    return readings


def _inject_temperature_drop(all_station_readings: dict, onset_idx: int):
    temp_drop = random.uniform(10, 20)
    for station_id, readings in all_station_readings.items():
        for i in range(onset_idx, len(readings)):
            elapsed = i - onset_idx
            ramp = min(1.0, elapsed / 6)
            readings[i]["temperature_f"] -= ramp * temp_drop
            pressure_effect = ramp * random.uniform(5, 12)
            readings[i]["pressure_psi"] -= pressure_effect
            readings[i]["mass_balance_deficit_mmscfd"] = round(
                ramp * random.uniform(0.15, 0.25) + random.gauss(0, 0.02), 4
            )
    return all_station_readings


def generate_test_event(event_type: str, difficulty: str = "medium") -> dict:
    event_id = f"TEST-{uuid.uuid4().hex[:6].upper()}"

    noise_scale = {"easy": 0.5, "medium": 1.0, "hard": 1.5}.get(difficulty, 1.0)

    if event_type == "leak_seep":
        segment = random.choice(SEGMENTS)
        from_st, to_st = dl.SEGMENT_STATIONS[segment]
        leak_rate = random.uniform(0.08, 0.19)
        readings_from = _baseline_readings(from_st)
        readings_to = _baseline_readings(to_st)
        onset = random.randint(8, 12)
        _inject_leak(readings_to, onset, leak_rate, "seep")
        mile = dl.OPERATING_ENVELOPES[from_st]["mile"] + random.uniform(5, 20)
        return {
            "event_id": event_id,
            "ground_truth": "leak",
            "severity": "seep",
            "segment": segment,
            "leak_rate_mmscfd": round(leak_rate, 3),
            "mile_marker": round(mile, 1),
            "description": f"Simulated seep leak at {segment} (mile {round(mile,1)}), rate {round(leak_rate,3)} MMSCFD",
            "scada_data": {from_st: readings_from, to_st: readings_to},
            "onset_index": onset,
            "weather": {"ambient_temp_f": round(55 + random.gauss(0, 5), 1), "temp_change_last_6h": round(random.gauss(0, 3), 1)},
        }

    elif event_type == "leak_moderate":
        segment = random.choice(SEGMENTS)
        from_st, to_st = dl.SEGMENT_STATIONS[segment]
        leak_rate = random.uniform(0.2, 0.79)
        readings_from = _baseline_readings(from_st)
        readings_to = _baseline_readings(to_st)
        onset = random.randint(8, 12)
        _inject_leak(readings_to, onset, leak_rate, "moderate")
        mile = dl.OPERATING_ENVELOPES[from_st]["mile"] + random.uniform(5, 20)
        return {
            "event_id": event_id,
            "ground_truth": "leak",
            "severity": "moderate",
            "segment": segment,
            "leak_rate_mmscfd": round(leak_rate, 3),
            "mile_marker": round(mile, 1),
            "description": f"Simulated moderate leak at {segment} (mile {round(mile,1)}), rate {round(leak_rate,3)} MMSCFD",
            "scada_data": {from_st: readings_from, to_st: readings_to},
            "onset_index": onset,
            "weather": {"ambient_temp_f": round(55 + random.gauss(0, 5), 1), "temp_change_last_6h": round(random.gauss(0, 3), 1)},
        }

    elif event_type == "leak_significant":
        segment = random.choice(SEGMENTS)
        from_st, to_st = dl.SEGMENT_STATIONS[segment]
        leak_rate = random.uniform(0.8, 1.99)
        readings_from = _baseline_readings(from_st)
        readings_to = _baseline_readings(to_st)
        onset = random.randint(8, 12)
        _inject_leak(readings_to, onset, leak_rate, "significant")
        mile = dl.OPERATING_ENVELOPES[from_st]["mile"] + random.uniform(5, 20)
        return {
            "event_id": event_id,
            "ground_truth": "leak",
            "severity": "significant",
            "segment": segment,
            "leak_rate_mmscfd": round(leak_rate, 3),
            "mile_marker": round(mile, 1),
            "description": f"Simulated significant leak at {segment} (mile {round(mile,1)}), rate {round(leak_rate,3)} MMSCFD",
            "scada_data": {from_st: readings_from, to_st: readings_to},
            "onset_index": onset,
            "weather": {"ambient_temp_f": round(55 + random.gauss(0, 5), 1), "temp_change_last_6h": round(random.gauss(0, 3), 1)},
        }

    elif event_type == "leak_near_rupture":
        segment = random.choice(SEGMENTS)
        from_st, to_st = dl.SEGMENT_STATIONS[segment]
        leak_rate = random.uniform(2.0, 3.5)
        readings_from = _baseline_readings(from_st)
        readings_to = _baseline_readings(to_st)
        onset = random.randint(8, 12)
        _inject_leak(readings_to, onset, leak_rate, "near_rupture")
        mile = dl.OPERATING_ENVELOPES[from_st]["mile"] + random.uniform(5, 20)
        return {
            "event_id": event_id,
            "ground_truth": "leak",
            "severity": "near_rupture",
            "segment": segment,
            "leak_rate_mmscfd": round(leak_rate, 3),
            "mile_marker": round(mile, 1),
            "description": f"Simulated near-rupture at {segment} (mile {round(mile,1)}), rate {round(leak_rate,3)} MMSCFD",
            "scada_data": {from_st: readings_from, to_st: readings_to},
            "onset_index": onset,
            "weather": {"ambient_temp_f": round(55 + random.gauss(0, 5), 1), "temp_change_last_6h": round(random.gauss(0, 3), 1)},
        }

    elif event_type == "fp_compressor_start":
        station = random.choice(["ST-01", "ST-04"])
        readings = _baseline_readings(station)
        onset = random.randint(8, 12)
        _inject_compressor_start(readings, onset)
        return {
            "event_id": event_id,
            "ground_truth": "false_positive",
            "fp_type": "compressor_start",
            "station": station,
            "description": f"Simulated compressor start transient at {station}",
            "scada_data": {station: readings},
            "onset_index": onset,
            "weather": {"ambient_temp_f": round(55 + random.gauss(0, 5), 1), "temp_change_last_6h": round(random.gauss(0, 3), 1)},
        }

    elif event_type == "fp_valve_change":
        segment = random.choice(SEGMENTS)
        from_st, to_st = dl.SEGMENT_STATIONS[segment]
        readings_from = _baseline_readings(from_st)
        readings_to = _baseline_readings(to_st)
        onset = random.randint(8, 12)
        _inject_valve_change(readings_from, onset)
        _inject_valve_change(readings_to, onset)
        return {
            "event_id": event_id,
            "ground_truth": "false_positive",
            "fp_type": "valve_change",
            "station": from_st,
            "segment": segment,
            "description": f"Simulated valve change at {segment}",
            "scada_data": {from_st: readings_from, to_st: readings_to},
            "onset_index": onset,
            "weather": {"ambient_temp_f": round(55 + random.gauss(0, 5), 1), "temp_change_last_6h": round(random.gauss(0, 3), 1)},
        }

    elif event_type == "fp_temperature":
        all_readings = {}
        for st in STATION_IDS:
            all_readings[st] = _baseline_readings(st)
        onset = random.randint(8, 12)
        _inject_temperature_drop(all_readings, onset)
        return {
            "event_id": event_id,
            "ground_truth": "false_positive",
            "fp_type": "temperature_line_pack",
            "station": "ALL",
            "description": "Simulated temperature-driven line pack contraction across all stations",
            "scada_data": all_readings,
            "onset_index": onset,
            "weather": {"ambient_temp_f": round(30 + random.gauss(0, 3), 1), "temp_change_last_6h": round(-random.uniform(10, 20), 1)},
        }

    else:
        raise ValueError(f"Unknown event type: {event_type}")


def generate_test_suite(num_events: int = 16, difficulty: str = "medium", seed: int = None) -> list:
    if seed is not None:
        random.seed(seed)

    event_types = [
        "leak_seep", "leak_moderate", "leak_significant", "leak_near_rupture",
        "fp_compressor_start", "fp_valve_change", "fp_temperature",
    ]

    leak_types = [t for t in event_types if t.startswith("leak")]
    fp_types = [t for t in event_types if t.startswith("fp")]

    num_leaks = max(2, num_events // 3)
    num_fps = num_events - num_leaks

    events = []
    for _ in range(num_leaks):
        etype = random.choice(leak_types)
        events.append(generate_test_event(etype, difficulty))
    for _ in range(num_fps):
        etype = random.choice(fp_types)
        events.append(generate_test_event(etype, difficulty))

    random.shuffle(events)
    for i, evt in enumerate(events):
        evt["test_index"] = i + 1

    return events


def format_event_for_agent(event: dict) -> str:
    scada_summary = []
    for station_id, readings in event["scada_data"].items():
        pre_onset = readings[:event["onset_index"]]
        post_onset = readings[event["onset_index"]:]

        if pre_onset:
            avg_p_pre = sum(r["pressure_psi"] for r in pre_onset) / len(pre_onset)
            avg_mbd_pre = sum(r["mass_balance_deficit_mmscfd"] for r in pre_onset) / len(pre_onset)
        else:
            avg_p_pre = 0
            avg_mbd_pre = 0

        if post_onset:
            avg_p_post = sum(r["pressure_psi"] for r in post_onset) / len(post_onset)
            max_mbd_post = max(r["mass_balance_deficit_mmscfd"] for r in post_onset)
            avg_mbd_post = sum(r["mass_balance_deficit_mmscfd"] for r in post_onset) / len(post_onset)
            min_p_post = min(r["pressure_psi"] for r in post_onset)
        else:
            avg_p_post = avg_p_pre
            max_mbd_post = 0
            avg_mbd_post = 0
            min_p_post = avg_p_pre

        scada_summary.append(
            f"Station {station_id}:\n"
            f"  Pre-event avg pressure: {avg_p_pre:.1f} PSI, avg mass balance deficit: {avg_mbd_pre:.4f} MMSCFD\n"
            f"  Post-event avg pressure: {avg_p_post:.1f} PSI, min pressure: {min_p_post:.1f} PSI\n"
            f"  Post-event max mass balance deficit: {max_mbd_post:.4f} MMSCFD, avg: {avg_mbd_post:.4f} MMSCFD\n"
            f"  Compressor status: {readings[0]['compressor_status']}\n"
            f"  Sample readings around event onset:"
        )
        start = max(0, event["onset_index"] - 2)
        end = min(len(readings), event["onset_index"] + 8)
        for r in readings[start:end]:
            scada_summary.append(
                f"    {r['timestamp']} | P={r['pressure_psi']:.1f} | Flow={r['flow_mmscfd']:.3f} | "
                f"MBD={r['mass_balance_deficit_mmscfd']:.4f} | T={r['temperature_f']:.1f}F | "
                f"Valve={r['valve_position_pct']:.1f}%"
            )

    weather_info = event.get("weather", {})
    num_stations = len(event["scada_data"])

    recovery_analysis = []
    for station_id, readings in event["scada_data"].items():
        post = readings[event["onset_index"]:]
        if len(post) >= 4:
            early_mbd = [r["mass_balance_deficit_mmscfd"] for r in post[:3]]
            late_mbd = [r["mass_balance_deficit_mmscfd"] for r in post[-3:]]
            avg_early = sum(early_mbd) / len(early_mbd)
            avg_late = sum(late_mbd) / len(late_mbd)
            if abs(avg_late) < abs(avg_early) * 0.5:
                recovery_analysis.append(f"  {station_id}: deficit RECOVERS (early avg={avg_early:.4f}, late avg={avg_late:.4f})")
            else:
                recovery_analysis.append(f"  {station_id}: deficit SUSTAINED / NO RECOVERY (early avg={avg_early:.4f}, late avg={avg_late:.4f})")

    prompt = (
        f"ALERT: Anomaly detected in pipeline SCADA data.\n\n"
        f"Number of stations showing anomaly: {num_stations}\n"
        f"Weather: ambient temp {weather_info.get('ambient_temp_f', 'N/A')}°F, "
        f"temp change last 6h: {weather_info.get('temp_change_last_6h', 'N/A')}°F\n\n"
        f"SCADA Data:\n" + "\n".join(scada_summary) + "\n\n"
        f"Recovery Analysis:\n" + "\n".join(recovery_analysis) + "\n\n"
        f"Based on this data and the operating procedures, classify this event.\n"
        f"Key questions to answer:\n"
        f"1. Is the mass balance deficit SUSTAINED (no recovery) or TRANSIENT (recovers within 5-20 min)?\n"
        f"2. Is the anomaly LOCALIZED to one segment or affecting ALL stations equally?\n"
        f"3. Is there a correlated event (compressor start, valve change, temperature drop)?\n"
        f"4. Even small sustained localized deficits (0.05-0.15 MMSCFD) with no recovery indicate a seep.\n\n"
        f"Classification: REAL LEAK or FALSE POSITIVE?\n"
        f"If leak: severity (seep/moderate/significant/near_rupture)?\n"
        f"What action do you recommend?\n\n"
        f"Respond with a JSON block at the end in this exact format:\n"
        f'{{"classification": "leak" or "false_positive", "severity": "seep/moderate/significant/near_rupture/compressor_start/valve_change/temperature_line_pack", "confidence": 0.0-1.0, "recommended_action": "..."}}'
    )
    return prompt


def parse_agent_response(response: str) -> dict:
    import re
    json_match = re.search(r'\{[^{}]*"classification"[^{}]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    response_lower = response.lower()
    classification = "leak" if "real leak" in response_lower or "confirmed leak" in response_lower or '"classification": "leak"' in response_lower else "false_positive"

    severity = "unknown"
    for s in ["near_rupture", "significant", "moderate", "seep", "compressor_start", "valve_change", "temperature_line_pack"]:
        if s in response_lower:
            severity = s
            break

    return {
        "classification": classification,
        "severity": severity,
        "confidence": 0.5,
        "recommended_action": "See full response",
    }


def score_results(events: list, results: list) -> dict:
    tp = fp = tn = fn = 0
    correct = 0
    total = len(events)

    for evt, res in zip(events, results):
        gt = evt["ground_truth"]
        pred = res.get("agent_classification", res.get("parsed", {}).get("classification", "unknown"))

        if gt == "leak" and pred == "leak":
            tp += 1
            correct += 1
        elif gt == "false_positive" and pred == "false_positive":
            tn += 1
            correct += 1
        elif gt == "false_positive" and pred == "leak":
            fp += 1
        elif gt == "leak" and pred == "false_positive":
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = correct / total if total > 0 else 0

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1, 3),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "true_leaks": tp + fn,
        "true_fps": tn + fp,
    }
