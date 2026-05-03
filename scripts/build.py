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


# ── NEW: Sendinblue → Brevo redirect map ────────────────────────────────────
# Keys   = old Sendinblue slugs to retire (both orderings)
# Values = replacement Brevo page path (relative, no leading slash)
# Add a row for every Sendinblue compare/tool page you currently publish.
SENDINBLUE_REDIRECTS = {
    # compare pages — canonical ordering
    "sendinblue-vs-mailchimp":       "compare/brevo-vs-mailchimp",
    "sendinblue-vs-activecampaign":  "compare/brevo-vs-activecampaign",
    "sendinblue-vs-klaviyo":         "compare/brevo-vs-klaviyo",
    "sendinblue-vs-constantcontact": "compare/brevo-vs-constantcontact",
    "sendinblue-vs-getresponse":     "compare/brevo-vs-getresponse",
    "sendinblue-vs-moosend":         "compare/brevo-vs-moosend",
    "sendinblue-vs-mailerlite":      "compare/brevo-vs-mailerlite",
    "sendinblue-vs-convertkit":      "compare/brevo-vs-convertkit",
    # compare pages — reversed ordering (both must redirect)
    "mailchimp-vs-sendinblue":       "compare/brevo-vs-mailchimp",
    "activecampaign-vs-sendinblue":  "compare/brevo-vs-activecampaign",
    "klaviyo-vs-sendinblue":         "compare/brevo-vs-klaviyo",
    "constantcontact-vs-sendinblue": "compare/brevo-vs-constantcontact",
    "getresponse-vs-sendinblue":     "compare/brevo-vs-getresponse",
    "moosend-vs-sendinblue":         "compare/brevo-vs-moosend",
    "mailerlite-vs-sendinblue":      "compare/brevo-vs-mailerlite",
    "convertkit-vs-sendinblue":      "compare/brevo-vs-convertkit",
    # tool page
    "tools/sendinblue":              "tools/brevo",
}
# ── END NEW ──────────────────────────────────────────────────────────────────


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
    if not faq_items: return "{}"
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": i["q"],
             "acceptedAnswer": {"@type": "Answer", "text": i["a"]}}
            for i in faq_items
        ]
    })


# ── NEW: canonical URL helper ────────────────────────────────────────────────
def get_canonical_slug(slug_a: str, slug_b: str) -> str:
    """
    Returns the canonical compare slug using alphabetical ordering.
    Both 'mailchimp-vs-klaviyo' and 'klaviyo-vs-mailchimp' return
    'klaviyo-vs-mailchimp' — so Google indexes only one version.
    """
    ordered = sorted([slug_a.lower(), slug_b.lower()])
    return f"{ordered[0]}-vs-{ordered[1]}"
# ── END NEW ──────────────────────────────────────────────────────────────────


# ── DROP-IN REPLACEMENT for generate_comparison_table() in scripts/build.py ──
#
# Paste this over the existing function (search for "def generate_comparison_table").
# Changes from previous version:
#   - Reads free_tier as fallback for free_plan
#   - Reads g2_rating as fallback for rating
#   - Reads paid_from_usd as fallback for starting_at
#   - Infers feature flags from key_features[] array as last-resort fallback
#   - affiliate_url falls back to affiliate_program homepage pattern
#
# Everything else (HTML output, CSS) is identical.

