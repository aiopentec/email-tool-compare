#!/usr/bin/env python3
"""
generate.py — AI content generation pipeline
Reads entities.json, calls Claude API for each unprocessed entity,
writes structured JSON content files ready for static site build.

Usage:
  python scripts/generate.py --site email-tools --limit 50
  python scripts/generate.py --site email-tools --limit 10 --demo   # no API calls
  python scripts/generate.py --site email-tools --type compare       # only compare pages
"""

import argparse
import json
import pathlib
import sys
import time
import itertools
import random

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).parent.parent
SITES_DIR = ROOT / "sites"
CONTENT_DIR = ROOT / "content"


# ── Prompts ────────────────────────────────────────────────────────────────────

TOOL_PAGE_PROMPT = """\
You are a helpful, unbiased product reviewer writing for a comparison website.
Write a detailed review page for {name}, an email marketing tool.

Tool data:
{tool_data}

Return ONLY valid JSON (no markdown, no preamble) with this exact schema:
{{
  "type": "tool",
  "slug": "{slug}",
  "title": "{name} Review 2025: Features, Pricing & Honest Verdict",
  "meta_description": "string under 155 chars",
  "h1": "string",
  "intro": "2-3 sentence paragraph introducing the tool and who it's best for",
  "verdict": "2-3 sentence honest overall verdict with specific strengths and weaknesses",
  "pros": ["string", "string", "string", "string"],
  "cons": ["string", "string", "string"],
  "pricing_summary": "2 sentences describing the pricing structure clearly",
  "best_for_detail": "2 sentences explaining specifically which type of user benefits most",
  "faq": [
    {{"q": "Is {name} free?", "a": "string (2-3 sentences)"}},
    {{"q": "What is {name} best used for?", "a": "string (2-3 sentences)"}},
    {{"q": "Is {name} good for beginners?", "a": "string (2-3 sentences)"}},
    {{"q": "Does {name} have an affiliate program?", "a": "string (2-3 sentences)"}}
  ]
}}"""

COMPARE_PAGE_PROMPT = """\
You are a helpful, unbiased product reviewer writing for a comparison website.
Write a detailed comparison between {name_a} and {name_b}, two email marketing tools.

Tool A — {name_a}:
{data_a}

Tool B — {name_b}:
{data_b}

Return ONLY valid JSON (no markdown, no preamble) with this exact schema:
{{
  "type": "compare",
  "slug": "{slug_a}-vs-{slug_b}",
  "title": "{name_a} vs {name_b} (2025): Which Is Better?",
  "meta_description": "string under 155 chars",
  "h1": "string",
  "intro": "2-3 sentence paragraph framing the comparison and who should care",
  "quick_verdict": {{
    "winner_overall": "{name_a} or {name_b}",
    "winner_price": "{name_a} or {name_b}",
    "winner_features": "{name_a} or {name_b}",
    "winner_beginners": "{name_a} or {name_b}",
    "winner_ecommerce": "{name_a} or {name_b}"
  }},
  "comparison_table": [
    {{"feature": "string", "tool_a": "string", "tool_b": "string"}},
    {{"feature": "string", "tool_a": "string", "tool_b": "string"}},
    {{"feature": "string", "tool_a": "string", "tool_b": "string"}},
    {{"feature": "string", "tool_a": "string", "tool_b": "string"}},
    {{"feature": "string", "tool_a": "string", "tool_b": "string"}}
  ],
  "choose_a_if": ["string", "string", "string"],
  "choose_b_if": ["string", "string", "string"],
  "faq": [
    {{"q": "Is {name_a} better than {name_b}?", "a": "string (2-3 sentences)"}},
    {{"q": "Which is cheaper, {name_a} or {name_b}?", "a": "string (2-3 sentences)"}},
    {{"q": "Can I switch from {name_b} to {name_a}?", "a": "string (2-3 sentences)"}}
  ]
}}"""

