"""Capture screenshots from the live dashboard for the presentation."""

from playwright.sync_api import sync_playwright
from pathlib import Path
import time

SHOT_DIR = Path("/workshop/presentation_build/screenshots")
SHOT_DIR.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:3000"

def capture():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = ctx.new_page()

        # 1. Full dashboard
        print("Capturing full dashboard...")
        page.goto(BASE, wait_until="networkidle", timeout=30000)
        time.sleep(2)
        page.screenshot(path=str(SHOT_DIR / "dashboard_full.png"), full_page=False)

        # 2. Pipeline visualization (top section)
        print("Capturing pipeline visualization...")
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)
        pipeline_el = page.query_selector(".pipeline-viz") or page.query_selector("svg") or page.query_selector(".card")
        if pipeline_el:
            pipeline_el.screenshot(path=str(SHOT_DIR / "pipeline_viz.png"))
        else:
            page.screenshot(path=str(SHOT_DIR / "pipeline_viz.png"), clip={"x": 0, "y": 0, "width": 1920, "height": 500})

        # 3. Stats / cost cards
        print("Capturing cost metrics...")
        stats_el = page.query_selector(".stats-grid") or page.query_selector(".stats-row")
        if stats_el:
            stats_el.screenshot(path=str(SHOT_DIR / "cost_stats.png"))
        else:
            page.screenshot(path=str(SHOT_DIR / "cost_stats.png"), clip={"x": 0, "y": 300, "width": 1920, "height": 250})

        # 4. Event timeline section
        print("Capturing event timeline...")
        page.evaluate("window.scrollTo(0, 600)")
        time.sleep(0.5)
        page.screenshot(path=str(SHOT_DIR / "events_timeline.png"), clip={"x": 0, "y": 0, "width": 1920, "height": 1080})

        # 5. Click a leak event to show detail modal/chart
        print("Capturing leak event detail...")
        page.evaluate("window.scrollTo(0, 600)")
        time.sleep(0.5)
        leak_btn = page.query_selector('[data-type="leak"]') or page.query_selector('.event-card.leak') or page.query_selector('.event-item.leak')
        if not leak_btn:
            event_cards = page.query_selector_all('.event-card, .event-item, .timeline-event')
            for card in event_cards:
                text = card.inner_text()
                if "LK-" in text or "leak" in text.lower():
                    leak_btn = card
                    break
        if leak_btn:
            leak_btn.click()
            time.sleep(1.5)
            page.screenshot(path=str(SHOT_DIR / "leak_detail.png"), full_page=False)
            dismiss = page.query_selector('.modal-close, .close-btn, [data-dismiss]')
            if dismiss:
                dismiss.click()
                time.sleep(0.5)
        else:
            print("  (no leak button found, skipping)")

        # 6. Agent chat section
        print("Capturing agent chat...")
        chat_el = page.query_selector('.chat-container, .chat-section, #chat')
        if chat_el:
            page.evaluate("el => el.scrollIntoView()", chat_el)
            time.sleep(0.5)
            chat_el.screenshot(path=str(SHOT_DIR / "agent_chat.png"))
        else:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            page.screenshot(path=str(SHOT_DIR / "agent_chat.png"), full_page=False)

        # 7. Test page
        print("Capturing test page...")
        page.goto(BASE + "/test", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        page.screenshot(path=str(SHOT_DIR / "test_page.png"), full_page=False)

        browser.close()

    shots = list(SHOT_DIR.glob("*.png"))
    print(f"\nCaptured {len(shots)} screenshots:")
    for s in sorted(shots):
        print(f"  {s.name} ({s.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    capture()
