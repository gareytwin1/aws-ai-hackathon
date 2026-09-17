import json
import traceback
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import data_loader as dl
from simulator import generate_test_suite, format_event_for_agent, parse_agent_response, score_results

app = FastAPI(title="Pipeline Leak Detection Agent")
templates = Jinja2Templates(directory="templates")

test_state = {"running": False, "events": [], "results": [], "scores": None, "progress": 0, "total": 0}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/pipeline")
async def get_pipeline():
    meta = dl.pipeline_metadata()
    segments = []
    for _, row in meta.iterrows():
        segments.append({
            "segment_id": row["segment_id"],
            "from_station": row["from_station"],
            "to_station": row["to_station"],
            "length_miles": float(row["length_miles"]),
            "maop_psi": float(row["maop_psi"]),
        })
    return {"segments": segments, "stations": dl.OPERATING_ENVELOPES}


@app.get("/api/events")
async def get_events():
    leaks = dl.leak_events()
    fps = dl.false_positive_events()

    events = []
    for _, row in leaks.iterrows():
        events.append({
            "event_id": row["event_id"],
            "timestamp": str(row["onset_timestamp"]),
            "type": "leak",
            "severity": row["severity"],
            "segment": row["affected_segment"],
            "station": "",
            "leak_rate": float(row["leak_rate_mmscfd"]),
            "mile_marker": float(row["true_leak_location_mile_marker"]),
            "detection_lag_minutes": int(row["detection_lag_minutes"]),
            "detail": f"Leak rate: {row['leak_rate_mmscfd']} MMSCFD at mile {row['true_leak_location_mile_marker']}",
        })

    for _, row in fps.iterrows():
        events.append({
            "event_id": row["event_id"],
            "timestamp": str(row["timestamp"]),
            "type": "false_positive",
            "severity": row["fp_type"],
            "segment": "",
            "station": row["station_id"],
            "leak_rate": 0,
            "mile_marker": 0,
            "pressure_drop_psi": float(row["pressure_drop_psi"]),
            "duration_minutes": int(row["duration_minutes"]),
            "detail": row["explanation"],
        })

    events.sort(key=lambda e: e["timestamp"])
    return {"events": events}


@app.get("/api/scada_snapshot")
async def scada_snapshot(timestamp: str, window_minutes: int = 60):
    import pandas as pd
    center = pd.to_datetime(timestamp)
    delta = pd.Timedelta(minutes=window_minutes)
    df = dl.scada()
    mask = (df["timestamp"] >= center - delta) & (df["timestamp"] <= center + delta)
    window = df[mask]

    stations = {}
    for station_id in window["station_id"].unique():
        st_data = window[window["station_id"] == station_id].sort_values("timestamp")
        stations[station_id] = {
            "timestamps": [str(t) for t in st_data["timestamp"]],
            "pressure_psi": [round(v, 2) for v in st_data["pressure_psi"]],
            "flow_mmscfd": [round(v, 3) for v in st_data["flow_mmscfd"]],
            "mass_balance_deficit": [round(v, 4) for v in st_data["mass_balance_deficit_mmscfd"]],
            "temperature_f": [round(v, 1) for v in st_data["temperature_f"]],
        }

    return {"center": str(center), "stations": stations}


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    query = body.get("message", "")
    if not query:
        return JSONResponse({"error": "No message provided"}, status_code=400)

    try:
        from agent import run_query
        response = run_query(query)
        return {"response": response}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/segment/{segment_id}")
