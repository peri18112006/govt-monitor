# Govt Site Monitor — AI Agent System

Multiple government websites-a periodically check pannitu, edhavadhu update/news varum bothu,
AI (Mistral) use panni news-style summary generate panni, unga Gmail-ku automatic-ah mail
anupura always-on FastAPI service.

## Architecture

```
FastAPI app (always-on)
  └── APScheduler background job (runs every N minutes)
        └── For each site in data/sites.json:
              1. Scrape page (requests + BeautifulSoup)
              2. Compare content hash with last saved hash (SQLite)
              3. If changed → Mistral AI summarizes it news-style
              4. Send email via Gmail SMTP
              5. Log the alert in SQLite
```

## 1. Setup (Windows PowerShell)

```powershell
# Extract the zip, then cd into the folder
cd govt-monitor

# Create virtual environment
python -m venv venv

# Activate it (PowerShell-specific)
.\venv\Scripts\Activate.ps1

# If activation is blocked by execution policy, run this once:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -r requirements.txt
```

## 2. Configure `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Fill in:
- `MISTRAL_API_KEY` — your Mistral API key (same one from your RAG chatbot project)
- `GMAIL_ADDRESS` — your Gmail address
- `GMAIL_APP_PASSWORD` — **not your normal password**. Generate one at:
  Google Account → Security → 2-Step Verification → App Passwords
- `MAIL_TO` — where alerts should be sent (can be same as GMAIL_ADDRESS)
- `CHECK_INTERVAL_MINUTES` — how often to check (default 60)

## 3. Sites already configured

`data/sites.json` already has your 6 sites wired in:

| Site | Renderer | Notes |
|---|---|---|
| ICAI - Announcements | `requests` | Server-rendered list, works directly |
| Income Tax India - Circulars | `selenium` | JS-rendered (Liferay portal) — table loads via AJAX |
| CBIC - Tax Information Portal | `selenium` | JS-rendered (Angular SPA) — content loads via AJAX |
| NFRA - What's New | `requests` | Server-rendered ticker |
| IFRS - Open for Comment | `requests` | Server-rendered list, works directly |
| IFRS Foundation - News | `selenium` | JS-rendered — table is empty until AJAX loads |

**Each entry looks like:**
```json
{
  "name": "ICAI - Announcements",
  "url": "https://www.icai.org/category/announcements",
  "selector": "main, #main-content, .region-content",
  "renderer": "requests",
  "enabled": true
}
```

- `renderer: "requests"` → fast, plain HTTP fetch (for server-rendered pages)
- `renderer: "selenium"` → opens a headless Edge browser, waits 5 seconds for
  JS/AJAX to finish loading, then reads the page (needed for the 3 sites above)

**Important — the `selector` values are my best-effort guess** based on typical
page structure. Since these are React/Angular/Liferay-based government portals,
the exact CSS class names can only be confirmed by inspecting the live page in
your browser. Andha step pannunga:

1. Open the site in Chrome/Edge
2. Right-click directly on the announcements/news list → **Inspect**
3. Find the smallest wrapping `<div>`/`<table>` that contains just that list
   (not the whole page, not just the header)
4. Note its class or id (e.g. `.notice-board`, `#news-table`)
5. Update the `selector` field for that site in `data/sites.json`

If the current broad selector (`main, #main-content, ...`) already works fine
without noise, you don't need to change anything — leave it as is.

## 4. Selenium / Edge WebDriver setup (for JS-heavy sites)

Same pattern as your Feasibility form automation project — using **Edge** instead
of Chrome avoids corporate ChromeDriver policy blocks.

```powershell
# Download msedgedriver matching your installed Edge version from:
# https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/

# Check your Edge version:
(Get-Item (Get-Command msedge).Path).VersionInfo.ProductVersion

# Place msedgedriver.exe somewhere on PATH, e.g.:
# C:\WebDrivers\msedgedriver.exe
# Then add that folder to your PATH environment variable
```

Test it works:
```powershell
python -c "from app.scraper import fetch_page_text_selenium; print(fetch_page_text_selenium('https://www.ifrs.org/news-and-events/news/', 'main')[:300])"
```

If this errors with "msedgedriver not found", the PATH isn't set correctly —
same fix as your earlier LiveKit/Selenium PATH issues (add the folder, restart
PowerShell).

## 5. Configure sites to monitor (adding more later)

To add another site, append to `data/sites.json`:

```json
{
  "name": "GST Portal - Notifications",
  "url": "https://example.gov.in/notifications",
  "selector": ".notification-list",
  "renderer": "requests",
  "enabled": true
}
```

Set `"enabled": true` only for sites you actually want monitored. If unsure
whether a site needs `selenium`, try `requests` first — if the scraped text
looks empty or missing the actual list, switch to `selenium`.

## 6. Run the server

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

(`debug=False` equivalent — this is production-style run, no `--reload` flag, so it won't
restart mid-scrape.)

Server starts, DB auto-creates at `data/monitor.db`, scheduler starts in background.

## 7. API Endpoints

