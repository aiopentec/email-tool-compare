#!/usr/bin/env python3
"""
build.py — Static site generator
Reads content JSON files → renders Jinja2 templates → writes HTML to dist/

Usage:
  python scripts/build.py --site email-tools
"""

import argparse
import json
import pathlib
import shutil
import itertools
import sys
from datetime import datetime, timezone

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Error: jinja2 not installed. Run: pip install jinja2")
    sys.exit(1)

ROOT = pathlib.Path(__file__).parent.parent
SITES_DIR = ROOT / "sites"
CONTENT_DIR = ROOT / "content"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"


def schema_article(title, description, url, site_name):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "url": url,
        "publisher": {"@type": "Organization", "name": site_name}
    })


def schema_faq(faq_items):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": i["q"],
             "acceptedAnswer": {"@type": "Answer", "text": i["a"]}}
            for i in faq_items
        ]
    })


def load_entities(site_id):
    path = SITES_DIR / site_id / "data" / "entities.json"
    return json.loads(path.read_text())


def find_related_compares(entity_slug, entities, limit=5):
    """Return compare page slugs involving this entity."""
    related = []
    for other in entities:
        if other["slug"] == entity_slug:
            continue
        related.append({
            "slug": f"{entity_slug}-vs-{other['slug']}",
            "label": f"{next(e['name'] for e in entities if e['slug']==entity_slug)} vs {other['name']}"
        })
        if len(related) >= limit:
            break
    return related