async def segment_detail(segment_id: str):
    meta = dl.pipeline_metadata()
    seg = meta[meta["segment_id"] == segment_id]
    if seg.empty:
        return JSONResponse({"error": "Segment not found"}, status_code=404)

    row = seg.iloc[0]
    insp = dl.inspection_history()
    seg_insp = insp[insp["segment_id"] == segment_id]

    cp = dl.cathodic_protection()
    seg_cp = cp[cp["segment_id"] == segment_id]

    enc = dl.row_encroachment()
    seg_enc = enc[enc["segment_id"] == segment_id]

    return {
        "metadata": {
            "segment_id": segment_id,
            "from_station": row["from_station"],
            "to_station": row["to_station"],
            "length_miles": float(row["length_miles"]),
            "diameter_in": float(row["diameter_in"]),
            "wall_thickness_in": float(row["wall_thickness_in"]),
            "material_grade": row["material_grade"],
            "maop_psi": float(row["maop_psi"]),
        },
        "inspections": len(seg_insp),
        "inspection_issues": int((seg_insp.get("result", pd.Series()) != "Pass").sum()) if not seg_insp.empty else 0,
        "cp_readings": len(seg_cp),
        "cp_pass_rate": round(100 * (seg_cp["criteria_met"] == "Pass").mean(), 1) if not seg_cp.empty else 0,
        "encroachments": len(seg_enc),
        "high_risk_encroachments": int((seg_enc.get("risk_level", pd.Series()) == "High").sum()) if not seg_enc.empty else 0,
    }


@app.get("/presentation")
async def presentation_video():
    return FileResponse("/workshop/presentation.mp4", media_type="video/mp4", filename="presentation.mp4")


@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    return templates.TemplateResponse(request=request, name="test.html")


@app.post("/api/test/generate")
async def generate_tests(request: Request):
    body = await request.json()
    num_events = body.get("num_events", 12)
    difficulty = body.get("difficulty", "medium")
    seed = body.get("seed", None)

    events = generate_test_suite(num_events, difficulty, seed)
    events_summary = []
    for evt in events:
        events_summary.append({
            "event_id": evt["event_id"],
            "test_index": evt["test_index"],
            "ground_truth": evt["ground_truth"],
            "severity": evt.get("severity", evt.get("fp_type", "")),
            "description": evt["description"],
            "num_stations": len(evt["scada_data"]),
            "weather": evt.get("weather", {}),
        })

    test_state["events"] = events
    test_state["results"] = []
    test_state["scores"] = None
    test_state["progress"] = 0
    test_state["total"] = len(events)
    test_state["running"] = False

    return {"events": events_summary, "total": len(events)}


@app.post("/api/test/run")
async def run_tests(request: Request):
    if test_state["running"]:
        return JSONResponse({"error": "Test already running"}, status_code=409)
    if not test_state["events"]:
        return JSONResponse({"error": "No test events generated. Call /api/test/generate first."}, status_code=400)

    test_state["running"] = True
    test_state["results"] = []
    test_state["progress"] = 0

    asyncio.create_task(_run_test_suite())
    return {"status": "started", "total": len(test_state["events"])}


async def _run_test_suite():
    from agent import run_query
    events = test_state["events"]

    for i, evt in enumerate(events):
        try:
            prompt = format_event_for_agent(evt)
            response = await asyncio.to_thread(run_query, prompt)
            parsed = parse_agent_response(response)

            test_state["results"].append({
                "event_id": evt["event_id"],
                "test_index": evt["test_index"],
                "ground_truth": evt["ground_truth"],
                "ground_truth_severity": evt.get("severity", evt.get("fp_type", "")),
                "description": evt["description"],
                "agent_classification": parsed.get("classification", "unknown"),
                "agent_severity": parsed.get("severity", "unknown"),
                "agent_confidence": parsed.get("confidence", 0),
                "agent_action": parsed.get("recommended_action", ""),
                "correct": (evt["ground_truth"] == parsed.get("classification", "")),
                "full_response": response,
            })
        except Exception as e:
            test_state["results"].append({
                "event_id": evt["event_id"],
                "test_index": evt["test_index"],
                "ground_truth": evt["ground_truth"],
                "ground_truth_severity": evt.get("severity", evt.get("fp_type", "")),
                "description": evt["description"],
                "agent_classification": "error",
                "agent_severity": "error",
                "agent_confidence": 0,
                "agent_action": "",
                "correct": False,
                "full_response": f"Error: {str(e)}",
            })

        test_state["progress"] = i + 1

    test_state["scores"] = score_results(events, test_state["results"])
    test_state["running"] = False


@app.get("/api/test/status")
async def test_status():
    return {
        "running": test_state["running"],
        "progress": test_state["progress"],
        "total": test_state["total"],
        "results": test_state["results"],
        "scores": test_state["scores"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
