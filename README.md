# NovaMind Content Pipeline

An AI-powered marketing automation pipeline that generates, distributes, and optimizes blog and newsletter content — built as a take-home assignment for a Content & Growth Analyst role.

**Live Dashboard:** https://novamind-pipeline-7qnew5gmpmfexvrbggwv6h.streamlit.app/

---

## What it does

Takes a single blog topic as input and automatically:
1. Generates a 400–600 word blog post using Google Gemini
2. Creates 3 persona-specific newsletter versions of that blog
3. Syncs 9 segmented contacts to HubSpot CRM
4. Logs the campaign with a unique ID and timestamp
5. Simulates performance data and generates AI-powered insights
6. Recommends next blog topics based on engagement trends

---

## Architecture
```
Topic Input
→ AI Content Engine (Gemini)
→ Blog + Persona-based Newsletters
→ HubSpot CRM (contacts + campaign logging)
→ campaign_history.json (storage)
→ Analytics Engine (performance simulation)
→ AI Insight + Next Topic Recommendations
→ Streamlit Dashboard
```
---

## Personas

| Persona | Focus | Newsletter Tone |
|---|---|---|
| Agency Founder | ROI, cost savings, business growth | Business-focused, data-driven |
| Marketing Manager | Campaign performance, lead generation | Strategic, metrics-focused |
| Operations Manager | Workflow efficiency, team productivity | Practical, process-oriented |

Performance ranges are calibrated per persona based on realistic B2B email benchmarks:
- Marketing Manager consistently shows highest engagement (active content seekers)
- Agency Founder shows moderate engagement (time-poor, selective)
- Operations Manager shows lowest engagement (less content-driven)

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Google Gemini API (gemini-2.5-flash) | Blog + newsletter generation, AI insights |
| HubSpot CRM API | Contact management, persona segmentation |
| Streamlit | Web dashboard UI |
| Altair | Performance charts |
| Python / JSON | Data storage and pipeline logic |

---

## Assumptions & Design Decisions

- **Email delivery is simulated.** In production, this would integrate with HubSpot Marketing or Mailchimp for actual sends.
- **Performance data is mock-simulated** with realistic per-persona ranges. In production, this would be pulled from HubSpot's Campaign Analytics API.
- **9 mock contacts** (3 per persona) are used to demonstrate CRM segmentation. The architecture supports any number of real contacts.
- **Campaign history and analytics** are stored locally in JSON files. In production, these would live in HubSpot or a database.

---

## How to Run Locally

1. Clone the repo

git clone https://github.com/staceylim/novamind-pipeline.git
cd novamind-pipeline

2. Install dependencies

pip install -r requirements.txt

3. Set up environment variables

Create a .env file in the root directory:

Note: API keys are configured in Streamlit Cloud secrets for the live demo.

4. Run the dashboard

streamlit run app.py

---

## File Structure

```
novamind-pipeline/
├── app.py              # Streamlit dashboard
├── pipeline.py         # AI content generation + HubSpot integration
├── analytics.py        # Performance simulation + AI insights
├── requirements.txt    # Dependencies
├── .env                # API keys (not tracked)
└── .gitignore
```

---

## Continuous Optimization Loop

The system is designed to improve over time:

Performance data → AI analysis → Next topic recommendations → New campaign

After each analytics run, Gemini analyzes which persona had the lowest engagement
and recommends 3 targeted blog topics to improve future performance.
