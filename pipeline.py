"""
pipeline.py — NovaMind Core Pipeline
Handles blog generation, newsletter creation, HubSpot contact sync,
campaign logging, and orchestrates the full content workflow.
"""

import os
import re
import json
import uuid
from datetime import datetime, timezone

import google.generativeai as genai
from hubspot import HubSpot
from hubspot.crm.contacts import SimplePublicObjectInputForCreate
from hubspot.crm.contacts import PublicObjectSearchRequest, Filter, FilterGroup
from hubspot.crm.contacts.exceptions import ApiException
from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate as NoteInput
from hubspot.crm.objects.notes.exceptions import ApiException as NoteApiException
from dotenv import load_dotenv

# ── Environment ──────────────────────────────────────────────────────────────

load_dotenv()

# Configure Google Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini = genai.GenerativeModel("gemini-2.5-flash")

# Configure HubSpot client
hubspot_client = HubSpot(access_token=os.getenv("HUBSPOT_API_KEY"))
contacts_api = hubspot_client.crm.contacts.basic_api

# ── Mock contacts (9 total, 3 per persona) ───────────────────────────────────

CONTACTS = [
    # Agency Founders — focus on ROI, cost savings, business growth
    {"firstname": "James",  "lastname": "Park",    "email": "james@founderstudio.io",   "jobtitle": "Agency Founder"},
    {"firstname": "Lisa",   "lastname": "Johnson", "email": "lisa@studiofounder.co",    "jobtitle": "Agency Founder"},
    {"firstname": "David",  "lastname": "Chen",    "email": "david@creativeagency.io",  "jobtitle": "Agency Founder"},
    # Marketing Managers — focus on campaign performance, lead generation
    {"firstname": "Sarah",  "lastname": "Kim",     "email": "sarah@growthlab.co",       "jobtitle": "Marketing Manager"},
    {"firstname": "Rachel", "lastname": "Wong",    "email": "rachel@marketingpro.co",   "jobtitle": "Marketing Manager"},
    {"firstname": "Kevin",  "lastname": "Park",    "email": "kevin@growthmarketer.io",  "jobtitle": "Marketing Manager"},
    # Operations Managers — focus on workflow efficiency, team productivity
    {"firstname": "Mia",    "lastname": "Lee",     "email": "mia@opsagency.com",        "jobtitle": "Operations Manager"},
    {"firstname": "Tom",    "lastname": "Harris",  "email": "tom@projectops.com",       "jobtitle": "Operations Manager"},
    {"firstname": "Anna",   "lastname": "Kim",     "email": "anna@opsmanager.com",      "jobtitle": "Operations Manager"},
]

# ── Helper ────────────────────────────────────────────────────────────────────

def _strip_json(text: str) -> str:
    """
    Remove markdown code fences (```json ... ``` or ``` ... ```) from a
    Gemini response so it can be safely passed to json.loads().
    """
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


# ── Blog generation ───────────────────────────────────────────────────────────

def generate_blog(topic: str) -> dict:
    """
    Use Gemini to generate a structured blog post for the given topic.

    Returns a dict with keys:
        title   — catchy blog title
        outline — list of 3 section headings
        content — 400-600 word body text
    """
    prompt = f"""
You are a content writer for NovaMind, an AI startup that helps small creative agencies automate workflows.

Write a complete blog post about: "{topic}"

CRITICAL REQUIREMENTS FOR THE "content" FIELD:
- Write the FULL, COMPLETE article — not a summary, not a placeholder, not an excerpt
- The content must be between 400 and 600 words of real, substantive prose
- Cover all three outline sections in sequence using clear paragraph breaks
- Write in an engaging, professional tone suitable for creative agency owners

Return ONLY valid JSON (no markdown, no code fences) in this exact format:
{{
  "title": "Compelling blog title here",
  "outline": ["Section 1 heading", "Section 2 heading", "Section 3 heading"],
  "content": "WRITE THE COMPLETE 400-600 WORD ARTICLE HERE. Every sentence counts. Start writing the introduction paragraph immediately, then cover section 2, then section 3, ending with a strong conclusion. Do not write a placeholder — write the actual full article."
}}
""".strip()

    try:
        response = gemini.generate_content(prompt)
        data = json.loads(_strip_json(response.text))
        print(f"[pipeline] Blog generated: {data.get('title', 'Untitled')}")
        return data
    except Exception as e:
        print(f"[pipeline] ERROR generating blog: {e}")
        # Return a minimal fallback so the pipeline can continue
        return {
            "title": f"The Future of {topic}",
            "outline": ["Introduction", "Key Benefits", "Getting Started"],
            "content": f"An exploration of {topic} for modern creative agencies.",
        }


# ── Newsletter generation ─────────────────────────────────────────────────────