def generate_comparison_table(entity_a: dict, entity_b: dict, page_data: dict) -> str:
    def yes(val):
        return '<span class="chk y" aria-label="Yes">✓</span>' if val \
          else '<span class="chk n" aria-label="No">✗</span>'

    def stars(rating):
        r = float(rating) if rating else 0
        full = int(r)
        return "★" * full + "☆" * (5 - full) + f"<small> {r}/5</small>"

    def get_bool(entity, *keys):
        """
        Try multiple keys in order, return bool.
        Last arg can be a fallback bool (default False).
        """
        fallback = False
        check_keys = list(keys)
        if isinstance(check_keys[-1], bool):
            fallback = check_keys.pop()
        for k in check_keys:
            if k in entity:
                return bool(entity[k])
        return fallback

    def feat(entity, key):
        """
        Look up a feature flag. Priority:
        1. entity['features'][key]        — populated by enrich_entities.py
        2. entity[key]                    — direct field
        3. key_features array inference   — e.g. 'ab_testing' ← 'A/B testing' in list
        """
        features = entity.get("features", {})
        if key in features:
            return bool(features[key])
        if key in entity:
            return bool(entity[key])
        # Infer from key_features string list
        kf = [k.lower() for k in entity.get("key_features", [])]
        inference_map = {
            "email_automation":    ["automation", "email automation"],
            "visual_workflow":     ["visual workflow", "visual automation"],
            "landing_pages":       ["landing pages", "landing page"],
            "crm_builtin":         ["crm", "built-in crm"],
            "sms_marketing":       ["sms", "sms marketing"],
            "ab_testing":          ["a/b testing", "ab testing", "split testing"],
            "ecommerce":           ["ecommerce", "e-commerce", "woocommerce", "shopify"],
            "transactional_email": ["transactional", "transactional email"],
            "remove_branding":     ["remove branding", "white label"],
            "ai_subject_lines":    ["ai", "subject line", "ai subject"],
            "ai_send_time":        ["send time", "send time optimization"],
        }
        return any(term in " ".join(kf) for term in inference_map.get(key, []))

    def get_starting_price(entity):
        if "starting_at" in entity:
            return entity["starting_at"]
        paid = entity.get("paid_from_usd")
        if paid is not None:
            return f"${paid}/mo" if paid > 0 else "Free"
        return "—"

    def get_rating(entity):
        return entity.get("rating") or entity.get("g2_rating") or 0

    def get_affiliate_url(entity):
        if "affiliate_url" in entity:
            return entity["affiliate_url"]
        slug = entity.get("slug", "")
        return f"https://{slug}.com/"   # safe fallback until AFFILIATE_URLS are set

    a, b = entity_a, entity_b

    rows = [
        ("💰 Pricing", None, None),
        ("Free Plan",
            yes(get_bool(a, "free_plan", "free_tier")),
            yes(get_bool(b, "free_plan", "free_tier"))),
        ("Starting Price",
            get_starting_price(a),
            get_starting_price(b)),
        ("Free Trial",
            yes(get_bool(a, "free_trial")),
            yes(get_bool(b, "free_trial"))),

        ("⚙️ Features", None, None),
        ("Email Automation",
            yes(feat(a, "email_automation")),
            yes(feat(b, "email_automation"))),
        ("Visual Workflow Builder",
            yes(feat(a, "visual_workflow")),
            yes(feat(b, "visual_workflow"))),
        ("Landing Pages",
            yes(feat(a, "landing_pages")),
            yes(feat(b, "landing_pages"))),
        ("Built-in CRM",
            yes(feat(a, "crm_builtin")),
            yes(feat(b, "crm_builtin"))),
        ("SMS Marketing",
            yes(feat(a, "sms_marketing")),
            yes(feat(b, "sms_marketing"))),
        ("A/B Testing",
            yes(feat(a, "ab_testing")),
            yes(feat(b, "ab_testing"))),
        ("E-commerce Integration",
            yes(feat(a, "ecommerce")),
            yes(feat(b, "ecommerce"))),
        ("Transactional Email",
            yes(feat(a, "transactional_email")),
            yes(feat(b, "transactional_email"))),
        ("Remove Branding",
            yes(feat(a, "remove_branding")),
            yes(feat(b, "remove_branding"))),

        ("🤖 AI Features", None, None),
        ("AI Subject Lines",
            yes(feat(a, "ai_subject_lines")),
            yes(feat(b, "ai_subject_lines"))),
        ("AI Send-Time Optimisation",
            yes(feat(a, "ai_send_time")),
            yes(feat(b, "ai_send_time"))),

        ("🛎 Support", None, None),
        ("Email Support",
            yes(a.get("support", {}).get("email", False)),
            yes(b.get("support", {}).get("email", False))),
        ("Live Chat",
            yes(a.get("support", {}).get("live_chat", False)),
            yes(b.get("support", {}).get("live_chat", False))),
        ("Phone Support",
            yes(a.get("support", {}).get("phone", False)),
            yes(b.get("support", {}).get("phone", False))),
    ]

    tbody = ""
    for row in rows:
        label, cell_a, cell_b = row
        if cell_a is None:
            tbody += f'<tr class="sec-hdr"><td colspan="3">{label}</td></tr>\n'
        else:
            tbody += (f'<tr><td class="lbl">{label}</td>'
                      f'<td>{cell_a}</td><td>{cell_b}</td></tr>\n')

    aff_a    = get_affiliate_url(a)
    aff_b    = get_affiliate_url(b)
    verdict_a = a.get("verdict") or page_data.get("verdict_a") or a.get("tagline", "")
    verdict_b = b.get("verdict") or page_data.get("verdict_b") or b.get("tagline", "")
    rating_a  = get_rating(a)
    rating_b  = get_rating(b)

    return f"""
<div class="cmp-wrap">
  <table class="cmp-tbl" role="table"
         aria-label="{a['name']} vs {b['name']} feature comparison">
    <thead>
      <tr>
        <th class="col-feat">Feature</th>
        <th class="col-tool">
          <a href="{aff_a}" target="_blank" rel="noopener sponsored">{a['name']}</a>
        </th>
        <th class="col-tool">
          <a href="{aff_b}" target="_blank" rel="noopener sponsored">{b['name']}</a>
        </th>
      </tr>
    </thead>
    <tbody>{tbody}</tbody>
  </table>

  <div class="rating-row">
    <div class="r-cell"><strong>{a['name']}</strong>
      <div class="stars">{stars(rating_a)}</div></div>
    <div class="r-cell"><strong>{b['name']}</strong>
      <div class="stars">{stars(rating_b)}</div></div>
  </div>

  <div class="verdict-row">
    <div class="v-cell">
      <span class="v-label">Our verdict</span>
      <p>{verdict_a}</p>
      <a class="cta-btn" href="{aff_a}" target="_blank" rel="noopener sponsored">
        Try {a['name']} Free →
      </a>
    </div>
    <div class="v-cell">
      <span class="v-label">Our verdict</span>
      <p>{verdict_b}</p>
      <a class="cta-btn" href="{aff_b}" target="_blank" rel="noopener sponsored">
        Try {b['name']} Free →
      </a>
    </div>
  </div>
</div>

<style>
.cmp-wrap{{width:100%;overflow-x:auto;margin:2rem 0;font-size:.95rem}}
.cmp-tbl{{width:100%;border-collapse:collapse;min-width:480px}}
.cmp-tbl th,.cmp-tbl td{{padding:.65rem 1rem;text-align:center;border-bottom:1px solid #e8e8e8}}
.cmp-tbl th{{background:#1a3a5c;color:#fff;font-weight:700}}
.cmp-tbl th.col-feat,.cmp-tbl td.lbl{{text-align:left;font-size:.88rem;width:46%}}
.cmp-tbl th.col-feat{{color:#fff}}
.cmp-tbl td.lbl{{color:#444}}
.cmp-tbl tr:hover td{{background:#fafafa}}
.cmp-tbl tr.sec-hdr td{{background:#f0f4f8;font-weight:700;font-size:.75rem;
  text-transform:uppercase;letter-spacing:.06em;color:#555;padding:.4rem 1rem;
  border-top:2px solid #d8e4f0}}
.chk{{font-size:1.05rem;font-weight:700}}
.chk.y{{color:#22a06b}}.chk.n{{color:#c9372c}}
.rating-row,.verdict-row{{display:flex;gap:1rem;margin-top:1rem}}
.r-cell{{flex:1;text-align:center;padding:.75rem;background:#f7f7f7;border-radius:8px}}
.stars{{font-size:1.15rem;color:#f5a623;margin-top:.25rem}}
.stars small{{font-size:.78rem;color:#666}}
.v-cell{{flex:1;padding:1rem 1.25rem;border:1px solid #e0e8f0;border-radius:8px;text-align:center}}
.v-label{{display:block;font-size:.72rem;text-transform:uppercase;
  letter-spacing:.06em;color:#888;margin-bottom:.4rem}}
.v-cell p{{font-size:.88rem;color:#333;margin:0 0 1rem}}
.cta-btn{{display:inline-block;padding:.6rem 1.4rem;background:#1a56db;color:#fff!important;
  border-radius:6px;font-size:.88rem;font-weight:600;text-decoration:none;
  transition:background .15s ease}}
.cta-btn:hover{{background:#1444b8;text-decoration:none}}
@media(max-width:560px){{.verdict-row,.rating-row{{flex-direction:column}}}}
</style>"""
# ── END NEW ──────────────────────────────────────────────────────────────────


