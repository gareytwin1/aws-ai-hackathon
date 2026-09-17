"""Generate a 3-minute video presentation with Polly narration and slide images."""

import boto3
import json
import os
import subprocess
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path("/workshop/presentation_build")
OUT_DIR.mkdir(exist_ok=True)
AUDIO_DIR = OUT_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)
SLIDE_DIR = OUT_DIR / "slides"
SLIDE_DIR.mkdir(exist_ok=True)

W, H = 1920, 1080

COLORS = {
    "bg": (15, 23, 42),
    "surface": (30, 41, 59),
    "accent": (59, 130, 246),
    "danger": (239, 68, 68),
    "warning": (245, 158, 11),
    "success": (34, 197, 94),
    "text": (241, 245, 249),
    "muted": (148, 163, 184),
    "white": (255, 255, 255),
}

SCREENSHOT_DIR = OUT_DIR / "screenshots"

SLIDE_SCREENSHOTS = {
    0: None,
    1: "leak_detail.png",
    2: "dashboard_full.png",
    3: "test_page.png",
    4: "events_timeline.png",
    5: "dashboard_full.png",
}

SLIDES = [
    {
        "title": "$100K per false alarm.\n$2.7M per missed leak.",
        "subtitle": "The Problem",
        "bullets": [
            "200 miles of natural gas pipeline, 8 SCADA stations",
            "207,000 data points over 90 days at 5-minute intervals",
            "When pressure drops — is it a real leak,\na compressor start, or just a cold morning?",
            "Rule-based alarms: too sensitive = $100K shutdowns,\ntoo conservative = missed leaks for days",
            "40% of leaks undetected for over a week",
            "We need contextual reasoning, not static thresholds",
        ],
        "narration": (
            "Our operator manages 200 miles of natural gas pipeline — "
            "8 SCADA stations generating 207 thousand data points over 90 days. "
            "When pressure drops, is it a real leak, a compressor start, or just a cold morning? "
            "Rule-based alarms can't tell the difference. "
            "Too sensitive means 100 thousand dollar false alarm shutdowns. "
            "Too conservative and you miss leaks for days — "
            "risking 2.7 million dollar PHMSA penalties. "
            "We need contextual reasoning, not static thresholds."
        ),
    },
    {
        "title": "7 Tools. 10 Data Sources.\nOne Reasoning Engine.",
        "subtitle": "Our Solution",
        "bullets": [
            "Claude Sonnet 4 on Amazon Bedrock + Strands Agents SDK",
            "SCADA scanner — finds anomalies in 207K readings",
            "Event investigator — pressure, flow, weather, valve context",
            "Integrity checker — inspection history, corrosion, encroachment",
            "Operating envelope — normal ranges + false positive signatures",
            "Regulatory engine — PHMSA 49 CFR 191 compliance",
            "Key insight: real leaks are sustained & localized,\nfalse positives are transient or system-wide",
        ],
        "narration": (
            "We built an agentic AI system on Claude Sonnet 4 with the Strands Agents SDK. "
            "The agent has 7 tools across 10 data sources — "
            "SCADA scanning, event investigation, integrity checks, operating envelopes, and regulatory compliance. "
            "As you can see on the right, the agent investigates each event in depth — "
            "pulling SCADA readings, cost analysis, and mass balance charts. "
            "The key insight: real leaks produce sustained, localized deficits that don't recover. "
            "False positives are transient or system-wide. "
            "That single discriminator is what separates us from threshold-based detection."
        ),
    },
    {
        "title": "Live Dashboard",
        "subtitle": "Interactive Pipeline Monitoring",
        "bullets": [
            "Pipeline visualization — 8 stations, 7 segments, leak markers",
            "Cost impact metrics — repair, shutdown, environmental, PHMSA",
            "$1.5M saved by dismissing 15 false positives correctly",
            "Event timeline — 20 events color-coded by type and severity",
            "Agent chat — natural language queries with grounded answers",
            "Every number traces back to a specific CSV row",
        ],
        "narration": (
            "Here's the dashboard. "
            "The pipeline visualization shows all 8 stations with leak markers. "
            "The stats bar shows 6.5 million in estimated leak impact, "
            "5.2 million in PHMSA exposure, "
            "and 1.5 million saved by correctly dismissing 15 false positives. "
            "The event timeline lists all 20 events color-coded by type. "
            "Click any event for SCADA charts and cost breakdowns. "
            "The agent chat on the right takes natural language queries — "
            "every answer is grounded with citations to specific data rows."
        ),
    },
    {
        "title": "91.7% Accuracy on\nUnseen Events",
        "subtitle": "Proving It Generalizes",
        "bullets": [
            "Synthetic event generator — new scenarios the agent has never seen",
            "Injects realistic SCADA signatures onto baseline readings",
            "Agent classifies each event blind — no ground truth labels",
            "100% recall — caught every leak including 0.09 MMSCFD seep",
            "80% precision — one borderline valve change misclassified",
            "Zero false negatives — never misses a real leak",
        ],
        "narration": (
            "Anyone can build an agent that works on known data. "
            "We built a synthetic event generator that creates scenarios the agent has never seen — "
            "injecting realistic SCADA signatures onto baseline readings. "
            "Results: 91.7 percent accuracy. "
            "100 percent recall — every leak caught, including a faint seep at 0.09 MMSCFD. "
            "Zero false negatives. "
            "In pipeline operations, a missed leak is catastrophic. Our agent never misses one."
        ),
    },
    {
        "title": "Claude + Strands + AgentCore",
        "subtitle": "From Prototype to Production",
        "bullets": [
            "Amazon Bedrock — Claude Sonnet 4 via inference profiles",
            "Strands SDK — @tool decorator auto-generates tool schemas",
            "Agent class manages the full reasoning loop autonomously",
            "AgentCore — Python runtime, CodeZip build, streaming responses",
            "LRU session cache (128 sessions) for conversation state",
            "2,600 lines across 9 files — built in one Claude Code session",
        ],
        "narration": (
            "The stack: Amazon Bedrock for Claude Sonnet 4 access, "
            "Strands SDK where the at-tool decorator auto-generates schemas from Python docstrings, "
            "and Bedrock AgentCore for production deployment with streaming and session caching. "
            "The agent decides which tools to call and in what order — we didn't hardcode the analysis pipeline. "
            "The entire application — 2,600 lines across 9 files — "
            "was built in one Claude Code session."
        ),
    },
    {
        "title": "From Days to Minutes.\nFrom Guessing to\nGrounded Reasoning.",
        "subtitle": "Pipeline Leak Detection & Integrity Agent",
        "bullets": [
            "Traditional: days to detect, 40% miss rate, $100K per false alarm",
            "Our agent: minutes to detect, 100% recall, every claim grounded",
            "PHMSA-ready incident reports generated on demand",
            "The agent explains WHY — cites evidence, recommends action",
            "Not just an alarm system — an intelligent operator assistant",
        ],
        "narration": (
            "Traditional detection: days to find leaks, 40 percent miss rate, "
            "100 thousand per false alarm. "
            "Our agent: minutes to detect, 100 percent recall, every claim grounded in data. "
            "It doesn't just detect — it explains why, cites the evidence, and recommends action. "
            "That's an intelligent operator assistant. Thank you."
        ),
    },
]