def generate_newsletters(blog_title: str, blog_content: str) -> dict:
    """
    Use Gemini to generate three persona-specific newsletter versions
    based on the generated blog post.

    Returns a dict keyed by persona name, each value containing:
        subject — email subject line
        body    — 3-4 sentence email body with a CTA
    """
    prompt = f"""
You are an email marketer for NovaMind, an AI startup serving creative agencies.

Based on this blog post titled "{blog_title}":
{blog_content[:1500]}

Write three personalised newsletter emails, one per audience persona.
Each email should have a subject line and a 3-4 sentence body ending with a clear call-to-action (CTA).

Persona guidance and required CTA style:
- Agency Founder: business-focused, data-driven tone. CTA must be ROI or profitability focused
  (e.g. "See how agencies cut costs by 30% — Book a demo", "Calculate your ROI — Get started free").
- Marketing Manager: strategic, metrics-focused tone. CTA must reference campaign results or performance
  (e.g. "See real campaign benchmarks — Start your free trial", "Improve your open rates — View the report").
- Operations Manager: practical, process-oriented tone. CTA must reference workflow or efficiency demo
  (e.g. "Watch the workflow demo — Book a 15-min walkthrough", "See how it streamlines your ops — Try it free").

Return ONLY valid JSON (no markdown, no code fences) in this exact format:
{{
  "Agency Founder": {{
    "subject": "Subject line for founders",
    "body": "3-4 sentence body ending with an ROI or profitability CTA."
  }},
  "Marketing Manager": {{
    "subject": "Subject line for marketing managers",
    "body": "3-4 sentence body ending with a campaign results or performance CTA."
  }},
  "Operations Manager": {{
    "subject": "Subject line for ops managers",
    "body": "3-4 sentence body ending with a workflow or efficiency demo CTA."
  }}
}}
""".strip()

    try:
        response = gemini.generate_content(prompt)
        data = json.loads(_strip_json(response.text))
        print(f"[pipeline] Newsletters generated for {list(data.keys())}")
        return data
    except Exception as e:
        print(f"[pipeline] ERROR generating newsletters: {e}")
        # Fallback: minimal newsletter content for each persona
        fallback = {}
        for persona in ["Agency Founder", "Marketing Manager", "Operations Manager"]:
            fallback[persona] = {
                "subject": f"{blog_title} — A Message for You",
                "body": f"We have new insights on {blog_title} tailored for your role. Read our latest post to stay ahead. Click here to read more.",
            }
        return fallback


# ── HubSpot contact creation ──────────────────────────────────────────────────

def create_hubspot_contacts() -> list:
    """
    Create all 9 mock contacts in HubSpot.
    Sets the jobtitle property to the persona name for each contact.
    Handles CONTACT_EXISTS errors gracefully — skips duplicates without crashing.

    Returns a list of status strings (one per contact).
    """
    results = []

    for contact in CONTACTS:
        name = f"{contact['firstname']} {contact['lastname']}"
        try:
            payload = SimplePublicObjectInputForCreate(properties=contact)
            contacts_api.create(simple_public_object_input_for_create=payload)
            print(f"[pipeline] Created contact: {name}")
            results.append(f"created: {name}")
        except ApiException as e:
            # HubSpot returns 409 with CONTACT_EXISTS when the email already exists
            if "CONTACT_EXISTS" in str(e.body):
                print(f"[pipeline] Contact already exists, skipping: {name}")
                results.append(f"exists: {name}")
            else:
                print(f"[pipeline] ERROR creating {name}: {e}")
                results.append(f"error: {name} — {e.status}")
        except Exception as e:
            print(f"[pipeline] Unexpected error for {name}: {e}")
            results.append(f"error: {name}")

    return results


# ── Campaign logging ──────────────────────────────────────────────────────────

def log_campaign(blog_title: str, newsletters: dict) -> dict:
    """
    Append a campaign record to campaign_history.json.

    Each record contains:
        campaign_id — short unique ID
        blog_title  — title of the generated blog post
        send_date   — UTC ISO timestamp
        personas    — list of persona names that received newsletters
        status      — "sent"

    Returns the campaign dict.
    """
    campaign = {
        "campaign_id": str(uuid.uuid4())[:8],
        "blog_title": blog_title,
        "send_date": datetime.now(timezone.utc).isoformat(),
        "personas": list(newsletters.keys()),
        "status": "sent",
    }

    history_path = "campaign_history.json"
    try:
        if os.path.exists(history_path):
            with open(history_path, "r") as f:
                history = json.load(f)
        else:
            history = []

        history.append(campaign)

        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)

        print(f"[pipeline] Campaign logged: {campaign['campaign_id']}")
    except Exception as e:
        print(f"[pipeline] ERROR logging campaign: {e}")

    return campaign


# ── HubSpot campaign notes ────────────────────────────────────────────────────