# ── NEW: redirect page generator ─────────────────────────────────────────────
def generate_redirect_page(from_slug: str, to_url: str) -> str:
    """Generates a JS + meta-refresh redirect page for retired Sendinblue URLs."""
    display = from_slug.replace("-", " ").replace("/", " › ").title()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{display} | Redirecting…</title>
  <link rel="canonical" href="{to_url}">
  <meta http-equiv="refresh" content="0; url={to_url}">
  <script>window.location.replace("{to_url}");</script>
</head>
<body>
  <p>Sendinblue is now Brevo.
     <a href="{to_url}">Click here if you are not redirected.</a></p>
</body>
</html>"""
# ── END NEW ──────────────────────────────────────────────────────────────────


def load_entities(site_id):
    path = SITES_DIR / site_id / "data" / "entities.json"
    return json.loads(path.read_text(encoding="utf-8"))


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
    site_cfg = json.loads(config_path.read_text(encoding="utf-8"))
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

    # Build richer compare card data for homepage
    LOGO_PALETTE = [
        "#1F5C99","#2ECC71","#E74C3C","#9B59B6","#F39C12",
        "#1ABC9C","#E91E63","#3498DB","#FF5722","#607D8B",
        "#00BCD4","#8BC34A","#FF9800","#673AB7","#009688",
        "#795548","#F44336","#2196F3",
    ]
    CAT_COLORS = {
        "freemium":"#3498DB","paid":"#E74C3C",
        "flat-rate":"#9B59B6","revenue-share":"#F39C12",
    }
    CAT_ICONS = {"freemium":"📧","paid":"💼","flat-rate":"📬","revenue-share":"✍️"}

    # Assign a unique colour to each entity for its logo avatar
    for i, e in enumerate(entities):
        e["color"] = LOGO_PALETTE[i % len(LOGO_PALETTE)]

    rich_compares = []
    for idx, (a, b) in enumerate(list(__import__('itertools').combinations(entities, 2))[:12]):
        color = CAT_COLORS.get(a.get("pricing_model","freemium"), "#3498DB")
        rich_compares.append({
            "slug": f"{a['slug']}-vs-{b['slug']}",
            "slug_a": a["slug"], "slug_b": b["slug"],
            "tool_a": a["name"], "tool_b": b["name"],
            "init_a": a["name"][0].upper(),
            "init_b": b["name"][0].upper(),
            "color_a": a.get("color","#1F5C99"),
            "color_b": b.get("color","#2ECC71"),
            "color": color,
            "icon": CAT_ICONS.get(a.get("pricing_model","freemium"), "📧"),
            "label": a.get("pricing_model","freemium").replace("-"," ").title(),
            "cat": a.get("pricing_model","freemium"),
            "pricing_a": f"${a.get('paid_from_usd',0)}/mo",
            "pricing_b": f"${b.get('paid_from_usd',0)}/mo",
            "best_for": a.get("best_for","all users")[:40],
        })

    home_html = home_tmpl.render(
        site=site_cfg,
        entities=entities,
        featured_compares=rich_compares,
        compare_count=153,
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

    # ── Compare pages (both orderings so A-vs-B and B-vs-A both work) ──────────
    compare_tmpl = env.get_template("compare.html")
    compare_dir = content_dir / "compare"
    if compare_dir.exists():
        out_dir = dist_dir / "compare"
        out_dir.mkdir(exist_ok=True)
        for json_file in compare_dir.glob("*.json"):
            page_data = json.loads(json_file.read_text())
            slug = json_file.stem
            parts = slug.split("-vs-", 1)
            entity_a = entity_map.get(parts[0], {}) if len(parts) == 2 else {}
            entity_b = entity_map.get(parts[1], {}) if len(parts) == 2 else {}

            related = [
                {"slug": f"{entity_a.get('slug','')}-vs-{e['slug']}",
                 "label": f"{entity_a.get('name','')} vs {e['name']}"}
                for e in entities
                if e["slug"] not in (entity_a.get("slug"), entity_b.get("slug"))
            ][:4]

            page_data["schema_json"] = schema_faq(page_data.get("faq", []))

            # ── NEW: pre-generate comparison table once per file ─────────────
            table_html = generate_comparison_table(entity_a, entity_b, page_data)
            # ── END NEW ──────────────────────────────────────────────────────

            # ── NEW: compute canonical slug (alphabetical ordering) ──────────
            canonical_slug = get_canonical_slug(
                parts[0], parts[1] if len(parts) == 2 else parts[0]
            )
            # ── END NEW ──────────────────────────────────────────────────────

            # Build BOTH orderings: a-vs-b AND b-vs-a
            for s_a, s_b, ea, eb in [
                (parts[0], parts[1] if len(parts)==2 else "", entity_a, entity_b),
                (parts[1] if len(parts)==2 else "", parts[0], entity_b, entity_a),
            ]:
                rev_slug = f"{s_a}-vs-{s_b}"
                url_path = f"compare/{rev_slug}/"
                full_url = f"{site_cfg['base_url']}/{url_path}"

                # ── NEW: canonical URL always points to alphabetical ordering ─
                canonical_url = f"{site_cfg['base_url']}/compare/{canonical_slug}/"
                page_data["url_path"]     = url_path
                page_data["canonical_url"] = canonical_url           # ← NEW
                # ── END NEW ──────────────────────────────────────────────────

                html = compare_tmpl.render(
                    site=site_cfg, page=page_data,
                    entity_a=ea, entity_b=eb,
                    related_pages=related,
                    table_html=table_html,                            # ← NEW
                )
                page_out = out_dir / rev_slug
                page_out.mkdir(exist_ok=True)
                (page_out / "index.html").write_text(html, encoding="utf-8")
                sitemap_urls.append({"url": full_url, "priority": "0.9", "changefreq": "monthly"})
                page_count += 1

    # ── NEW: Sendinblue → Brevo redirect pages ───────────────────────────────
    # Generates a lightweight redirect at every retired Sendinblue URL.
    # Canonical tag on each redirect page transfers link equity to the Brevo page.
    redirect_count = 0
    for from_slug, to_path in SENDINBLUE_REDIRECTS.items():
        to_url = f"{site_cfg['base_url']}/{to_path}/"
        page_out = dist_dir / from_slug
        page_out.mkdir(parents=True, exist_ok=True)
        redirect_html = generate_redirect_page(from_slug, to_url)
        (page_out / "index.html").write_text(redirect_html, encoding="utf-8")
        redirect_count += 1
        # Note: redirect pages are intentionally excluded from sitemap
    print(f"  Redirects: {redirect_count} Sendinblue → Brevo pages generated")
    # ── END NEW ──────────────────────────────────────────────────────────────

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

    # ── Section index pages (built from entities, not content files) ─────────
    import itertools as _it

    base = site_cfg["base_url"]
    name = site_cfg["site_name"]

    def _nav():
        return (f"<header class='site-header'><div class='container'>"
                f"<a href='{base}/' class='logo'>Email Tool <span>Compare</span></a>"
                f"<nav><a href='{base}/compare/'>Compare Tools</a> "
                f"<a href='{base}/alternatives/'>Alternatives</a> "
                f"<a href='{base}/tools/'>All Tools</a></nav></div></header>")

    def _pg(title, h1, desc, body, canonical=None):       # ← NEW: canonical param
        canon_tag = f"<link rel='canonical' href='{canonical}'>" if canonical else ""  # ← NEW
        return (f"<!DOCTYPE html><html lang=en data-theme=light><head>"
                f"<meta charset=UTF-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                f"<title>{title} | {name}</title>"
                f"<meta name=description content='{desc}'>"
                f"{canon_tag}"                                        # ← NEW
                f"<link rel=stylesheet href='{base}/static/style.css'>"
                f"<script>(function(){{var t=localStorage.getItem('theme')||'light';"
                f"document.documentElement.setAttribute('data-theme',t);}})();</script>"
                f"</head><body>{_nav()}"
                f"<div class='page-wrap'><h1 class='page-h1'>{h1}</h1>"
                f"<p class='page-intro'>{desc}</p>{body}</div></body></html>")

    # Compare index
    (dist_dir / "compare").mkdir(exist_ok=True)
    clinks = "".join(
        f"<li><a href='{base}/compare/{a['slug']}-vs-{b['slug']}/'>{a['name']} vs {b['name']}</a></li>"
        for a, b in _it.combinations(entities, 2)
    )
    (dist_dir / "compare" / "index.html").write_text(
        _pg("All Comparisons", "All Email Tool Comparisons",
            f"Side-by-side comparisons across {len(entities)} email marketing platforms.",
            f"<ul style='columns:2;padding-left:1.5rem;line-height:2'>{clinks}</ul>",
            canonical=f"{base}/compare/"),                            # ← NEW
        encoding="utf-8")

    # Alternatives index
    (dist_dir / "alternatives").mkdir(exist_ok=True)
    alinks = "".join(
        f"<li><a href='{base}/alternatives/{e['slug']}-alternatives/'>Best {e['name']} Alternatives</a></li>"
        for e in entities
    )
    (dist_dir / "alternatives" / "index.html").write_text(
        _pg("All Alternatives", "Best Email Tool Alternatives",
            "Find the best alternative for every major email marketing platform.",
            f"<ul style='columns:2;padding-left:1.5rem;line-height:2'>{alinks}</ul>",
            canonical=f"{base}/alternatives/"),                       # ← NEW
        encoding="utf-8")

    # Tools index
    (dist_dir / "tools").mkdir(exist_ok=True)
    tlinks = "".join(
        f"<li><a href='{base}/tools/{e['slug']}/'>{e['name']} — {e['tagline']}</a></li>"
        for e in entities
    )
    (dist_dir / "tools" / "index.html").write_text(
        _pg("All Tools", "All 18 Email Marketing Tools Reviewed",
            f"Honest reviews of {len(entities)} email marketing platforms.",
            f"<ul style='padding-left:1.5rem;line-height:2'>{tlinks}</ul>",
            canonical=f"{base}/tools/"),                              # ← NEW
        encoding="utf-8")

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