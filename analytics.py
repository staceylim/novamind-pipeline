"""
analytics.py — NovaMind Performance Analytics
Simulates newsletter performance metrics, generates AI-powered insights,
recommends next content topics, and persists analytics history.
"""

import os
import re
import json
import random
from datetime import datetime, timezone

import google.generativeai as genai
from dotenv import load_dotenv

# ── Environment ──────────────────────────────────────────────────────────────

load_dotenv()

# Configure Google Gemini (same model as pipeline.py)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini = genai.GenerativeModel("gemini-2.5-flash")

# ── Persona performance baselines ────────────────────────────────────────────
#
# Each persona has a fixed baseline that reflects real-world email marketing
# behaviour for that audience type. Small noise is added per run so the
# numbers vary realistically without ever inverting the persona hierarchy.
#
# Marketing Manager — highest engagement
#   They actively seek marketing tools and content; newsletters land directly
#   in their professional interest zone. High intent, high click-through.
#
# Agency Founder — moderate engagement
#   Interested in growth and ROI but time-poor. Selective openers who click
#   only when the subject line speaks to business outcomes.
#
# Operations Manager — lowest engagement
#   More task-focused than content-focused. Less emotionally invested in
#   marketing newsletters; opens are pragmatic rather than curious.

PERSONA_BASELINES = {
    "Marketing Manager": {
        "open_rate":        0.55,   # 50–60% range
        "click_rate":       0.275,  # 25–30% range
        "unsubscribe_rate": 0.005,  # 0.3–0.8% range
    },
    "Agency Founder": {
        "open_rate":        0.40,   # 35–45% range
        "click_rate":       0.175,  # 15–20% range
        "unsubscribe_rate": 0.015,  # 1–2% range
    },
    "Operations Manager": {
        "open_rate":        0.30,   # 25–35% range
        "click_rate":       0.125,  # 10–15% range
        "unsubscribe_rate": 0.025,  # 2–3% range
    },
}

# Maximum noise added in either direction (±) for each metric
NOISE = {
    "open_rate":        0.05,    # ±5 percentage points
    "click_rate":       0.05,    # ±5 percentage points
    "unsubscribe_rate": 0.005,   # ±0.5 percentage points
}

# Hard bounds — values are clipped to these after noise is applied
BOUNDS = {
    "open_rate":        (0.20, 0.70),
    "click_rate":       (0.05, 0.40),
    "unsubscribe_rate": (0.001, 0.05),
}

# ── Helper ────────────────────────────────────────────────────────────────────

def _strip_json(text: str) -> str:
    """
    Strip markdown code fences from Gemini responses before JSON parsing.
    Handles ```json ... ``` and ``` ... ``` wrappers.
    """
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


# ── Performance simulation ────────────────────────────────────────────────────

def simulate_performance() -> dict:
    """
    Simulate realistic newsletter performance metrics for each persona.

    Strategy:
      1. Draw a single campaign_factor (0.8–1.2) shared across all personas.
         This shifts every metric up or down together, simulating a strong or
         weak campaign — so some runs produce universally high numbers and
         others universally low ones.
      2. Add per-metric noise (±5pp for rates) on top of the shifted baseline
         to give each persona its own variation within the run.
      3. Clip to hard bounds so nothing goes outside plausible ranges.

    The persona hierarchy (Marketing Manager > Agency Founder > Ops Manager)
    is maintained by the baseline gaps being wider than the noise range.

    Returns a dict keyed by persona name, each value containing:
        open_rate        — fraction (e.g. 0.55 = 55%)
        click_rate       — fraction
        unsubscribe_rate — fraction
    """
    # One campaign-level factor shifts all personas together this run
    campaign_factor = random.uniform(0.8, 1.2)

    performance = {}

    for persona, baseline in PERSONA_BASELINES.items():
        metrics = {}
        for metric, base_value in baseline.items():
            # Apply campaign factor, then add per-metric noise
            shifted   = base_value * campaign_factor
            noise     = random.uniform(-NOISE[metric], NOISE[metric])
            raw_value = shifted + noise
            # Clip to hard bounds
            lo, hi    = BOUNDS[metric]
            metrics[metric] = round(max(lo, min(hi, raw_value)), 4)
        performance[persona] = metrics

    print(f"[analytics] Performance simulated (campaign_factor={campaign_factor:.2f}) "
          f"for {list(performance.keys())}")
    return performance


# ── AI insights ───────────────────────────────────────────────────────────────

