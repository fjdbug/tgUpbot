"""
Main entry point for the TikTok Scraper.
Orchestrates scraping, notifications, and exports on a schedule.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from scraper import scrape_all_accounts
from notifier import send_report
from sheets_export import export_to_sheets
from snapshot import load_snapshot, save_snapshot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("tiktok_scraper")


def run_scrape_job():
    """Execute a full scrape cycle: load snapshot → scrape → notify → save snapshot → export."""
    logger.info("=" * 50)
    logger.info("Starting scheduled scrape job...")
    logger.info("=" * 50)

    try:
        # 0. Load previous snapshot for delta calculation
        prev_snapshot = load_snapshot()

        # 1. Scrape all accounts (synchronous with Apify)
        results = scrape_all_accounts()

        if not results:
            logger.warning("No results to report")
            return

        # 2. Send Telegram notification with deltas (async)
        if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            asyncio.run(send_report(results, prev_snapshot))
        else:
            logger.info("Telegram not configured, skipping notification")

        # 3. Save current results as new snapshot
        save_snapshot(results)

        # 4. Export to Google Sheets
        try:
            export_to_sheets(results)
        except Exception as e:
            logger.warning(f"Google Sheets export skipped: {e}")

        # Summary
        success = sum(1 for r in results if not r.error)
        total_videos = sum(len(r.videos) for r in results)
        logger.info(
            f"Job complete: {success}/{len(results)} accounts, "
            f"{total_videos} videos scraped"
        )

    except Exception as e:
        logger.error(f"Scrape job failed: {e}", exc_info=True)


def start_scheduler():
    """Start the scheduler with configured scrape times."""
    scheduler = BlockingScheduler()

    # Schedule jobs for each configured time
    for time_str in config.SCRAPE_TIMES:
        time_str = time_str.strip()
        try:
            hour, minute = time_str.split(":")
            trigger = CronTrigger(hour=int(hour), minute=int(minute))
            scheduler.add_job(
                run_scrape_job,
                trigger=trigger,
                id=f"scrape_{time_str}",
                name=f"TikTok Scrape at {time_str}",
                misfire_grace_time=300,
            )
            logger.info(f"Scheduled scrape at {time_str}")
        except ValueError:
            logger.error(f"Invalid time format: '{time_str}'. Use HH:MM format.")

    return scheduler


def main():
    """Main entry point."""
    logger.info("🎬 TikTok Scraper starting up...")

    # Validate Apify token
    if not config.APIFY_API_TOKEN:
        logger.error("APIFY_API_TOKEN not set in .env!")
        sys.exit(1)

    # Load and validate accounts
    try:
        accounts = config.load_accounts()
        logger.info(f"Loaded {len(accounts)} accounts from accounts.json")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # Check what's configured
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        logger.info("✓ Telegram notifications enabled")
    else:
        logger.warning("✗ Telegram not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)")

    logger.info(f"✓ Apify API configured")

    # Check for --now flag to run immediately
    if "--now" in sys.argv:
        logger.info("Running immediate scrape (--now flag)...")
        run_scrape_job()
        return

    # Start scheduler
    scheduler = start_scheduler()

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    logger.info(f"Next scrape times: {', '.join(config.SCRAPE_TIMES)}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down... Goodbye! 👋")


if __name__ == "__main__":
    main()