ALTERNATIVES_PAGE_PROMPT = """\
You are a helpful, unbiased product reviewer writing for a comparison website.
Write a page listing the best alternatives to {name}, an email marketing tool.

Tool being replaced:
{tool_data}

Alternative tools to mention (pick the 5 most relevant):
{alternatives_data}

Return ONLY valid JSON (no markdown, no preamble) with this exact schema:
{{
  "type": "alternatives",
  "slug": "{slug}-alternatives",
  "title": "7 Best {name} Alternatives in 2025 (Free & Paid)",
  "meta_description": "string under 155 chars",
  "h1": "string",
  "intro": "2-3 sentence paragraph explaining why someone might want an alternative",
  "why_switch": ["string", "string", "string"],
  "alternatives": [
    {{
      "slug": "string",
      "name": "string",
      "tagline": "string",
      "best_for": "string",
      "key_difference": "2 sentences on what makes this the best alternative in a specific situation"
    }}
  ],
  "faq": [
    {{"q": "What is the best free alternative to {name}?", "a": "string (2-3 sentences)"}},
    {{"q": "What is the best {name} alternative for small business?", "a": "string (2-3 sentences)"}},
    {{"q": "Is there a cheaper alternative to {name}?", "a": "string (2-3 sentences)"}}
  ]
}}"""


# ── Demo content generator (no API needed) ────────────────────────────────────

def demo_tool_content(entity: dict) -> dict:
    name = entity["name"]
    return {
        "type": "tool",
        "slug": entity["slug"],
        "title": f"{name} Review 2025: Features, Pricing & Honest Verdict",
        "meta_description": f"Is {name} worth it in 2025? We break down pricing, features, pros and cons so you can decide.",
        "h1": f"{name} Review 2025: Everything You Need to Know",
        "intro": f"{name} is {entity['tagline'].lower()} that positions itself for {entity['best_for']}. Founded in {entity['founded']}, it has become one of the most recognised platforms in the email marketing space. In this review we cover what it does well, where it falls short, and who should actually use it.",
        "verdict": f"{name} is a solid choice for {entity['best_for']}. Its {'free tier is genuinely useful' if entity['free_tier'] else 'paid-only pricing reflects its focus on serious senders'}. The main trade-off is between its particular strengths and the limitations that make alternatives worth considering for some users.",
        "pros": [f"Good fit for {entity['best_for']}", f"Competitive pricing starting at ${entity['paid_from_usd']}/mo", f"Key feature: {entity['key_features'][0].title()}", f"{'Free tier available' if entity['free_tier'] else 'Mature, well-supported platform'}"],
        "cons": ["Can get expensive at higher subscriber counts", "Learning curve for advanced automations", "Some features locked to higher tiers"],
        "pricing_summary": f"{name} {'offers a free plan' if entity['free_tier'] else 'starts at $' + str(entity['starting_price_usd']) + '/month'}, with paid plans from ${entity['paid_from_usd']}/month. Pricing typically scales with subscriber count.",
        "best_for_detail": f"{name} works best for {entity['best_for']}. If you fit that profile, the feature set aligns well. If you need something different, check the alternatives section.",
        "faq": [
            {"q": f"Is {name} free?", "a": f"{'Yes, ' + name + ' has a free plan supporting up to ' + str(entity['subscribers_limit_free']) + ' subscribers.' if entity['free_tier'] else name + ' does not offer a free plan. Paid plans start at $' + str(entity['paid_from_usd']) + '/month.'} This makes it {'accessible for new senders testing the platform' if entity['free_tier'] else 'more suited to established senders with a budget'}."},
            {"q": f"What is {name} best used for?", "a": f"{name} is best for {entity['best_for']}. Its standout features include {', '.join(entity['key_features'][:3])}, which suit this use case well."},
            {"q": f"Is {name} good for beginners?", "a": f"{name} is {'generally beginner-friendly' if entity['pricing_model'] == 'freemium' else 'aimed at users with some email marketing experience'}. The interface is straightforward for basic campaigns, though advanced automation features have a learning curve."},
            {"q": f"Does {name} have an affiliate program?", "a": f"{'Yes, ' + name + ' runs an affiliate program paying ' + entity['affiliate_commission'] + '.' if entity['affiliate_program'] else name + ' does not currently offer an affiliate program.'} This is worth considering if you plan to recommend the platform to your audience."}
        ]
    }