def generate_ai_insights(performance_data: dict) -> str:
    """
    Use Gemini to analyse the simulated performance metrics and produce
    a concise 2-3 sentence insight summary.

    The summary names the best-performing persona and gives one concrete
    recommendation for improving future campaigns.

    Returns a plain-text string.
    """
    # Format metrics as readable text for the prompt
    metrics_text = "\n".join(
        f"- {persona}: open rate {data['open_rate']*100:.1f}%, "
        f"click rate {data['click_rate']*100:.1f}%, "
        f"unsubscribe rate {data['unsubscribe_rate']*100:.2f}%"
        for persona, data in performance_data.items()
    )

    prompt = f"""
You are a marketing analyst for NovaMind, an AI startup serving creative agencies.

Here are the latest newsletter performance metrics by audience persona:
{metrics_text}

In 2-3 concise sentences:
1. Identify which persona performed best overall and why.
2. Give one concrete, actionable recommendation to improve the next campaign.

Write in a professional but friendly tone. Return plain text only — no markdown, no bullet points.
""".strip()

    try:
        response = gemini.generate_content(prompt)
        insights = response.text.strip()
        print("[analytics] AI insights generated")
        return insights
    except Exception as e:
        print(f"[analytics] ERROR generating insights: {e}")
        # Determine best persona by open rate as fallback
        best = max(performance_data, key=lambda p: performance_data[p]["open_rate"])
        return (
            f"The {best} segment showed the strongest engagement this period. "
            "Consider A/B testing subject lines to further improve open rates across all segments."
        )


# ── Topic recommendations ─────────────────────────────────────────────────────

def recommend_next_topics(performance_data: dict, campaign_history: list) -> list:
    """
    Use Gemini to recommend 3 future blog topics based on:
    - Current performance trends (which personas are most engaged)
    - Past campaign topics (to avoid repetition)

    Returns a list of 3 topic strings.
    """
    # Target topics at the lowest-performing persona to improve their engagement
    worst_persona = min(performance_data, key=lambda p: performance_data[p]["open_rate"])
    worst_open    = performance_data[worst_persona]["open_rate"] * 100

    # Extract past blog titles for context
    past_titles = [c.get("blog_title", "") for c in campaign_history if c.get("blog_title")]
    past_titles_text = (
        "\n".join(f"- {t}" for t in past_titles[-10:])
        if past_titles
        else "No previous campaigns yet."
    )

    prompt = f"""
You are a B2B content strategist for NovaMind, an AI startup that helps small creative agencies automate workflows.

The lowest-performing audience segment is: {worst_persona} ({worst_open:.1f}% open rate).
Your goal is to recommend topics that will improve engagement for this segment.

Recent blog topics already covered (do not repeat these):
{past_titles_text}

Recommend exactly 3 new blog post topics following these strict rules:
- Maximum 8 words per title
- No colons, no subtitles, no em dashes
- Professional B2B tone — no clickbait, no listicle-style phrasing
- Directly relevant to the pain points of: {worst_persona}
- Applicable to creative agency professionals

Good examples of the required style:
- "AI Workflow Automation for Creative Agency Teams"
- "Measuring Campaign ROI with AI Analytics"
- "Reducing Creative Overhead with Automation Tools"

Return ONLY valid JSON (no markdown, no code fences) as a JSON array of 3 strings:
["Topic 1", "Topic 2", "Topic 3"]
""".strip()

    try:
        response = gemini.generate_content(prompt)
        topics = json.loads(_strip_json(response.text))
        # Ensure we always return exactly 3 strings
        if isinstance(topics, list) and len(topics) >= 3:
            topics = [str(t) for t in topics[:3]]
        else:
            raise ValueError("Unexpected topic format from Gemini")
        print(f"[analytics] Recommended topics: {topics}")
        return topics
    except Exception as e:
        print(f"[analytics] ERROR recommending topics: {e}")
        return [
            "AI Workflow Automation for Creative Agency Teams",
            "Measuring Campaign ROI with AI Analytics",
            "Reducing Creative Overhead with Automation Tools",
        ]


# ── Persistence ───────────────────────────────────────────────────────────────

def save_analytics(data: dict) -> None:
    """
    Append an analytics result (with a UTC timestamp) to analytics_history.json.
    Creates the file if it does not exist.
    """
    history_path = "analytics_history.json"
    entry = {**data, "timestamp": datetime.now(timezone.utc).isoformat()}

    try:
        if os.path.exists(history_path):
            with open(history_path, "r") as f:
                history = json.load(f)
        else:
            history = []

        history.append(entry)

        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)

        print("[analytics] Analytics saved to analytics_history.json")
    except Exception as e:
        print(f"[analytics] ERROR saving analytics: {e}")


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_analytics() -> dict:
    """
    Orchestrate the full analytics workflow:
      1. Load campaign history for context
      2. Simulate per-persona performance metrics
      3. Generate AI insights summary
      4. Recommend 3 next blog topics
      5. Save results to analytics_history.json

    Returns the full analytics dict.
    """
    print("\n[analytics] Starting analytics run...")

    # Step 1 — Load campaign history (used for topic recommendations)
    campaign_history = []
    if os.path.exists("campaign_history.json"):
        try:
            with open("campaign_history.json", "r") as f:
                campaign_history = json.load(f)
        except Exception as e:
            print(f"[analytics] Could not load campaign_history.json: {e}")

    # Step 2 — Simulate performance
    performance = simulate_performance()

    # Step 3 — AI insights
    insights = generate_ai_insights(performance)

    # Step 4 — Topic recommendations
    topics = recommend_next_topics(performance, campaign_history)

    # Step 5 — Persist and return
    result = {
        "performance": performance,
        "insights": insights,
        "recommended_topics": topics,
    }

    save_analytics(result)
    print("[analytics] Analytics run complete\n")
    return result


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = run_analytics()
    print(json.dumps(result, indent=2))
