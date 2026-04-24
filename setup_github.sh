#!/usr/bin/env bash
# setup_github.sh — One-command GitHub repo setup for aiopentec PSEO engine
#
# Prerequisites:
#   brew install gh   (macOS)  or   apt install gh  (Linux)
#   gh auth login
#   export ANTHROPIC_API_KEY=sk-ant-...
#
# Usage:
#   chmod +x setup_github.sh
#   ./setup_github.sh

set -e

REPO_NAME="email-tool-compare"
ORG="aiopentec"
SITE_ID="email-tools"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   aiopentec PSEO Engine — GitHub Setup           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Check prerequisites ─────────────────────────────────────────────────────
if ! command -v gh &> /dev/null; then
  echo "✗ GitHub CLI (gh) not found."
  echo "  Install: https://cli.github.com"
  exit 1
fi

if ! gh auth status &> /dev/null; then
  echo "✗ Not authenticated with GitHub CLI."
  echo "  Run: gh auth login"
  exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "✗ ANTHROPIC_API_KEY is not set."
  echo "  Run: export ANTHROPIC_API_KEY=sk-ant-..."
  exit 1
fi

echo "✓ GitHub CLI authenticated"
echo "✓ ANTHROPIC_API_KEY present"
echo ""

# ── 2. Create GitHub repo ──────────────────────────────────────────────────────
echo "→ Creating GitHub repo: $ORG/$REPO_NAME ..."

if gh repo view "$ORG/$REPO_NAME" &> /dev/null; then
  echo "  Repo already exists — skipping creation"
else
  gh repo create "$ORG/$REPO_NAME" \
    --public \
    --description "Email marketing tool comparisons — built with the aiopentec PSEO engine" \
    --homepage "https://$ORG.github.io/$REPO_NAME"
  echo "✓ Repo created"
fi

# ── 3. Init git and push ───────────────────────────────────────────────────────
echo ""
echo "→ Pushing code to GitHub ..."

if [ ! -d ".git" ]; then
  git init
  git branch -M main
fi

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$ORG/$REPO_NAME.git"
git add -A
git commit -m "feat: initial PSEO engine setup — $(date +%Y-%m-%d)" 2>/dev/null || echo "  Nothing new to commit"
git push -u origin main --force
echo "✓ Code pushed"

# ── 4. Set ANTHROPIC_API_KEY secret ───────────────────────────────────────────
echo ""
echo "→ Setting ANTHROPIC_API_KEY secret ..."
echo "$ANTHROPIC_API_KEY" | gh secret set ANTHROPIC_API_KEY --repo "$ORG/$REPO_NAME"
echo "✓ Secret set"

# ── 5. Enable GitHub Pages ────────────────────────────────────────────────────
echo ""
echo "→ Enabling GitHub Pages (gh-pages branch) ..."
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  "/repos/$ORG/$REPO_NAME/pages" \
  -f source='{"branch":"gh-pages","path":"/"}' \
  2>/dev/null && echo "✓ Pages enabled" || echo "  Pages may already be enabled — continuing"

# ── 6. Run first content generation ──────────────────────────────────────────
echo ""
echo "→ Triggering first workflow run ..."
gh workflow run content_engine.yml \
  --repo "$ORG/$REPO_NAME" \
  -f site="$SITE_ID" \
  -f limit="50" \
  -f demo="false"
echo "✓ Workflow triggered"

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✓ Setup complete!                                    ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Repo:     https://github.com/$ORG/$REPO_NAME"
echo "║  Site:     https://$ORG.github.io/$REPO_NAME"
echo "║  Actions:  https://github.com/$ORG/$REPO_NAME/actions"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Next steps:                                          ║"
echo "║  1. Wait ~10 min for first workflow to complete       ║"
echo "║  2. Submit sitemap to Google Search Console:          ║"
echo "║     https://$ORG.github.io/$REPO_NAME/sitemap.xml"
echo "║  3. Add a custom domain in repo Settings > Pages      ║"
echo "║  4. Add Ezoic script to templates/base.html           ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
