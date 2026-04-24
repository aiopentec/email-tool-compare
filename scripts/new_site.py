#!/usr/bin/env python3
"""
new_site.py — Scaffold a new niche site in the PSEO engine portfolio

Usage:
  python scripts/new_site.py \
    --id "saas-tools" \
    --name "SaaS Tool Compare" \
    --description "Unbiased comparisons for SaaS and productivity tools" \
    --base-url "https://aiopentec.github.io/saas-tool-compare" \
    --niche "SaaS productivity tools" \
    --audience "startup founders, product managers, and remote teams"

After running:
  1. Edit sites/<id>/data/entities.json — add your tool/entity list
  2. Run: python scripts/generate.py --site <id> --limit 50 --demo
  3. Run: python scripts/build.py --site <id>
  4. Add <id> to the matrix in .github/workflows/content_engine.yml
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
SITES_DIR = ROOT / "sites"

ENTITY_TEMPLATE = [
    {
        "slug": "example-tool-a",
        "name": "Example Tool A",
        "category": "YOUR_CATEGORY",
        "tagline": "Your tagline here",
        "pricing_model": "freemium",
        "free_tier": True,
        "starting_price_usd": 0,
        "paid_from_usd": 19,
        "best_for": "small businesses and freelancers",
        "founded": 2020,
        "subscribers_limit_free": 0,
        "key_features": ["feature one", "feature two", "feature three", "feature four", "feature five"],
        "affiliate_program": True,
        "affiliate_commission": "30% recurring",
        "g2_rating": 4.5,
        "trustpilot_rating": 4.2,
        "generated": False
    },
    {
        "slug": "example-tool-b",
        "name": "Example Tool B",
        "category": "YOUR_CATEGORY",
        "tagline": "Another tagline here",
        "pricing_model": "paid",
        "free_tier": False,
        "starting_price_usd": 29,
        "paid_from_usd": 29,
        "best_for": "enterprise teams and agencies",
        "founded": 2018,
        "subscribers_limit_free": 0,
        "key_features": ["feature one", "feature two", "feature three", "feature four"],
        "affiliate_program": True,
        "affiliate_commission": "20% recurring",
        "g2_rating": 4.3,
        "trustpilot_rating": 3.9,
        "generated": False
    }
]


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new PSEO site")
    parser.add_argument("--id", required=True, help="Site ID, e.g. saas-tools")
    parser.add_argument("--name", required=True, help="Display name, e.g. SaaS Tool Compare")
    parser.add_argument("--description", required=True, help="Site description / tagline")
    parser.add_argument("--base-url", required=True, help="Full base URL including path")
    parser.add_argument("--niche", required=True, help="Niche description used in prompts")
    parser.add_argument("--audience", required=True, help="Target audience description")
    args = parser.parse_args()

    site_dir = SITES_DIR / args.id
    data_dir = site_dir / "data"

    if site_dir.exists():
        print(f"Error: Site '{args.id}' already exists at {site_dir}")
        sys.exit(1)

    data_dir.mkdir(parents=True)

    config = {
        "site_id": args.id,
        "site_name": args.name,
        "site_description": args.description,
        "base_url": args.base_url,
        "repo_name": args.base_url.rstrip("/").split("/")[-1],
        "niche": args.niche,
        "audience": args.audience,
        "primary_keyword_pattern": "{tool_a} vs {tool_b}",
        "secondary_keyword_pattern": "{tool_a} alternatives",
        "tertiary_keyword_pattern": "best {tool_a} alternative for {use_case}",
        "affiliate_disclosure": "Some links on this site are affiliate links. We may earn a commission at no extra cost to you.",
        "generate_pages": ["tool", "compare", "alternatives"],
        "pages_per_run": 50,
        "model": "claude-haiku-4-5-20251001",
        "theme_color": "#2563eb",
        "ga4_id": "",
        "gsc_verification": ""
    }

    (site_dir / "config.json").write_text(json.dumps(config, indent=2))
    (data_dir / "entities.json").write_text(json.dumps(ENTITY_TEMPLATE, indent=2))

    print(f"""
╔═══════════════════════════════════════════════════╗
║  Site scaffolded: {args.id:<30}  ║
╠═══════════════════════════════════════════════════╣
║  Next steps:                                       ║
╠═══════════════════════════════════════════════════╣
║  1. Edit your entity list:                         ║
║     sites/{args.id}/data/entities.json
║                                                    ║
║     Populate with 15-30 real tools/entities.       ║
║     The more attributes you fill in, the better    ║
║     the AI-generated content quality.              ║
║                                                    ║
║  2. Test the pipeline (no API calls):              ║
║     python scripts/generate.py \\                  ║
║       --site {args.id} --limit 20 --demo
║                                                    ║
║  3. Build and preview:                             ║
║     python scripts/build.py --site {args.id}
║     open dist/{args.id}/index.html
║                                                    ║
║  4. Add to automation matrix:                      ║
║     .github/workflows/content_engine.yml           ║
║     matrix: site: [..., {args.id}]
╚═══════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