def log_hubspot_notes(campaign: dict) -> list:
    """
    Attach a campaign note to each HubSpot contact.

    For each contact we:
      1. Search HubSpot by email to get the contact's internal ID
         (works whether the contact was just created or already existed)
      2. Create a Note CRM object with campaign metadata
      3. Associate the note with the contact via associationTypeId 202
         (the standard HUBSPOT_DEFINED note→contact association)

    This function is intentionally non-blocking — any individual failure is
    logged and skipped so the rest of the pipeline is never interrupted.

    Returns a list of status strings (one per contact).
    """
    results = []
    notes_api = hubspot_client.crm.objects.notes.basic_api

    for contact in CONTACTS:
        name = f"{contact['firstname']} {contact['lastname']}"
        try:
            # Step 1 — look up contact ID by email
            search_filter = Filter(
                property_name="email",
                operator="EQ",
                value=contact["email"],
            )
            filter_group = FilterGroup(filters=[search_filter])
            search_req = PublicObjectSearchRequest(filter_groups=[filter_group])
            search_res = contacts_api.search(public_object_search_request=search_req)

            if not search_res.results:
                print(f"[pipeline] Note skipped — contact not found in HubSpot: {name}")
                results.append(f"not_found: {name}")
                continue

            contact_id = search_res.results[0].id

            # Step 2 — build note body
            note_body = (
                f"NovaMind Campaign Note\n"
                f"Campaign ID : {campaign.get('campaign_id', '—')}\n"
                f"Blog Title  : {campaign.get('blog_title', '—')}\n"
                f"Persona     : {contact.get('jobtitle', '—')}\n"
                f"Send Date   : {campaign.get('send_date', '—')}"
            )

            # Step 3 — create note with contact association in a single API call
            note_input = NoteInput(
                properties={
                    "hs_note_body": note_body,
                    # HubSpot expects timestamp in milliseconds
                    "hs_timestamp": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                },
                associations=[
                    {
                        "to": {"id": contact_id},
                        "types": [
                            {
                                "associationCategory": "HUBSPOT_DEFINED",
                                "associationTypeId": 202,  # note → contact
                            }
                        ],
                    }
                ],
            )
            notes_api.create(simple_public_object_input_for_create=note_input)
            print(f"[pipeline] Note logged for: {name}")
            results.append(f"noted: {name}")

        except (ApiException, NoteApiException, Exception) as e:
            # Non-blocking: log the error but never raise
            print(f"[pipeline] Note failed for {name}: {e}")
            results.append(f"note_error: {name}")

    return results


# ── Two-step pipeline functions ───────────────────────────────────────────────

def generate_content(topic: str) -> dict:
    """
    Step 1 of the pipeline — content generation only.

    Calls Gemini to produce a blog post and three persona newsletters.
    Makes NO HubSpot API calls and writes NO files, so it is safe to call
    repeatedly (e.g. when the user regenerates content before approving).

    Returns {"blog": ..., "newsletters": ...}
    """
    print(f"\n[pipeline] Generating content for: '{topic}'")
    blog        = generate_blog(topic)
    newsletters = generate_newsletters(blog["title"], blog["content"])
    print(f"[pipeline] Content ready: '{blog.get('title', '—')}'")
    return {"blog": blog, "newsletters": newsletters}


def send_campaign(blog: dict, newsletters: dict) -> dict:
    """
    Step 2 of the pipeline — distribute and log.

    Called only after the user has reviewed and approved the content.
    Syncs contacts to HubSpot, logs the campaign, attaches notes, and
    saves the full snapshot to latest_content.json.

    This does NOT send emails — actual email delivery requires a separate
    email service provider (e.g. HubSpot Marketing, Mailchimp).

    Returns the full content dict (same structure as run_pipeline).
    """
    print("\n[pipeline] Sending campaign…")

    contact_results = create_hubspot_contacts()
    campaign        = log_campaign(blog["title"], newsletters)
    note_results    = log_hubspot_notes(campaign)

    content = {
        "blog":            blog,
        "newsletters":     newsletters,
        "campaign":        campaign,
        "contact_results": contact_results,
        "note_results":    note_results,
    }

    try:
        with open("latest_content.json", "w") as f:
            json.dump(content, f, indent=2)
        print("[pipeline] Saved latest_content.json")
    except Exception as e:
        print(f"[pipeline] ERROR saving latest_content.json: {e}")

    print(f"[pipeline] Campaign sent — {campaign['campaign_id']} | notes: {len(note_results)}\n")
    return content


# ── Main orchestrator (generate + send in one call) ───────────────────────────

def run_pipeline(topic: str) -> dict:
    """
    Convenience function: generate_content() + send_campaign() in one call.
    Used for CLI testing. The Streamlit dashboard calls the two steps separately
    so the user can review content before it is logged.
    """
    print(f"\n[pipeline] Starting pipeline for topic: '{topic}'")
    draft = generate_content(topic)
    return send_campaign(draft["blog"], draft["newsletters"])


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = run_pipeline("How AI is transforming creative agency workflows in 2025")
    print(json.dumps(result, indent=2))
