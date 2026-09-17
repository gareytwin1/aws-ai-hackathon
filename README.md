# Pipeline Leak Detection & Integrity Agent

## High-Level Overview

This application is an AI-powered pipeline leak detection system built for a 200-mile natural gas transmission pipeline with 8 SCADA measurement stations. It uses **Claude on Amazon Bedrock** as its reasoning engine and the **Strands Agents SDK** for tool-use orchestration, with deployment configured for **Amazon Bedrock AgentCore**.

The core problem: distinguishing real pipeline leaks from false positives (compressor starts, valve changes, temperature-driven line pack shifts) that look identical on a SCADA dashboard. Rule-based alarms either flood operators with false alarms ($100K+ per unnecessary shutdown) or miss real leaks that escalate into environmental disasters and $2.7M PHMSA penalties.

Our agent solves this through **contextual reasoning** — it doesn't just look at pressure and flow, it cross-references weather, valve status, compressor activity, inspection history, cathodic protection, and right-of-way encroachment data to make grounded, evidence-backed classifications.

---

## What We Built

### Intelligent Agent with 7 Specialized Tools

The agent is built with the **Strands Agents SDK** and powered by **Claude Sonnet 4 on Amazon Bedrock**. It has 7 tools that give it structured access to the full dataset:

| Tool | What It Queries |
|------|----------------|
| `scan_for_anomalies` | Scans 207K SCADA readings for pressure/flow anomalies and mass balance deficits |
| `get_event_details` | Pulls detailed time-series data around a specific event, plus weather, valve, and cross-station context |
| `check_segment_integrity` | Looks up ILI inspection history, cathodic protection readings, and encroachment records for a segment |
| `get_operating_envelope` | Returns normal pressure/flow ranges, false-positive signatures, leak thresholds, and the escalation ladder |
| `get_regulatory_requirements` | Returns DOT PHMSA 49 CFR 191 reporting requirements, NRC timelines, and Form 7100.1 fields |
| `list_labeled_events` | Returns the 5 confirmed leaks and 15 confirmed false positives for analysis |
| `get_gas_composition` | Returns methane%, compressibility factor, and heating values for accurate mass balance calculations |

The agent's system prompt encodes the operating procedures' decision logic: what makes a real leak (sustained, localized mass balance deficit with no recovery) vs. each type of false positive (transient and/or system-wide).

### Interactive Web Dashboard

A dark-themed, real-time dashboard built with **FastAPI** and vanilla JavaScript:

- **Pipeline visualization** — SVG schematic of all 8 stations and 7 segments with leak markers sized by severity
- **Cost impact metrics** — estimated repair cost, shutdown cost, environmental cost, PHMSA penalty exposure, and avoided costs from dismissing false positives
- **Event timeline** — all 20 labeled events (5 leaks + 15 false positives) color-coded by type and severity, with per-event cost estimates
- **Event detail modals** — Chart.js visualization of mass balance deficit across all stations around each event, plus cost breakdown
- **Agent chat interface** — natural language queries with markdown-rendered responses. Quick-action buttons for common analyses: "Analyze All Events", "Leak vs FP Patterns", "Segment Risk Assessment", "Generate PHMSA Report"

### Cost Impact Model

Every leak event includes a financial impact estimate based on severity:

| Severity | Repair | Shutdown | Environmental | PHMSA Penalty Risk |
|----------|--------|----------|---------------|-------------------|
| Seep | $75K | $0 | $15K | $0 |
| Moderate | $250K | $100K | $75K | $500K |
| Significant | $750K | $250K | $350K | $1.5M |
| Near-rupture | $2.5M | $500K | $1.2M | $2.7M |

The model also calculates avoided costs from correctly dismissing false positives ($100K per avoided unnecessary shutdown × 15 false positives = $1.5M saved).

---

## How Amazon Bedrock AgentCore Is Used

### Model Access via Bedrock

The agent uses **Claude Sonnet 4** (`us.anthropic.claude-sonnet-4-20250514-v1:0`) through the Bedrock inference profile API. This provides:
- On-demand access to Claude without managing infrastructure
- Cross-region inference profiles for high availability
- The Converse API for structured tool use

### Strands Agents SDK Integration

The **Strands Agents SDK** (`strands-agents`) provides the agent framework:
- `Agent` class manages the conversation loop and tool-use orchestration
- `BedrockModel` wraps the Bedrock API with automatic retries and streaming
- `@tool` decorator converts Python functions into Claude-compatible tool definitions — the SDK reads docstrings and type hints to generate schemas automatically
- The agent autonomously decides which tools to call and in what order based on the user's query

### AgentCore Deployment Configuration