def demo_compare_content(entity_a: dict, entity_b: dict) -> dict:
    a, b = entity_a["name"], entity_b["name"]
    winner = a if entity_a.get("g2_rating", 0) >= entity_b.get("g2_rating", 0) else b
    cheaper = a if entity_a["paid_from_usd"] <= entity_b["paid_from_usd"] else b
    return {
        "type": "compare",
        "slug": f"{entity_a['slug']}-vs-{entity_b['slug']}",
        "title": f"{a} vs {b} (2025): Which Is Better?",
        "meta_description": f"{a} vs {b}: compare pricing, features, and real use cases to find the right email tool for your needs.",
        "h1": f"{a} vs {b}: Side-by-Side Comparison (2025)",
        "intro": f"Choosing between {a} and {b} comes down to your specific use case. Both are legitimate email marketing platforms, but they serve different audiences. {a} is built for {entity_a['best_for']}, while {b} targets {entity_b['best_for']}. This comparison covers the key differences so you can decide quickly.",
        "quick_verdict": {
            "winner_overall": winner,
            "winner_price": cheaper,
            "winner_features": a if len(entity_a["key_features"]) >= len(entity_b["key_features"]) else b,
            "winner_beginners": a if entity_a["free_tier"] else b,
            "winner_ecommerce": b if "e-commerce" in " ".join(entity_b["key_features"]).lower() else a
        },
        "comparison_table": [
            {"feature": "Starting price", "tool_a": f"${entity_a['paid_from_usd']}/mo", "tool_b": f"${entity_b['paid_from_usd']}/mo"},
            {"feature": "Free plan", "tool_a": "Yes" if entity_a["free_tier"] else "No", "tool_b": "Yes" if entity_b["free_tier"] else "No"},
            {"feature": "Best for", "tool_a": entity_a["best_for"].title(), "tool_b": entity_b["best_for"].title()},
            {"feature": "Free subscriber limit", "tool_a": str(entity_a["subscribers_limit_free"]) if entity_a["free_tier"] else "N/A", "tool_b": str(entity_b["subscribers_limit_free"]) if entity_b["free_tier"] else "N/A"},
            {"feature": "G2 rating", "tool_a": str(entity_a.get("g2_rating", "N/A")), "tool_b": str(entity_b.get("g2_rating", "N/A"))}
        ],
        "choose_a_if": [f"You are primarily focused on {entity_a['best_for']}", f"You value {entity_a['key_features'][0]}", f"You prefer {entity_a['pricing_model']} pricing"],
        "choose_b_if": [f"You are primarily focused on {entity_b['best_for']}", f"You value {entity_b['key_features'][0]}", f"You prefer {entity_b['pricing_model']} pricing"],
        "faq": [
            {"q": f"Is {a} better than {b}?", "a": f"It depends on your use case. {a} wins for {entity_a['best_for']}, while {b} is stronger for {entity_b['best_for']}. Neither is objectively better — the right choice depends on your specific needs."},
            {"q": f"Which is cheaper, {a} or {b}?", "a": f"{cheaper} starts at a lower price point (${min(entity_a['paid_from_usd'], entity_b['paid_from_usd'])}/mo vs ${max(entity_a['paid_from_usd'], entity_b['paid_from_usd'])}/mo). However, pricing scales with subscriber count, so the total cost depends on your list size."},
            {"q": f"Can I switch from {b} to {a}?", "a": f"Yes, switching from {b} to {a} is possible. Most platforms support CSV import/export for subscriber lists. Plan for some time to recreate automations and templates, as these rarely transfer directly between platforms."}
        ]
    }


def demo_alternatives_content(entity: dict, all_entities: list) -> dict:
    name = entity["name"]
    others = [e for e in all_entities if e["slug"] != entity["slug"]][:5]
    return {
        "type": "alternatives",
        "slug": f"{entity['slug']}-alternatives",
        "title": f"7 Best {name} Alternatives in 2025 (Free & Paid)",
        "meta_description": f"Looking for a {name} alternative? We compare the top options by price, features, and use case.",
        "h1": f"Best {name} Alternatives in 2025: Honest Comparison",
        "intro": f"While {name} is a capable platform, it is not the right fit for everyone. Whether you need a lower price point, a different feature set, or a platform better suited to your audience, there are strong alternatives worth considering. This guide covers the best {name} alternatives in 2025.",
        "why_switch": [
            f"You have outgrown {name}'s free tier limits",
            "You need features that are not available on this plan",
            "Pricing does not scale well for your subscriber count"
        ],
        "alternatives": [
            {
                "slug": o["slug"],
                "name": o["name"],
                "tagline": o["tagline"],
                "best_for": o["best_for"],
                "key_difference": f"{o['name']} is built for {o['best_for']}. It distinguishes itself from {name} through {o['key_features'][0]} and {o['key_features'][1]}, making it a strong choice when those capabilities are a priority."
            }
            for o in others
        ],
        "faq": [
            {"q": f"What is the best free alternative to {name}?", "a": f"{'MailerLite and Brevo both offer generous free plans that are worth considering as free alternatives to ' + name + '.' if entity['slug'] not in ['mailerlite','brevo'] else 'Moosend and ConvertKit offer strong free alternatives in this space.'} The best choice depends on your list size and the features you need most."},
            {"q": f"What is the best {name} alternative for small business?", "a": f"For small businesses, MailerLite is frequently recommended as a {name} alternative due to its low cost and ease of use. ActiveCampaign is worth considering if you need CRM features alongside email marketing."},
            {"q": f"Is there a cheaper alternative to {name}?", "a": f"{'Yes — ' + name + ' is not the cheapest option in the market.' if entity['paid_from_usd'] > 15 else 'Most competitors are similarly priced or higher at scale.'} Moosend and MailerLite consistently rank as the most affordable options with a comparable feature set."}
        ]
    }