def try_load_font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def try_load_regular_font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def add_rounded_screenshot(img, screenshot_path, x, y, w, h, border_color=COLORS["accent"], border_width=3, corner_radius=12):
    """Paste a screenshot onto the slide with a border and rounded corners."""
    screenshot = Image.open(str(screenshot_path))
    screenshot = screenshot.resize((w, h), Image.LANCZOS)

    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=corner_radius, fill=255)

    bordered = Image.new("RGBA", (w + border_width * 2, h + border_width * 2), border_color + (255,))
    border_mask = Image.new("L", bordered.size, 0)
    border_mask_draw = ImageDraw.Draw(border_mask)
    border_mask_draw.rounded_rectangle(
        [(0, 0), (bordered.size[0] - 1, bordered.size[1] - 1)],
        radius=corner_radius + border_width, fill=255
    )
    bg_rgba = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bg_rgba.paste(bordered, (x - border_width, y - border_width), border_mask)
    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, bg_rgba)

    screenshot_rgba = screenshot.convert("RGBA")
    canvas = Image.new("RGBA", img.size, (0, 0, 0, 0))
    canvas.paste(screenshot_rgba, (x, y), mask)
    result = Image.alpha_composite(img_rgba, canvas)

    return result.convert("RGB")


def render_slide(slide_idx, slide_data):
    screenshot_file = SLIDE_SCREENSHOTS.get(slide_idx)
    has_screenshot = screenshot_file and (SCREENSHOT_DIR / screenshot_file).exists()

    text_width = 880 if has_screenshot else W
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (W, 6)], fill=COLORS["accent"])

    font_small = try_load_regular_font(18)
    draw.text((W - 80, H - 40), f"{slide_idx + 1} / {len(SLIDES)}", fill=COLORS["muted"], font=font_small)

    font_subtitle = try_load_regular_font(20)
    draw.text((80, 50), slide_data["subtitle"].upper(), fill=COLORS["accent"], font=font_subtitle)

    font_title = try_load_font(42 if has_screenshot else 48)
    title_lines = slide_data["title"].split("\n")
    y = 85
    for line in title_lines:
        draw.text((80, y), line, fill=COLORS["white"], font=font_title)
        y += 54

    y += 14
    draw.rectangle([(80, y), (340, y + 3)], fill=COLORS["accent"])
    y += 24

    font_bullet = try_load_regular_font(22 if has_screenshot else 26)
    max_text_x = text_width - 40
    for bullet in slide_data["bullets"]:
        bullet_lines = bullet.split("\n")
        for j, bl in enumerate(bullet_lines):
            prefix = "  •  " if j == 0 else "      "
            draw.text((80, y), prefix + bl, fill=COLORS["text"] if j == 0 else COLORS["muted"], font=font_bullet)
            y += 32
        y += 6

    draw.rectangle([(0, H - 54), (W, H)], fill=COLORS["surface"])
    font_brand = try_load_regular_font(15)
    draw.text((80, H - 38), "Pipeline Leak Detection Agent  |  Claude Code + Bedrock AgentCore Hackathon  |  Energy Symposium", fill=COLORS["muted"], font=font_brand)

    if has_screenshot:
        shot_path = SCREENSHOT_DIR / screenshot_file
        shot_x = 940
        shot_y = 60
        shot_w = 920
        shot_h = 940
        draw.rectangle([(shot_x - 8, shot_y - 8), (shot_x + shot_w + 8, shot_y + shot_h + 8)], fill=COLORS["surface"])
        img = add_rounded_screenshot(img, shot_path, shot_x, shot_y, shot_w, shot_h)
        print(f"    + embedded screenshot: {screenshot_file}")

    path = SLIDE_DIR / f"slide_{slide_idx:02d}.png"
    img.save(str(path), "PNG")
    print(f"  Rendered slide {slide_idx + 1}: {path.name}")
    return path


