# aiopentec PSEO Engine

**Programmatic SEO + AI content pipeline → GitHub Pages → $10k/month**

Zero fixed costs. Fully automated. Runs on a cron schedule without your involvement.

---

## How it works

```
entities.json → generate.py (Claude API) → content/*.json → build.py (Jinja2) → dist/*.html → GitHub Pages
```

Each week, GitHub Actions:
1. Reads your entity list (tools, products, companies — whatever your niche is)
2. Calls Claude Haiku to generate structured page content as JSON
3. Renders static HTML via Jinja2 templates
4. Deploys to GitHub Pages automatically
5. Commits new content back to the repo

**Cost:** ~$0.05 per 50-page generation run. Hosting is free. CI/CD is free.

---

## Quick start

### Prerequisites
- Python 3.12+
- GitHub account (and the `gh` CLI installed + authenticated)
- Anthropic API key → [console.anthropic.com](https://console.anthropic.com)

### 1. Clone and install

```bash
git clone https://github.com/aiopentec/email-tool-compare
cd email-tool-compare
pip install -r requirements.txt
```

### 2. Test locally (no API key needed)

```bash
# Generate content using demo mode (template-based, no API calls)
python scripts/generate.py --site email-tools --limit 20 --demo

# Build the static site
python scripts/build.py --site email-tools

# Preview in browser
open dist/email-tools/index.html
```

### 3. Deploy to GitHub

```bash
export ANTHROPIC_API_KEY=sk-ant-...
chmod +x setup_github.sh
./setup_github.sh
```

This script:
- Creates a public GitHub repo under your org
- Pushes all code
- Sets `ANTHROPIC_API_KEY` as a repo secret
- Enables GitHub Pages on the `gh-pages` branch
- Triggers the first live content generation run

Your site will be live at `https://aiopentec.github.io/email-tool-compare` within ~10 minutes.

---

## File structure

```
pseo-engine/
├── .github/
│   └── workflows/
│       └── content_engine.yml    ← cron automation (runs every Monday)
├── scripts/
│   ├── generate.py               ← AI content generation pipeline
│   ├── build.py                  ← static site generator
│   └── new_site.py               ← scaffold a new niche site
├── sites/
│   └── email-tools/
│       ├── config.json           ← site config (name, URL, niche)
│       └── data/
│           └── entities.json     ← your entity list (tools, products, etc.)
├── templates/
│   ├── base.html                 ← shared layout with SEO meta, schema.org
│   ├── home.html                 ← homepage template
│   ├── tool.html                 ← individual tool review page
│   ├── compare.html              ← X vs Y comparison page
│   └── alternatives.html        ← "Best X alternatives" page
├── static/
│   └── style.css                 ← production CSS
├── content/                      ← auto-generated JSON (committed to repo)
│   └── email-tools/
│       ├── tools/
│       ├── compare/
│       └── alternatives/
└── dist/                         ← built HTML (deployed to gh-pages)
    └── email-tools/
```

---

## Adding a new site

```bash
python scripts/new_site.py \
  --id "saas-tools" \
  --name "SaaS Tool Compare" \
  --description "Unbiased comparisons for SaaS tools" \
  --base-url "https://aiopentec.github.io/saas-tool-compare" \
  --niche "SaaS productivity tools" \
  --audience "startup founders and product managers"
```

Then:
1. Edit `sites/saas-tools/data/entities.json` — add 15–30 real tools with attributes
2. Test: `python scripts/generate.py --site saas-tools --limit 20 --demo`
3. Build: `python scripts/build.py --site saas-tools`
4. Add `saas-tools` to the matrix in `.github/workflows/content_engine.yml`
5. Create a new GitHub repo and run `./setup_github.sh` with the updated config

---

## Generating content with the real API

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Generate 50 new pages (tool + alternatives + compare, in that priority)
python scripts/generate.py --site email-tools --limit 50

# Generate only compare pages
python scripts/generate.py --site email-tools --limit 30 --type compare

# Generate only tool review pages
python scripts/generate.py --site email-tools --limit 20 --type tool
```

The pipeline is **idempotent** — already-generated pages are skipped automatically.
Re-running is safe. Failed runs can be retried without duplicating content.

**Cost reference (Claude Haiku):**
| Pages | Approx. cost |
|-------|-------------|
| 50    | ~$0.05      |
| 200   | ~$0.20      |
| 1,000 | ~$1.00      |
| 5,000 | ~$5.00      |

---

## Monetization setup

### 1. Display ads (Ezoic / Mediavine)

Once you hit **10,000 sessions/month** → apply to [Ezoic](https://www.ezoic.com)
Once you hit **50,000 sessions/month** → apply to [Mediavine](https://mediavine.com)

Add the ad script to `templates/base.html` in the `<head>` section.

### 2. Affiliate links

Replace the `href="#"` placeholders in `templates/compare.html` and `templates/tool.html`
with your real affiliate links. Most email marketing tools pay 20–30% recurring.

Good programs for this niche:
- ConvertKit: 30% recurring for 24 months
- Beehiiv: 50% for first year
- Flodesk: 50% recurring
- MailerLite: 30% recurring
- GetResponse: 33% recurring or $100 flat

### 3. Info product embed

Add a Gumroad or Payhip embed widget to the base template or a dedicated landing page.
A `$19 Email Tool Selector Kit` or `$29 Email Marketing Prompt Pack` converts well
against comparison traffic.

### 4. GA4 and Google Search Console

In `sites/email-tools/config.json`:
```json
{
  "ga4_id": "G-XXXXXXXXXX",
  "gsc_verification": "your-verification-code"
}
```

Submit your sitemap at: `https://aiopentec.github.io/email-tool-compare/sitemap.xml`

---

## Scaling the portfolio

The workflow matrix runs one job per site in parallel — add sites freely:

```yaml
# .github/workflows/content_engine.yml
strategy:
  matrix:
    site: [email-tools, saas-tools, project-management-tools, ai-writing-tools]
```

Each site runs independently. One failing doesn't affect the others.

**Target portfolio by month 12:**
```
Month 1-2:   email-tools + saas-tools
Month 3-4:   + project-management-tools + ai-writing-tools
Month 7-9:   + crm-tools + video-tools
Month 10-12: + developer-tools + hr-tools
```

---

## Page math

With 18 entities:
- Tool review pages:       18
- Alternatives pages:      18
- Compare pages (n×n-1/2): 153
- **Total pages:**         189

With 40 entities:
- Tool reviews:    40
- Alternatives:    40
- Compares:        780
- **Total:**       860

At 80 avg monthly visits per ranking page → **860 pages × 80 visits = 68,800 sessions/month** → Mediavine territory.

---

## Cron schedule

The workflow runs every Monday at 03:00 UTC. Change in `content_engine.yml`:

```yaml
on:
  schedule:
    - cron: '0 3 * * 1'   # Monday 03:00 UTC
```

Manual trigger anytime via GitHub Actions tab → "Run workflow".

---

## License

MIT — build freely, monetize freely, fork freely.

Built by [aiopentec](https://github.com/aiopentec) using the quiet product machine model.
