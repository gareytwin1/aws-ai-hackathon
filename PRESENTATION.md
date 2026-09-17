# Pipeline Leak Detection & Integrity Agent
### 3-Minute Presentation Script

---

## SLIDE 1 — The Problem (30 seconds)

**Title:** _"$100K per false alarm. $2.7M per missed leak. Pick your poison."_

**Talking Points:**

- We manage 200 miles of natural gas pipeline with 8 SCADA stations generating a reading every 5 minutes — that's 207,000 data points over 90 days.
- The core challenge: when pressure drops and flow shifts, is it a real leak — or just a compressor starting up, a valve adjustment, or a cold morning contracting the line pack?
- Rule-based SCADA alarms can't tell the difference. Set them sensitive: constant false alarms, $100K+ unnecessary shutdowns, operator fatigue. Set them conservative: you miss real leaks. 40% of pipeline leaks go undetected for over a week — escalating repair costs 6x and risking $2.7M PHMSA penalties per violation.
- **We need contextual reasoning, not static thresholds.**

---

## SLIDE 2 — Our Solution: An AI Agent That Thinks Like an Engineer (45 seconds)

**Title:** _"7 tools. 10 data sources. One reasoning engine."_

**Talking Points:**

- We built an **agentic AI system** powered by **Claude Sonnet 4 on Amazon Bedrock**, using the **Strands Agents SDK** for tool orchestration and configured for **Bedrock AgentCore** deployment.
- The agent has **7 specialized tools** that give it structured access to the full dataset:
  - **SCADA scanner** — finds anomalies in 207K readings
  - **Event investigator** — pulls pressure, flow, weather, valve, and compressor data around any event
  - **Integrity checker** — cross-references inspection history, cathodic protection, and third-party encroachment records
  - **Operating envelope** — knows the normal ranges for every station and the exact signatures of false positives
  - **Regulatory engine** — knows DOT PHMSA 49 CFR 191 reporting requirements and when to trigger NRC notifications
- The key insight we encoded: **real leaks produce sustained, localized mass balance deficits that don't recover**. False positives are either transient (compressor starts settle in 5-15 min) or system-wide (temperature drops affect all stations equally). This single discriminator is what separates our agent from threshold-based detection.

---

## SLIDE 3 — Live Demo: The Dashboard (45 seconds)

**Title:** _"Show, don't tell."_

> **[OPEN THE DASHBOARD]** — `https://dkxcmungl6jld.cloudfront.net/code/ports/3000/`

**Walk through (pick 2-3 of these):**

1. **Pipeline overview** — "Here's our 200-mile pipeline with 8 stations. The red markers show where the 5 confirmed leaks occurred. The stats bar shows the financial impact — estimated leak costs, PHMSA penalty exposure, and $1.5M in avoided unnecessary shutdowns from correctly dismissing 15 false positives."

2. **Click a leak event (LK-005)** — "This is a near-rupture event: 2.4 MMSCFD leak rate at mile 13.6 on segment SEG-01. The chart shows the mass balance deficit spiking across stations. Estimated impact: $4.2M in repair, shutdown, and environmental costs. PHMSA penalty exposure: $2.7M."

3. **Agent chat** — Click "Analyze All Events" or type a question. "The agent calls its tools autonomously — it pulls the SCADA data, cross-references weather and valve status, checks the operating envelope, and delivers a grounded classification with citations. Every number traces back to a specific CSV row."

4. **Click a false positive (FP-001)** — "This compressor start at ST-01 looks like a leak: 13.8 PSI pressure drop. But the agent sees the transient signature — pressure recovers in 19 minutes, mass balance stays normal. Correctly dismissed."

---

## SLIDE 4 — Proving It Generalizes: The Test Suite (30 seconds)

**Title:** _"91.7% accuracy on events it's never seen."_

> **[OPEN THE TEST PAGE]** — Click "Test Suite" link on dashboard

**Talking Points:**

- Anyone can build an agent that works on known data. We built a **synthetic event generator** that creates new leak and false-positive scenarios the agent has never seen.
- It injects realistic SCADA signatures — pressure drops, mass balance deficits, compressor transients, temperature shifts — onto baseline readings, then asks the agent to classify them blind.


## SLIDE 5 — How It's Built: Bedrock AgentCore Stack (30 seconds)

**Title:** _"Claude + Strands + AgentCore — from prototype to production."_

**Talking Points:**

- **Amazon Bedrock** — provides on-demand access to Claude Sonnet 4 via inference profiles. The Converse API handles structured tool use natively.
- **Strands Agents SDK** — the `@tool` decorator turns Python functions into Claude-compatible tools automatically. The `Agent` class manages the full reasoning loop: receive query → select tools → call tools → synthesize response. We didn't hardcode the analysis pipeline — the agent adapts its investigation to what it finds.
- **Bedrock AgentCore** — our deployment config (`agentcore.json`) defines a Python runtime with CodeZip build. The entrypoint streams responses via an async generator pattern. An LRU session cache (128 sessions) maintains conversation state. This takes us from a local prototype to a managed, scalable production service.
- **The entire application — 2,600 lines across 9 files — was built in a single session using Claude Code.** Three sub-agents explored the dataset in parallel. Iterative test runs caught regressions. Even a CloudFront proxy bug was diagnosed and fixed in-session.

---

## SLIDE 6 — Closing: Why This Matters (15 seconds)

**Title:** _"From days to minutes. From guessing to grounded reasoning."_

**Talking Points:**

- Traditional leak detection: days to detect, 40% miss rate, $100K per false alarm.
- Our agent: **minutes to detect, 100% recall, every claim grounded in data, PHMSA-ready reports on demand.**
- The agent doesn't just detect — it explains _why_ it classified an event, cites the evidence, and recommends the exact operational response. That's the difference between an alarm system and an intelligent operator assistant.

