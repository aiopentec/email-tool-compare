#!/usr/bin/env python3
"""
enrich_entities.py — Populates missing feature flags, support info, verdicts,
and affiliate URLs for all entities in entities.json using the Groq API (free tier).

Run once locally (or via GitHub Actions):
  python scripts/enrich_entities.py --site email-tools
  python scripts/enrich_entities.py --site email-tools --demo
  python scripts/enrich_entities.py --site email-tools --slug mailchimp

Writes results back to sites/<site>/data/entities.json in-place.
Skips any entity that already has a 'features' dict (safe to re-run).

Groq free tier limits (as of 2024):
  llama-3.3-70b-versatile — 6000 req/day, 30 req/min
  18 entities = 18 requests — well within limits.
"""

import argparse
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).parent.parent
SITES_DIR = ROOT / "sites"

try:
    from groq import Groq
except ImportError:
    print("Error: groq not installed. Run: pip install groq")
    sys.exit(1)


# ── Model ─────────────────────────────────────────────────────────────────────
GROQ_MODEL = "llama-3.3-70b-versatile"   # best free model on Groq; handles JSON well


# ── Demo stubs ────────────────────────────────────────────────────────────────
DEMO_FEATURES = {
    "email_automation":    True,
    "visual_workflow":     False,
    "landing_pages":       True,
    "crm_builtin":         False,
    "sms_marketing":       False,
    "ab_testing":          True,
    "ecommerce":           True,
    "transactional_email": False,
    "remove_branding":     False,
    "ai_subject_lines":    True,
    "ai_send_time":        False,
}
DEMO_SUPPORT = {"email": True, "live_chat": True, "phone": False}


# ── Affiliate URL map ─────────────────────────────────────────────────────────
# Replace placeholder URLs with your actual affiliate links.
AFFILIATE_URLS = {
    "mailchimp":        "https://mailchimp.com/",
    "activecampaign":   "https://www.activecampaign.com/",
    "klaviyo":          "https://www.klaviyo.com/",
    "brevo":            "https://www.brevo.com/",
    "constantcontact":  "https://www.constantcontact.com/",
    "getresponse":      "https://www.getresponse.com/",
    "mailerlite":       "https://www.mailerlite.com/",
    "convertkit":       "https://convertkit.com/",
    "moosend":          "https://moosend.com/",
    "drip":             "https://www.drip.com/",
    "omnisend":         "https://www.omnisend.com/",
    "sendinblue":       "https://www.brevo.com/",
    "hubspot":          "https://www.hubspot.com/",
    "campaign-monitor": "https://www.campaignmonitor.com/",
    "aweber":           "https://www.aweber.com/",
    "benchmark":        "https://www.benchmarkemail.com/",
    "zoho-campaigns":   "https://www.zoho.com/campaigns/",
    "sendgrid":         "https://sendgrid.com/",
}


def build_prompt(entity: dict) -> str:
    return f"""You are a product research assistant. Given factual data about an email marketing tool,
return a JSON object with ONLY the fields listed below. Be accurate — base answers on real
product capabilities as of 2024. Do not guess; if uncertain, default to false.

Tool data:
{json.dumps(entity, indent=2)}

Return ONLY valid JSON — no markdown fences, no explanation, no preamble:
{{
  "free_trial": <bool>,
  "features": {{
    "email_automation":    <bool>,
    "visual_workflow":     <bool>,
    "landing_pages":       <bool>,
    "crm_builtin":         <bool>,
    "sms_marketing":       <bool>,
    "ab_testing":          <bool>,
    "ecommerce":           <bool>,
    "transactional_email": <bool>,
    "remove_branding":     <bool>,
    "ai_subject_lines":    <bool>,
    "ai_send_time":        <bool>
  }},
  "support": {{
    "email":     <bool>,
    "live_chat": <bool>,
    "phone":     <bool>
  }},
  "verdict": "<one sentence: what this tool is best for>"
}}"""


def enrich_entity_via_api(entity: dict, client: Groq) -> dict:
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": build_prompt(entity)}],
        temperature=0.1,
        max_tokens=500,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


def enrich_entity_demo(entity: dict) -> dict:
    name     = entity.get("name", "this tool")
    best_for = entity.get("best_for", "businesses of all sizes")
    return {
        "free_trial": entity.get("free_tier", False),
        "features":   DEMO_FEATURES.copy(),
        "support":    DEMO_SUPPORT.copy(),
        "verdict":    f"{name} is a solid choice for {best_for}.",
    }


def enrich(site_id: str, target_slug: str = None, demo: bool = False):
    entities_path = SITES_DIR / site_id / "data" / "entities.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))

    client = None
    if not demo:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            print("Error: GROQ_API_KEY not set.")
            print("  Set it with: set GROQ_API_KEY=your-key   (Windows)")
            print("  Or use --demo to run without API calls.")
            sys.exit(1)
        client = Groq(api_key=api_key)
        print(f"  Using Groq model: {GROQ_MODEL}")

    enriched_count = 0
    skipped_count  = 0

    for entity in entities:
        slug = entity["slug"]

        if target_slug and slug != target_slug:
            continue

        if "features" in entity and not target_slug:
            print(f"  skip  {slug} (already enriched)")
            skipped_count += 1
            continue

        print(f"  enriching {slug}...", end=" ", flush=True)

        try:
            enrichment = enrich_entity_demo(entity) if demo \
                else enrich_entity_via_api(entity, client)

            entity.update(enrichment)

            # Remap existing fields to names the table expects
            entity.setdefault("free_plan",     entity.get("free_tier", False))
            entity.setdefault("rating",        entity.get("g2_rating", 0))
            entity.setdefault("starting_at",   f"${entity.get('paid_from_usd', 0)}/mo"
                                               if entity.get("paid_from_usd", 0) > 0
                                               else "Free")
            entity.setdefault("affiliate_url", AFFILIATE_URLS.get(
                slug, f"https://{slug}.com/"))

            enriched_count += 1
            print("✓")

            # Groq free tier: 30 req/min — 2s gap keeps us safely within limit
            if not demo:
                time.sleep(2)

        except json.JSONDecodeError as e:
            print(f"✗  JSON parse error: {e}")
        except Exception as e:
            print(f"✗  Error: {e}")

    entities_path.write_text(
        json.dumps(entities, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\n  Done. Enriched: {enriched_count}, Skipped: {skipped_count}")
    print(f"  Saved → {entities_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site",  required=True)
    parser.add_argument("--slug",  default=None, help="Single entity slug to (re-)enrich")
    parser.add_argument("--demo",  action="store_true", help="No API calls, stub data")
    args = parser.parse_args()
    enrich(args.site, args.slug, args.demo)


if __name__ == "__main__":
    main()