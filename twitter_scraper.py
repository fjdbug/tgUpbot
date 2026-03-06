"""
Twitter/X scraper module.
Uses Apify's Twitter Scraper to extract profile metrics from public X accounts.
"""

import logging
from datetime import datetime

from apify_client import ApifyClient

import config
from scraper import AccountData

logger = logging.getLogger(__name__)

TWITTER_SCRAPER_ACTOR = "apidojo/twitter-user-scraper"


def scrape_twitter_account(username, label="", category=""):
    """
    Scrape profile metrics from a single X/Twitter account using Apify.

    Args:
        username: Twitter username (without @)
        label: Friendly label
        category: Account category

    Returns:
        AccountData with profile metrics
    """
    username = username.lstrip("@")

    try:
        client = ApifyClient(config.APIFY_API_TOKEN)

        logger.info("Scraping X account: @%s via Apify...", username)

        run_input = {
            "startUrls": ["https://x.com/" + username],
            "maxItems": 1,
        }

        run = client.actor(TWITTER_SCRAPER_ACTOR).call(run_input=run_input)

        items = list(
            client.dataset(run["defaultDatasetId"]).iterate_items()
        )

        if not items:
            logger.warning("  No results returned for @%s on X", username)
            return AccountData(
                username=username,
                label=label or username,
                category=category,
                scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error="No data returned for @%s on X" % username,
            )

        # Parse the first profile result
        profile = items[0]

        account_data = AccountData(
            username=username,
            label=label or username,
            category=category,
            followers=profile.get("followers", 0),
            following=profile.get("following", 0),
            total_likes=profile.get("favouritesCount", 0),
            total_videos=profile.get("statusesCount", 0),
            scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        logger.info(
            "  @%s (X): %s followers",
            username,
            "{:,}".format(account_data.followers),
        )
        return account_data

    except Exception as e:
        error_msg = "Failed to scrape @%s on X: %s: %s" % (username, type(e).__name__, e)
        logger.error("  %s", error_msg)
        return AccountData(
            username=username,
            label=label or username,
            category=category,
            scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            error=error_msg,
        )