# ── Real API generation ────────────────────────────────────────────────────────

def generate_with_api(client, prompt: str, retries: int = 3) -> dict:
    """Supports Groq (free), Gemini (free), or Anthropic."""
    import os
    provider = os.environ.get("AI_PROVIDER", "anthropic")

    for attempt in range(retries):
        try:
            if provider == "groq":
                # Groq — free tier, OpenAI-compatible
                import urllib.request, json as _json
                key = os.environ["GROQ_API_KEY"]
                payload = _json.dumps({
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2048, "temperature": 0.3
                }).encode()
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=payload,
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    text = _json.loads(r.read())["choices"][0]["message"]["content"].strip()

            elif provider == "gemini":
                # Gemini — free tier via Google AI Studio
                import urllib.request, json as _json
                key = os.environ["GEMINI_API_KEY"]
                payload = _json.dumps({
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.3}
                }).encode()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
                req = urllib.request.Request(url, data=payload,
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    text = _json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"].strip()

            else:
                # Anthropic (default)
                msg = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                text = msg.content[0].text.strip()

            # Strip markdown fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            return json.loads(text)

        except (json.JSONDecodeError, Exception) as e:
            if attempt == retries - 1:
                raise
            print(f"  Retry {attempt + 1}/{retries} after error: {e}")
            time.sleep(2 ** attempt)


# ── Main pipeline ──────────────────────────────────────────────────────────────

def generate_tool_pages(entities, site_cfg, content_dir, demo, client, limit_remaining):
    generated = 0
    for entity in entities:
        if generated >= limit_remaining:
            break
        out_path = content_dir / "tools" / f"{entity['slug']}.json"
        if out_path.exists():
            continue
        print(f"  [tool] {entity['name']} ...", end=" ", flush=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if demo:
            content = demo_tool_content(entity)
        else:
            prompt = TOOL_PAGE_PROMPT.format(
                name=entity["name"], slug=entity["slug"],
                tool_data=json.dumps(entity, indent=2)
            )
            content = generate_with_api(client, prompt)
        out_path.write_text(json.dumps(content, indent=2, ensure_ascii=False))
        entity["generated"] = True
        print("done")
        time.sleep(4)  # Gemini free tier: 15 req/min
        generated += 1
    return generated


def generate_compare_pages(entities, site_cfg, content_dir, demo, client, limit_remaining):
    generated = 0
    pairs = list(itertools.combinations(entities, 2))
    random.shuffle(pairs)  # vary what gets generated each run
    for a, b in pairs:
        if generated >= limit_remaining:
            break
        slug = f"{a['slug']}-vs-{b['slug']}"
        out_path = content_dir / "compare" / f"{slug}.json"
        if out_path.exists():
            continue
        print(f"  [compare] {a['name']} vs {b['name']} ...", end=" ", flush=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if demo:
            content = demo_compare_content(a, b)
        else:
            prompt = COMPARE_PAGE_PROMPT.format(
                name_a=a["name"], slug_a=a["slug"], data_a=json.dumps(a, indent=2),
                name_b=b["name"], slug_b=b["slug"], data_b=json.dumps(b, indent=2)
            )
            content = generate_with_api(client, prompt)
        out_path.write_text(json.dumps(content, indent=2, ensure_ascii=False))
        print("done")
        time.sleep(4)  # Gemini free tier: 15 req/min
        generated += 1
    return generated


def generate_alternatives_pages(entities, site_cfg, content_dir, demo, client, limit_remaining):
    generated = 0
    for entity in entities:
        if generated >= limit_remaining:
            break
        out_path = content_dir / "alternatives" / f"{entity['slug']}-alternatives.json"
        if out_path.exists():
            continue
        print(f"  [alternatives] {entity['name']} ...", end=" ", flush=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if demo:
            content = demo_alternatives_content(entity, entities)
        else:
            others = [e for e in entities if e["slug"] != entity["slug"]]
            prompt = ALTERNATIVES_PAGE_PROMPT.format(
                name=entity["name"], slug=entity["slug"],
                tool_data=json.dumps(entity, indent=2),
                alternatives_data=json.dumps(others[:8], indent=2)
            )
            content = generate_with_api(client, prompt)
        out_path.write_text(json.dumps(content, indent=2, ensure_ascii=False))
        print("done")
        time.sleep(4)  # Gemini free tier: 15 req/min
        generated += 1
    return generated


def main():
    parser = argparse.ArgumentParser(description="Generate programmatic SEO content")
    parser.add_argument("--site", required=True, help="Site ID (e.g. email-tools)")
    parser.add_argument("--limit", type=int, default=50, help="Max pages to generate per run")
    parser.add_argument("--type", choices=["all", "tool", "compare", "alternatives"], default="all")
    parser.add_argument("--demo", action="store_true", help="Run without API calls (uses template content)")
    args = parser.parse_args()

    site_dir = SITES_DIR / args.site
    entities_path = site_dir / "data" / "entities.json"
    config_path = site_dir / "config.json"

    if not entities_path.exists():
        print(f"Error: {entities_path} not found")
        sys.exit(1)

    entities = json.loads(entities_path.read_text())
    site_cfg = json.loads(config_path.read_text())
    content_dir = ROOT / "content" / args.site

    client = None
    if not args.demo:
        import os
        provider = os.environ.get("AI_PROVIDER", "anthropic")

        if provider == "groq":
            if not os.environ.get("GROQ_API_KEY"):
                print("Error: GROQ_API_KEY not set. Get a free key at console.groq.com")
                sys.exit(1)
            print(f"  Using provider: Groq (free tier) — llama-3.1-8b-instant")
            client = None  # Groq uses urllib directly

        elif provider == "gemini":
            if not os.environ.get("GEMINI_API_KEY"):
                print("Error: GEMINI_API_KEY not set. Get a free key at aistudio.google.com")
                sys.exit(1)
            print(f"  Using provider: Gemini (free tier) — gemini-1.5-flash")
            client = None  # Gemini uses urllib directly

        else:
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                print("Error: ANTHROPIC_API_KEY not set. Run with --demo to test without API.")
                sys.exit(1)
            client = anthropic.Anthropic(api_key=api_key)
            print(f"  Using provider: Anthropic — claude-haiku")

    mode = "DEMO (no API)" if args.demo else "LIVE (Claude API)"
    print(f"\n{'='*55}")
    print(f"  PSEO Engine — {site_cfg['site_name']}")
    print(f"  Mode: {mode} | Limit: {args.limit} pages")
    print(f"{'='*55}\n")

    remaining = args.limit
    total = 0

    if args.type in ("all", "tool"):
        print("Generating tool pages...")
        n = generate_tool_pages(entities, site_cfg, content_dir, args.demo, client, remaining)
        total += n; remaining -= n

    if args.type in ("all", "alternatives") and remaining > 0:
        print("\nGenerating alternatives pages...")
        n = generate_alternatives_pages(entities, site_cfg, content_dir, args.demo, client, remaining)
        total += n; remaining -= n

    if args.type in ("all", "compare") and remaining > 0:
        print("\nGenerating compare pages...")
        n = generate_compare_pages(entities, site_cfg, content_dir, args.demo, client, remaining)
        total += n; remaining -= n

    # Save updated entity flags back to disk
    entities_path.write_text(json.dumps(entities, indent=2, ensure_ascii=False))

    print(f"\n{'='*55}")
    print(f"  Done. Generated {total} pages.")
    print(f"  Content saved to: content/{args.site}/")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
