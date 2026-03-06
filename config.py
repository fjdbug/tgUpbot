"""
Configuration loader for TikTok Scraper.
Reads settings from .env file and accounts from accounts.json.
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent

# Apify settings
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")

# Telegram settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Google Sheets settings
GOOGLE_SHEETS_CREDS_PATH = os.getenv("GOOGLE_SHEETS_CREDS_PATH", "credentials.json")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "TikTok Metrics")

# Scraping settings
SCRAPE_TIMES = os.getenv("SCRAPE_TIMES", "09:00,18:00").split(",")
MAX_VIDEOS_PER_ACCOUNT = int(os.getenv("MAX_VIDEOS_PER_ACCOUNT", "10"))

# Delay between scraping each account (seconds)
MIN_DELAY = 2
MAX_DELAY = 5


def load_accounts() -> list[dict]:
    """Load TikTok accounts from accounts.json."""
    accounts_path = BASE_DIR / "accounts.json"
    if not accounts_path.exists():
        raise FileNotFoundError(
            f"accounts.json not found at {accounts_path}. "
            "Copy accounts.json.example and add your accounts."
        )
    with open(accounts_path, "r") as f:
        data = json.load(f)
    return data.get("accounts", [])