The application is configured for AgentCore deployment:
- **`agentcore/agentcore.json`** — defines a `pipeline_agent` runtime with Python 3.14, CodeZip build, HTTP protocol, and public network access
- **`app/pipeline_agent/main.py`** — the AgentCore entrypoint using `BedrockAgentCoreApp`. It wraps the agent behind a `@app.entrypoint` async generator that streams responses. An LRU cache (128 sessions) maintains conversation state across requests
- **`app/pipeline_agent/pyproject.toml`** — declares dependencies (`bedrock-agentcore`, `strands-agents`, `pandas`)

The entrypoint pattern:
```python
@app.entrypoint
async def invoke(payload, context):
    session_id = getattr(context, "session_id", "default-session")
    agent = get_or_create_agent(session_id)
    async for event in agent.stream_async(prompt):
        yield event
```

This allows the agent to be deployed to AgentCore's managed runtime, handling scaling, session management, and health checks automatically.

---

## 5 Key Tools & Tips for Building This Application

### The `@tool` Decorator Pattern — Let the LLM Choose Its Own Path

Rather than hardcoding an analysis pipeline, we defined 7 independent tools and let Claude decide which to call and in what order. When asked "Analyze event LK-003", the agent autonomously calls `list_labeled_events` → `get_event_details` → `get_operating_envelope` → `check_segment_integrity` → `get_regulatory_requirements` in sequence, building up context as it goes. This agentic pattern produces much richer analysis than a fixed pipeline because the agent adapts its investigation to what it finds.

### Synthetic Test Data as a Proof of Generalization

The test suite generates events the agent has never seen by injecting realistic SCADA signatures onto baseline readings. Each event type has a distinct pattern: leaks produce sustained, non-recovering mass balance deficits localized to one segment; compressor starts produce transient pressure spikes that settle in 5-15 minutes; temperature drops affect all stations equally. The agent must recognize these patterns from its operating procedures knowledge, not from memorizing the labeled data.

### Grounded Reasoning with Source Citations

Every tool response includes a `source_file` field that traces back to the specific CSV file. The agent's system prompt requires it to cite specific timestamps, station IDs, and numeric values for every claim. This means every number in the agent's output can be verified against the raw data — a key differentiator from generic LLM responses.

### The Recovery Analysis Pattern for Leak vs. False Positive Disambiguation

The #1 differentiator we discovered in the data: **real leaks produce mass balance deficits that don't recover**, while false positives (compressor starts, valve changes) produce transient spikes that return to baseline within 5-20 minutes. Temperature-driven line pack affects all stations equally, while leaks are localized to one segment. We encoded this as a "recovery analysis" in both the agent's system prompt and the test event formatter, which dramatically improved classification accuracy — especially for faint seep detection.

### Claude Code as the Full Development Environment

The entire application — agent, tools, data loader, web dashboard, test suite, and AgentCore deployment config — was built entirely within Claude Code. Key techniques:
- **Parallel agent exploration**: we spawned 3 sub-agents simultaneously to explore the SCADA data, context files, and reference documents, cutting exploration time from ~10 minutes to ~2 minutes
- **Iterative testing**: after each change, we ran the test suite to verify accuracy didn't regress
- **Proxy-aware URLs**: when the dashboard was accessed through a CloudFront reverse proxy, we diagnosed the JSON parse error (absolute `/api/` paths resolving to the wrong host) and fixed all fetch calls to use relative paths — a real-world deployment gotcha caught and fixed in-session

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Web Dashboard                        │
│  Pipeline Viz │ Cost Metrics │ Event Timeline │ Chat     │
└──────────────────────────┬──────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────┐
│                    FastAPI Server                         │
│  /api/chat → Agent  │ /api/test/* → Simulator            │
│  /api/events        │ /api/pipeline │ /api/scada_snapshot│
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│         Strands Agent (Claude Sonnet 4 on Bedrock)      │
│                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │scan_anomalies│ │event_details │ │segment_integrity │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │op_envelope   │ │regulatory    │ │gas_composition   │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
│  ┌──────────────┐                                       │
│  │labeled_events│                                       │
│  └──────────────┘                                       │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                    Data Layer (Pandas)                  │
│  9 CSV files │ 2 reference docs │ 210K+ rows            │
│  valve_status segment_id normalized (01 → SEG-01)       │
└─────────────────────────────────────────────────────────┘
```

---

## File Inventory

| File | Purpose | Lines |
|------|---------|-------|
| `agent.py` | Agent definition + system prompt | 67 |
| `tools.py` | 7 Strands tools | 418 |
| `data_loader.py` | Data loading, caching, normalization | 104 |
| `server.py` | FastAPI server + test runner | 260 |
| `simulator.py` | Synthetic event generator + scorer | 417 |
| `templates/index.html` | Main dashboard | 771 |
| `templates/test.html` | Test suite UI | 466 |
| `app/pipeline_agent/main.py` | AgentCore entrypoint | 87 |
| `agentcore/agentcore.json` | AgentCore deployment config | 34 |
| **Total** | | **~2,624** |