def synthesize_narration(slide_idx, text):
    polly = boto3.client("polly", region_name="us-east-1")
    response = polly.synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId="Matthew",
        Engine="neural",
    )
    path = AUDIO_DIR / f"narration_{slide_idx:02d}.mp3"
    with open(str(path), "wb") as f:
        f.write(response["AudioStream"].read())
    print(f"  Synthesized audio {slide_idx + 1}: {path.name}")
    return path


def get_audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def assemble_video():
    print("\nAssembling video...")

    segments = []
    concat_list = OUT_DIR / "concat.txt"

    for i in range(len(SLIDES)):
        slide_path = SLIDE_DIR / f"slide_{i:02d}.png"
        audio_path = AUDIO_DIR / f"narration_{i:02d}.mp3"
        segment_path = OUT_DIR / f"segment_{i:02d}.mp4"

        duration = get_audio_duration(audio_path)
        duration_with_pause = duration + 1.0

        subprocess.run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(slide_path),
            "-i", str(audio_path),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration_with_pause),
            "-shortest",
            str(segment_path),
        ], capture_output=True, check=True)

        segments.append(segment_path)
        print(f"  Segment {i + 1}: {duration:.1f}s audio + 1.0s pause = {duration_with_pause:.1f}s")

    with open(str(concat_list), "w") as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")

    output_path = Path("/workshop/presentation.mp4")
    result = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  concat copy failed, falling back to re-encode...")
        print(f"  stderr: {result.stderr[-500:]}")
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path),
        ], check=True)

    total_duration = sum(get_audio_duration(OUT_DIR / f"segment_{i:02d}.mp4") for i in range(len(SLIDES)))
    print(f"\nVideo created: {output_path}")
    print(f"Total duration: {total_duration:.0f} seconds ({total_duration/60:.1f} minutes)")
    print(f"File size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
    assert output_path.exists(), "FAILED: output video not found!"
    return output_path


def main():
    print("=" * 50)
    print("Pipeline Leak Detection — Video Presentation")
    print("=" * 50)

    print("\n1. Rendering slides...")
    for i, slide in enumerate(SLIDES):
        render_slide(i, slide)

    print("\n2. Synthesizing narration with Amazon Polly...")
    for i, slide in enumerate(SLIDES):
        synthesize_narration(i, slide["narration"])

    print("\n3. Assembling video with ffmpeg...")
    output = assemble_video()

    print("\n" + "=" * 50)
    print(f"DONE! Video at: {output}")
    print(f"File size: {output.stat().st_size / 1024 / 1024:.1f} MB")
    print("=" * 50)


if __name__ == "__main__":
    main()
