#!/usr/bin/env python3
"""
add_entities.py — Appends 12 new tool stubs to entities.json.
Run this, then immediately run enrich_entities.py to populate
features/support/verdict via Groq.

Usage:
  python scripts/add_entities.py --site email-tools
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
SITES_DIR = ROOT / "sites"

# ── 12 new entities ───────────────────────────────────────────────────────────
# Selected for high comparison search volume across different categories.
# Base fields only — enrich_entities.py fills in features/support/verdict.
NEW_ENTITIES = [
    {
        "slug": "hubspot",
        "name": "HubSpot",
        "category": "email-marketing",
        "tagline": "CRM-powered email marketing for growing teams",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 15,
        "best_for": "businesses that want email and CRM in one platform",
        "founded": 2006,
        "subscribers_limit_free": 1000,
        "key_features": [
            "drag-drop editor", "crm integration", "automation",
            "landing pages", "a/b testing", "analytics", "live chat"
        ],
        "affiliate_program": True,
        "affiliate_commission": "30% recurring",
        "g2_rating": 4.4,
        "trustpilot_rating": 2.5,
        "generated": False,
    },
    {
        "slug": "sendgrid",
        "name": "SendGrid",
        "category": "email-marketing",
        "tagline": "Email delivery you can trust at any scale",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 20,
        "best_for": "developers and high-volume senders",
        "founded": 2009,
        "subscribers_limit_free": 2000,
        "key_features": [
            "transactional email", "api access", "automation",
            "analytics", "a/b testing", "ip warmup"
        ],
        "affiliate_program": True,
        "affiliate_commission": "flat rate",
        "g2_rating": 4.0,
        "trustpilot_rating": 1.8,
        "generated": False,
    },
    {
        "slug": "emailoctopus",
        "name": "EmailOctopus",
        "category": "email-marketing",
        "tagline": "Simple, affordable email marketing",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 9,
        "best_for": "budget-conscious creators and small businesses",
        "founded": 2014,
        "subscribers_limit_free": 2500,
        "key_features": [
            "drag-drop editor", "automation", "landing pages",
            "segmentation", "analytics", "api access"
        ],
        "affiliate_program": True,
        "affiliate_commission": "20% recurring",
        "g2_rating": 4.2,
        "trustpilot_rating": 4.5,
        "generated": False,
    },
    {
        "slug": "sender",
        "name": "Sender",
        "category": "email-marketing",
        "tagline": "Professional email marketing for free",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 15,
        "best_for": "small businesses wanting a generous free plan",
        "founded": 2012,
        "subscribers_limit_free": 2500,
        "key_features": [
            "drag-drop editor", "automation", "sms marketing",
            "popups", "analytics", "segmentation"
        ],
        "affiliate_program": True,
        "affiliate_commission": "20% recurring",
        "g2_rating": 4.4,
        "trustpilot_rating": 4.6,
        "generated": False,
    },
    {
        "slug": "loops",
        "name": "Loops",
        "category": "email-marketing",
        "tagline": "Email for modern SaaS companies",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 49,
        "best_for": "SaaS companies sending product and lifecycle emails",
        "founded": 2022,
        "subscribers_limit_free": 1000,
        "key_features": [
            "transactional email", "automation", "audience segmentation",
            "api access", "analytics", "event-based triggers"
        ],
        "affiliate_program": False,
        "affiliate_commission": None,
        "g2_rating": 4.7,
        "trustpilot_rating": 4.5,
        "generated": False,
    },
    {
        "slug": "ghost",
        "name": "Ghost",
        "category": "email-marketing",
        "tagline": "Independent publishing for newsletters and blogs",
        "pricing_model": "flat-rate",
        "free_tier": False,
        "starting_price_usd": 0,
        "paid_from_usd": 9,
        "best_for": "writers and creators running paid newsletter businesses",
        "founded": 2013,
        "subscribers_limit_free": 0,
        "key_features": [
            "newsletter", "membership", "paid subscriptions",
            "blogging", "analytics", "seo tools"
        ],
        "affiliate_program": False,
        "affiliate_commission": None,
        "g2_rating": 4.1,
        "trustpilot_rating": 3.8,
        "generated": False,
    },
    {
        "slug": "zoho-campaigns",
        "name": "Zoho Campaigns",
        "category": "email-marketing",
        "tagline": "Email marketing built into the Zoho ecosystem",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 4,
        "best_for": "Zoho users and budget-conscious businesses",
        "founded": 2008,
        "subscribers_limit_free": 2000,
        "key_features": [
            "drag-drop editor", "automation", "crm integration",
            "a/b testing", "segmentation", "analytics"
        ],
        "affiliate_program": True,
        "affiliate_commission": "15% recurring",
        "g2_rating": 4.3,
        "trustpilot_rating": 2.9,
        "generated": False,
    },
    {
        "slug": "customer-io",
        "name": "Customer.io",
        "category": "email-marketing",
        "tagline": "Behavioral email and messaging for data-driven teams",
        "pricing_model": "paid",
        "free_tier": False,
        "starting_price_usd": 0,
        "paid_from_usd": 100,
        "best_for": "product and growth teams sending behaviour-triggered messages",
        "founded": 2012,
        "subscribers_limit_free": 0,
        "key_features": [
            "behavioural triggers", "visual workflow", "transactional email",
            "sms marketing", "in-app messaging", "api access", "analytics"
        ],
        "affiliate_program": False,
        "affiliate_commission": None,
        "g2_rating": 4.4,
        "trustpilot_rating": 3.5,
        "generated": False,
    },
    {
        "slug": "postmark",
        "name": "Postmark",
        "category": "email-marketing",
        "tagline": "Transactional email delivery done right",
        "pricing_model": "paid",
        "free_tier": False,
        "starting_price_usd": 0,
        "paid_from_usd": 15,
        "best_for": "developers who need fast, reliable transactional email",
        "founded": 2010,
        "subscribers_limit_free": 0,
        "key_features": [
            "transactional email", "api access", "analytics",
            "message streams", "spam testing", "webhooks"
        ],
        "affiliate_program": False,
        "affiliate_commission": None,
        "g2_rating": 4.6,
        "trustpilot_rating": 4.2,
        "generated": False,
    },
    {
        "slug": "mailgun",
        "name": "Mailgun",
        "category": "email-marketing",
        "tagline": "Email API service built for developers",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 15,
        "best_for": "developers sending transactional and bulk email via API",
        "founded": 2010,
        "subscribers_limit_free": 100,
        "key_features": [
            "email api", "transactional email", "analytics",
            "email validation", "inbound routing", "webhooks"
        ],
        "affiliate_program": True,
        "affiliate_commission": "flat rate",
        "g2_rating": 4.3,
        "trustpilot_rating": 2.2,
        "generated": False,
    },
    {
        "slug": "benchmark-email",
        "name": "Benchmark Email",
        "category": "email-marketing",
        "tagline": "Simple email marketing for growing businesses",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 13,
        "best_for": "small businesses wanting an easy-to-use email platform",
        "founded": 2004,
        "subscribers_limit_free": 500,
        "key_features": [
            "drag-drop editor", "automation", "landing pages",
            "a/b testing", "crm integration", "analytics"
        ],
        "affiliate_program": True,
        "affiliate_commission": "25% recurring",
        "g2_rating": 4.2,
        "trustpilot_rating": 3.8,
        "generated": False,
    },
    {
        "slug": "privy",
        "name": "Privy",
        "category": "email-marketing",
        "tagline": "Email and SMS marketing for e-commerce brands",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 30,
        "best_for": "Shopify stores wanting email, SMS, and popups in one tool",
        "founded": 2011,
        "subscribers_limit_free": 100,
        "key_features": [
            "popups", "email automation", "sms marketing",
            "shopify integration", "abandoned cart", "analytics"
        ],
        "affiliate_program": True,
        "affiliate_commission": "15% recurring",
        "g2_rating": 4.6,
        "trustpilot_rating": 4.1,
        "generated": False,
    },
]

# ── Affiliate URLs for new entities ──────────────────────────────────────────
# Replace with your actual affiliate links before deploying.
NEW_AFFILIATE_URLS = {
    "hubspot":         "https://hubspot.com/",
    "sendgrid":        "https://sendgrid.com/",
    "emailoctopus":    "https://emailoctopus.com/",
    "sender":          "https://www.sender.net/",
    "loops":           "https://loops.so/",
    "ghost":           "https://ghost.org/",
    "zoho-campaigns":  "https://www.zoho.com/campaigns/",
    "customer-io":     "https://customer.io/",
    "postmark":        "https://postmarkapp.com/",
    "mailgun":         "https://www.mailgun.com/",
    "benchmark-email": "https://www.benchmarkemail.com/",
    "privy":           "https://www.privy.com/",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    args = parser.parse_args()

    entities_path = SITES_DIR / args.site / "data" / "entities.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))

    existing_slugs = {e["slug"] for e in entities}
    added = 0
    skipped = 0

    for entity in NEW_ENTITIES:
        if entity["slug"] in existing_slugs:
            print(f"  skip  {entity['slug']} (already exists)")
            skipped += 1
            continue
        entity["affiliate_url"] = NEW_AFFILIATE_URLS.get(
            entity["slug"], f"https://{entity['slug']}.com/")
        entities.append(entity)
        print(f"  added {entity['slug']}")
        added += 1

    entities_path.write_text(
        json.dumps(entities, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\n  Done. Added: {added}, Skipped: {skipped}")
    print(f"  Total entities: {len(entities)}")
    print(f"  Total comparison pairs: {len(entities) * (len(entities) - 1) // 2}")
    print(f"\n  Next step:")
    print(f"  python scripts/enrich_entities.py --site {args.site}")


if __name__ == "__main__":
    main()
