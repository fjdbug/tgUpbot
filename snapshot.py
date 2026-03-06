"""
Snapshot module for tracking previous scrape results.
Saves daily snapshots so we can compare against the previous day.
"""

import glob
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

import config

logger = logging.getLogger(__name__)

SNAPSHOTS_DIR = config.BASE_DIR / "snapshots"


def save_snapshot(results):
    """
    Save current scrape results as a daily snapshot.
    Saves to snapshots/YYYY-MM-DD.json, overwriting if run multiple times per day.
    """
    SNAPSHOTS_DIR.mkdir(exist_ok=True)

    accounts = {}
    for account in results:
        if account.error:
            continue

        total_views = sum(v.views for v in account.videos)
        total_likes_videos = sum(v.likes for v in account.videos)

        accounts[account.username] = {
            "label": account.label,
            "followers": account.followers,
            "total_likes": account.total_likes,
            "total_views": total_views,
            "total_likes_videos": total_likes_videos,
        }

    today = datetime.now().strftime("%Y-%m-%d")
    snapshot = {
        "date": today,
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "accounts": accounts,
    }

    filepath = SNAPSHOTS_DIR / (today + ".json")
    try:
        with open(filepath, "w") as f:
            json.dump(snapshot, f, indent=2)
        logger.info("Snapshot saved to %s", filepath.name)
    except Exception as e:
        logger.error("Failed to save snapshot: %s", e)


def load_snapshot():
    """
    Load the most recent snapshot from a previous day.
    Skips today's snapshot so we always compare against an earlier date.

    Returns:
        Snapshot dict or None if no previous snapshot exists.
    """
    if not SNAPSHOTS_DIR.exists():
        logger.info("No snapshots directory found (first run)")
        return None

    today = datetime.now().strftime("%Y-%m-%d")

    # List all snapshot files, sorted descending
    files = sorted(SNAPSHOTS_DIR.glob("*.json"), reverse=True)

    for f in files:
        date_str = f.stem  # e.g. "2026-03-03"
        if date_str < today:
            try:
                with open(f, "r") as fh:
                    snapshot = json.load(fh)
                logger.info("Loaded snapshot from %s", date_str)
                return snapshot
            except Exception as e:
                logger.error("Failed to load snapshot %s: %s", f.name, e)
                continue

    logger.info("No previous-day snapshot found (first day)")
    return None