def build(site_id):
    config_path = SITES_DIR / site_id / "config.json"
    site_cfg = json.loads(config_path.read_text())
    entities = load_entities(site_id)
    entity_map = {e["slug"]: e for e in entities}

    content_dir = CONTENT_DIR / site_id
    dist_dir = ROOT / "dist" / site_id
    dist_dir.mkdir(parents=True, exist_ok=True)

    # Copy static assets
    dist_static = dist_dir / "static"
    if dist_static.exists():
        shutil.rmtree(dist_static)
    shutil.copytree(STATIC_DIR, dist_static)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    sitemap_urls = []
    page_count = 0

    # ── Homepage ────────────────────────────────────────────────────────────────
    home_tmpl = env.get_template("home.html")

    # Sample 12 compare pages for featured section
    all_pairs = list(itertools.combinations(entities, 2))
    featured_compares = [
        {"slug": f"{a['slug']}-vs-{b['slug']}",
         "title": f"{a['name']} vs {b['name']}"}
        for a, b in all_pairs[:12]
    ]

    home_html = home_tmpl.render(
        site=site_cfg,
        entities=entities,
        featured_compares=featured_compares,
        entity_count=len(entities),
        page={"title": site_cfg["site_name"], "meta_description": site_cfg["site_description"],
              "url_path": "", "schema_json": "{}"}
    )
    (dist_dir / "index.html").write_text(home_html, encoding="utf-8")
    sitemap_urls.append({"url": f"{site_cfg['base_url']}/", "priority": "1.0", "changefreq": "weekly"})
    page_count += 1

    # ── Tool pages ──────────────────────────────────────────────────────────────
    tool_tmpl = env.get_template("tool.html")
    tools_dir = content_dir / "tools"
    if tools_dir.exists():
        out_dir = dist_dir / "tools"
        out_dir.mkdir(exist_ok=True)
        for json_file in tools_dir.glob("*.json"):
            page_data = json.loads(json_file.read_text())
            slug = json_file.stem
            entity = entity_map.get(slug, {})
            url_path = f"tools/{slug}/"
            full_url = f"{site_cfg['base_url']}/{url_path}"

            page_data["url_path"] = url_path
            page_data["schema_json"] = schema_faq(page_data.get("faq", []))

            related = find_related_compares(slug, entities)
            html = tool_tmpl.render(
                site=site_cfg, page=page_data,
                entity=entity, related_pages=related
            )
            page_out = out_dir / slug
            page_out.mkdir(exist_ok=True)
            (page_out / "index.html").write_text(html, encoding="utf-8")
            sitemap_urls.append({"url": full_url, "priority": "0.8", "changefreq": "monthly"})
            page_count += 1

    # ── Compare pages ───────────────────────────────────────────────────────────
    compare_tmpl = env.get_template("compare.html")
    compare_dir = content_dir / "compare"
    if compare_dir.exists():
        out_dir = dist_dir / "compare"
        out_dir.mkdir(exist_ok=True)
        for json_file in compare_dir.glob("*.json"):
            page_data = json.loads(json_file.read_text())
            slug = json_file.stem
            url_path = f"compare/{slug}/"
            full_url = f"{site_cfg['base_url']}/{url_path}"

            # Extract entity slugs from compare slug (e.g. "mailchimp-vs-beehiiv")
            parts = slug.split("-vs-", 1)
            entity_a = entity_map.get(parts[0], {}) if len(parts) == 2 else {}
            entity_b = entity_map.get(parts[1], {}) if len(parts) == 2 else {}

            # Related: other comparisons involving either tool
            related = [
                {"slug": f"{entity_a.get('slug','')}-vs-{e['slug']}",
                 "label": f"{entity_a.get('name','')} vs {e['name']}"}
                for e in entities
                if e["slug"] not in (entity_a.get("slug"), entity_b.get("slug"))
            ][:4]

            page_data["url_path"] = url_path
            page_data["schema_json"] = schema_faq(page_data.get("faq", []))

            html = compare_tmpl.render(
                site=site_cfg, page=page_data,
                entity_a=entity_a, entity_b=entity_b,
                related_pages=related
            )
            page_out = out_dir / slug
            page_out.mkdir(exist_ok=True)
            (page_out / "index.html").write_text(html, encoding="utf-8")
            sitemap_urls.append({"url": full_url, "priority": "0.9", "changefreq": "monthly"})
            page_count += 1

    # ── Alternatives pages ──────────────────────────────────────────────────────
    alt_tmpl = env.get_template("alternatives.html")
    alt_content_dir = content_dir / "alternatives"
    if alt_content_dir.exists():
        out_dir = dist_dir / "alternatives"
        out_dir.mkdir(exist_ok=True)
        for json_file in alt_content_dir.glob("*.json"):
            page_data = json.loads(json_file.read_text())
            slug = json_file.stem  # e.g. "mailchimp-alternatives"
            base_slug = slug.replace("-alternatives", "")
            entity = entity_map.get(base_slug, {})
            url_path = f"alternatives/{slug}/"
            full_url = f"{site_cfg['base_url']}/{url_path}"

            page_data["url_path"] = url_path
            page_data["schema_json"] = schema_faq(page_data.get("faq", []))

            html = alt_tmpl.render(
                site=site_cfg, page=page_data, entity=entity
            )
            page_out = out_dir / slug
            page_out.mkdir(exist_ok=True)
            (page_out / "index.html").write_text(html, encoding="utf-8")
            sitemap_urls.append({"url": full_url, "priority": "0.85", "changefreq": "monthly"})
            page_count += 1

    # ── Compare index page
        compare_index = dist_dir / "compare" / "index.html"
        compare_links = "".join(
            f'<li><a href="{site_cfg["base_url"]}/compare/{u["url"].split("/compare/")[1]}">{u["url"].split("/compare/")[1].replace("/","").replace("-vs-"," vs ").replace("-"," ").title()}</a></li>'
            for u in sitemap_urls if "/compare/" in u["url"] and u["url"].count("/") > 4
        )
        compare_index.write_text(f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
    <title>All Comparisons | {site_cfg["site_name"]}</title>
    <link rel="stylesheet" href="{site_cfg["base_url"]}/static/style.css"></head>
    <body><header class="site-header"><div class="container">
    <a href="{site_cfg["base_url"]}/" class="logo">{site_cfg["site_name"]}</a></div></header>
    <main class="container"><h1 style="margin:2rem 0 1rem">All Comparisons</h1>
    <ul style="columns:2;gap:2rem">{compare_links}</ul></main></body></html>''', encoding="utf-8")
    

    # ── Compare index page
    comp_dir = content_dir / "compare"
    if comp_dir.exists():
        comp_index = dist_dir / "compare" / "index.html"
        base = site_cfg["base_url"]
        name = site_cfg["site_name"]
        links = "".join(
            "<li><a href='" + base + "/compare/" + p.stem + "/'>" +
            p.stem.replace("-vs-", " vs ").replace("-", " ").title() +
            "</a></li>"
            for p in sorted(comp_dir.glob("*.json"))
        )
        comp_index.write_text(
            "<!DOCTYPE html><html lang=en><head><meta charset=UTF-8>"
            "<title>All Comparisons | " + name + "</title>"
            "<link rel=stylesheet href='" + base + "/static/style.css'></head>"
            "<body><header class=site-header><div class=container>"
            "<a href='" + base + "/' class=logo>" + name + "</a>"
            "<nav><a href='" + base + "/compare/'>Compare Tools</a> "
            "<a href='" + base + "/alternatives/'>Alternatives</a> "
            "<a href='" + base + "/tools/'>All Tools</a></nav>"
            "</div></header><main class=container>"
            "<h1 style='margin:2rem 0 0.5rem'>All Comparisons</h1>"
            "<ul style='columns:2;padding-left:1.5rem'>" + links + "</ul>"
            "</main></body></html>",
            encoding="utf-8"
        )

    # ── Alternatives index page
    alt_dir = content_dir / "alternatives"
    if alt_dir.exists():
        alt_index = dist_dir / "alternatives" / "index.html"
        base = site_cfg["base_url"]
        name = site_cfg["site_name"]
        links = "".join(
            "<li><a href='" + base + "/alternatives/" + p.stem + "/'>" +
            p.stem.replace("-alternatives", "").replace("-", " ").title() +
            " Alternatives</a></li>"
            for p in sorted(alt_dir.glob("*.json"))
        )
        alt_index.write_text(
            "<!DOCTYPE html><html lang=en><head><meta charset=UTF-8>"
            "<title>All Alternatives | " + name + "</title>"
            "<link rel=stylesheet href='" + base + "/static/style.css'></head>"
            "<body><header class=site-header><div class=container>"
            "<a href='" + base + "/' class=logo>" + name + "</a>"
            "<nav><a href='" + base + "/compare/'>Compare Tools</a> "
            "<a href='" + base + "/alternatives/'>Alternatives</a> "
            "<a href='" + base + "/tools/'>All Tools</a></nav>"
            "</div></header><main class=container>"
            "<h1 style='margin:2rem 0 0.5rem'>All Alternatives</h1>"
            "<ul style='columns:2;padding-left:1.5rem'>" + links + "</ul>"
            "</main></body></html>",
            encoding="utf-8"
        )

    # ── Sitemap ─────────────────────────────────────────────────────────────────
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in sitemap_urls:
        sitemap_lines += [
            "  <url>",
            f"    <loc>{u['url']}</loc>",
            f"    <lastmod>{today}</lastmod>",
            f"    <changefreq>{u['changefreq']}</changefreq>",
            f"    <priority>{u['priority']}</priority>",
            "  </url>"
        ]
    sitemap_lines.append("</urlset>")
    (dist_dir / "sitemap.xml").write_text("\n".join(sitemap_lines), encoding="utf-8")

    # ── robots.txt ──────────────────────────────────────────────────────────────
    (dist_dir / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {site_cfg['base_url']}/sitemap.xml\n",
        encoding="utf-8"
    )

    print(f"\n{'='*50}")
    print(f"  Build complete: {page_count} pages")
    print(f"  Sitemap: {len(sitemap_urls)} URLs")
    print(f"  Output:  dist/{site_id}/")
    print(f"{'='*50}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    args = parser.parse_args()
    build(args.site)


if __name__ == "__main__":
    main()
