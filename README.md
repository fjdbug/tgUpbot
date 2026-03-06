# TikTok Video Scraper 📊

Scrape video metrics (views, likes, comments, shares) from multiple TikTok accounts with automated scheduling and notifications.

## Features

- �� Scrape video metrics from up to 20+ TikTok accounts
- 📱 Telegram notifications with formatted reports
- 📄 Google Sheets export (auto-creates monthly worksheets)
- ⏰ Configurable scheduling (default: 2x daily)
- 🔒 Reliable scraping via Apify (handles anti-bot for you)

## Quick Start

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Configure

Edit `.env` with your credentials:

- **APIFY_API_TOKEN** — Your Apify API token (from [apify.com](https://apify.com) → Settings → Integrations)
- **TELEGRAM_BOT_TOKEN** — Get from [@BotFather](https://t.me/BotFather) (optional)
- **TELEGRAM_CHAT_ID** — Your chat/channel ID (optional)
- **SCRAPE_TIMES** — Comma-separated HH:MM times (e.g., `09:00,18:00`)

### 3. Add your accounts

Edit `accounts.json` with your TikTok accounts:

```json
{
  "accounts": [
    { "username": "tiktok_user_1", "label": "Brand A" },
    { "username": "tiktok_user_2", "label": "Brand B" }
  ]
}
```

### 4. Run

**Immediate scrape (one-time):**
```bash
python3 scheduler.py --now
```

**Scheduled mode (runs at configured times):**
```bash
python3 scheduler.py
```

**Test a single account:**
```bash
python3 scraper.py username_here
```

**Test Telegram connection:**
```bash
python3 notifier.py
```

## Google Sheets Setup (Optional)

1. Create a Google Cloud service account and download `credentials.json`
2. Create a Google Sheet named "TikTok Metrics"
3. Share the sheet with the service account email
4. Set `GOOGLE_SHEETS_CREDS_PATH=credentials.json` in `.env`

## Files

| File | Description |
|------|-------------|
| `scheduler.py` | Main entry point with scheduling |
| `scraper.py` | Core scraping logic (Apify) |
| `notifier.py` | Telegram notification sender |
| `sheets_export.py` | Google Sheets export |
| `config.py` | Configuration loader |
| `accounts.json` | TikTok accounts to track |