| Method | Endpoint       | What it does                                  |
|--------|----------------|------------------------------------------------|
| GET    | `/health`      | Health check                                    |
| GET    | `/sites`       | List currently monitored sites                  |
| POST   | `/sites`       | Add a new site to monitor (JSON body)           |
| GET    | `/alerts`      | View recent detected updates + whether emailed  |
| POST   | `/check-now`   | Trigger an immediate check (don't wait for timer)|

Test it:
```powershell
# Trigger an immediate check
Invoke-RestMethod -Uri http://localhost:8000/check-now -Method POST

# View recent alerts
Invoke-RestMethod -Uri http://localhost:8000/alerts
```

## Sample email you'll receive

```
Subject: 🔔 ICAI - Announcements — Exposure Draft - Guidance Note on Tax Audit...

New update(s) detected on: ICAI - Announcements
Page monitored: https://www.icai.org/category/announcements

============================================================

1. Exposure Draft - Guidance Note on Tax Audit under section 44AB - (09-07-2026)
   What this means: A new exposure draft on tax audit guidance has been
   published for public comment.
   Link: https://www.icai.org/post/icai-dtc-exp-draft-09072026

============================================================
This is an automated alert from your Govt Site Monitor.
```

**How this works under the hood:** every check, the scraper pulls the current
list of item titles + their direct links from the monitored section. It compares
this against the titles it saw last time (stored in SQLite) — any title that's
new gets included in the email, with its own specific link (not just the site's
homepage link) and a short AI-written one-line explanation. If multiple items
appear in the same check cycle, they're all bundled into a single email.

## Important notes

- **First check per site = baseline only.** No email is sent on the very first check
  for a site — it just saves the initial snapshot. From the 2nd check onwards, if
  content changed, you'll get an email.
- **robots.txt / ToS**: Check each government site's `robots.txt` and terms before
  scraping. Some portals explicitly disallow automated access. This tool is meant for
  personal monitoring at low frequency (e.g. hourly), not aggressive polling.
- **CAPTCHA/login-protected portals** (GST filing dashboard, MCA login area, etc.)
  won't work with this — only public, no-login pages.
- **Full-page hashing** (selector `"body"`) can cause false positives if the site has
  a visitor counter, rotating banner, or "last updated" timestamp anywhere on the page.
  Narrow selector-a use pannuna, adhu correct-ah irukum.
- To run this permanently in the background on Windows without keeping a terminal
  open, you can wrap the uvicorn command in a scheduled Task (Task Scheduler → trigger
  "At startup") or use `nssm` to run it as a Windows service.

## 8. Run this 24/7 for free, even when your PC is off (GitHub Actions)

This is the recommended setup if you want checks to happen automatically without
keeping your PC on or a terminal window open. GitHub Actions runs the check on
a schedule, on GitHub's own servers, completely free.

### Step 1 — Push this project to a GitHub repo

```powershell
cd govt-monitor
git init
git add .
git commit -m "Initial commit - govt site monitor"
```

Create a new repo on github.com (can be **private** — recommended, since it'll
contain your monitored site list), then:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/govt-monitor.git
git branch -M main
git push -u origin main
```

**Important:** Do NOT commit your real `.env` file — `.gitignore` already
excludes it. Secrets go into GitHub Secrets instead (next step).

### Step 2 — Add your secrets to GitHub

On your repo page: **Settings → Secrets and variables → Actions → New repository secret**

Add these 4 secrets one by one:
| Name | Value |
|---|---|
| `MISTRAL_API_KEY` | your Mistral API key |
| `GMAIL_ADDRESS` | your Gmail address |
| `GMAIL_APP_PASSWORD` | your 16-character Gmail App Password |
| `MAIL_TO` | where you want alerts sent |

### Step 3 — Enable and test the workflow

The workflow file is already included at `.github/workflows/check-sites.yml`.
It's scheduled to run **every 3 hours** by default — edit the `cron:` line in
that file to change frequency (e.g. `0 * * * *` for every hour).

To test it immediately instead of waiting:
1. Go to your repo → **Actions** tab
2. Click **"Govt Site Monitor"** on the left
3. Click **"Run workflow"** → **Run workflow** button

Watch it run — first run saves the baseline (no email). Run it again (or wait
for the next scheduled run) to see real new-item detection + emails.

### How state persists between runs

GitHub Actions runners are temporary — nothing survives between runs by default.
To fix this, the workflow **commits `data/monitor.db` back to your repo** after
every run, so the next run picks up exactly where the last one left off. You'll
see small automated commits appear in your repo history — that's expected and
normal.

### Notes for the cloud version

- Uses **Chrome** (not Edge) for the JS-heavy sites, since Chrome comes
  preinstalled on GitHub's Ubuntu runners — this is handled automatically via
  the `SELENIUM_BROWSER: chrome` setting in the workflow, no action needed from you.
- Free tier limits: GitHub gives 2,000 free Action minutes/month for private
  repos (unlimited for public repos). Checking 6 sites every 3 hours uses a
  small fraction of that.
- You can still run everything locally too (Section 6) for testing — both
  methods use the exact same code.

## Extending this (matches your other agent projects)

- Swap `requests`+`BeautifulSoup` for Selenium (like your Feasibility form automation)
  if a site needs JS rendering / login.
- Add a Researcher→Writer→Reviewer pipeline (like Wire Desk) before emailing, for
  higher-quality summaries.
- Add Telegram/Slack webhook alongside email in `app/mailer.py`.
