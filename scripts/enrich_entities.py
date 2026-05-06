#!/usr/bin/env python3
"""
enrich_entities.py — Populates missing feature flags, support info, verdicts,
and affiliate URLs for all entities in entities.json using the Gemini API (free tier).

Usage:
  python scripts/enrich_entities.py --site email-tools
  python scripts/enrich_entities.py --site email-tools --demo
  python scripts/enrich_entities.py --site email-tools --slug hubspot
"""

import argparse, json, os, pathlib, sys, time, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).parent.parent
SITES_DIR = ROOT / "sites"

GEMINI_MODEL   = "gemini-1.5-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

DEMO_FEATURES = {
    "email_automation": True, "visual_workflow": False, "landing_pages": True,
    "crm_builtin": False, "sms_marketing": False, "ab_testing": True,
    "ecommerce": True, "transactional_email": False, "remove_branding": False,
    "ai_subject_lines": True, "ai_send_time": False,
}
DEMO_SUPPORT = {"email": True, "live_chat": True, "phone": False}

AFFILIATE_URLS = {
    "mailchimp": "https://mailchimp.com/", "activecampaign": "https://www.activecampaign.com/",
    "klaviyo": "https://www.klaviyo.com/", "brevo": "https://www.brevo.com/",
    "constantcontact": "https://www.constantcontact.com/", "getresponse": "https://www.getresponse.com/",
    "mailerlite": "https://www.mailerlite.com/", "convertkit": "https://convertkit.com/",
    "moosend": "https://moosend.com/", "drip": "https://www.drip.com/",
    "omnisend": "https://www.omnisend.com/", "sendinblue": "https://www.brevo.com/",
    "hubspot": "https://hubspot.com/", "sendgrid": "https://sendgrid.com/",
    "emailoctopus": "https://emailoctopus.com/", "sender": "https://www.sender.net/",
    "loops": "https://loops.so/", "ghost": "https://ghost.org/",
    "zoho-campaigns": "https://www.zoho.com/campaigns/", "customer-io": "https://customer.io/",
    "postmark": "https://postmarkapp.com/", "mailgun": "https://www.mailgun.com/",
    "benchmark-email": "https://www.benchmarkemail.com/", "privy": "https://www.privy.com/",
}

def build_prompt(entity):
    return f"""You are a product research assistant. Given data about an email marketing tool,
return a JSON object. Be accurate based on real product capabilities as of 2024.

Tool data:
{json.dumps(entity, indent=2)}

Return ONLY valid JSON, no markdown fences, no explanation:
{{
  "free_trial": <bool>,
  "features": {{
    "email_automation": <bool>, "visual_workflow": <bool>, "landing_pages": <bool>,
    "crm_builtin": <bool>, "sms_marketing": <bool>, "ab_testing": <bool>,
    "ecommerce": <bool>, "transactional_email": <bool>, "remove_branding": <bool>,
    "ai_subject_lines": <bool>, "ai_send_time": <bool>
  }},
  "support": {{"email": <bool>, "live_chat": <bool>, "phone": <bool>}},
  "verdict": "<one sentence: what this tool is best for>"
}}"""

def enrich_via_api(entity, api_key):
    url = GEMINI_API_URL.format(model=GEMINI_MODEL, key=api_key)
    payload = json.dumps({
        "contents": [{"parts": [{"text": build_prompt(entity)}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 600,
            "responseMimeType": "application/json",
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def enrich_demo(entity):
    return {
        "free_trial": entity.get("free_tier", False),
        "features": DEMO_FEATURES.copy(),
        "support": DEMO_SUPPORT.copy(),
        "verdict": f"{entity.get('name','Tool')} is a solid choice for {entity.get('best_for','businesses')}.",
    }

def enrich(site_id, target_slug=None, demo=False):
    path = SITES_DIR / site_id / "data" / "entities.json"
    entities = json.loads(path.read_text(encoding="utf-8"))

    api_key = None
    if not demo:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Error: GEMINI_API_KEY not set.")
            print("  Set it with: export GEMINI_API_KEY=your-key")
            print("  Or use --demo to run without API calls.")
            sys.exit(1)
        print(f"  Using Gemini model: {GEMINI_MODEL}")

    enriched = skipped = 0

    for entity in entities:
        slug = entity["slug"]
        if target_slug and slug != target_slug:
            continue
        if "features" in entity and not target_slug:
            print(f"  skip  {slug} (already enriched)")
            skipped += 1
            continue

        print(f"  enriching {slug}...", end=" ", flush=True)
        try:
            data = enrich_demo(entity) if demo else enrich_via_api(entity, api_key)
            entity.update(data)
            entity.setdefault("free_plan",    entity.get("free_tier", False))
            entity.setdefault("rating",       entity.get("g2_rating", 0))
            entity.setdefault("starting_at",
                f"${entity.get('paid_from_usd',0)}/mo"
                if entity.get("paid_from_usd", 0) > 0 else "Free")
            entity.setdefault("affiliate_url",
                AFFILIATE_URLS.get(slug, entity.get("affiliate_url", f"https://{slug}.com/")))
            enriched += 1
            print("✓")
            if not demo:
                time.sleep(1)   # Gemini free tier: 15 req/min — 1s gap is sufficient
        except Exception as e:
            print(f"✗  {e}")

    path.write_text(json.dumps(entities, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Done. Enriched: {enriched}, Skipped: {skipped}")
    print(f"  Saved → {path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--slug", default=None, help="Re-enrich a single entity by slug")
    parser.add_argument("--demo", action="store_true", help="No API calls, stub data")
    args = parser.parse_args()
    enrich(args.site, args.slug, args.demo)

if __name__ == "__main__":
    main()