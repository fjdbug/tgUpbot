"""
Core TikTok scraper module.
Uses Apify's TikTok Profile Scraper to extract video metrics from public TikTok profiles.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime

from apify_client import ApifyClient

import config

logger = logging.getLogger(__name__)

# Apify Actor IDs for TikTok scraping
TIKTOK_SCRAPER_ACTOR = "clockworks/tiktok-scraper"


@dataclass
class VideoMetrics:
    """Represents metrics for a single TikTok video."""
    video_id: str = ""
    video_url: str = ""
    caption: str = ""
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    post_date: str = ""
    music: str = ""


@dataclass
class AccountData:
    """Represents scraped data for a single TikTok account."""
    username: str = ""
    label: str = ""
    followers: int = 0
    following: int = 0
    total_likes: int = 0
    total_videos: int = 0
    scraped_at: str = ""
    videos: list = field(default_factory=list)
    category: str = ""
    error: str = ""


def _parse_apify_results(items: list, username: str, label: str) -> AccountData:
    """
    Parse Apify scraper results into our AccountData format.

    Args:
        items: Raw items from Apify dataset
        username: TikTok username
        label: Friendly label

    Returns:
        Parsed AccountData
    """
    account_data = AccountData(
        username=username,
        label=label or username,
        scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    for item in items:
        # Extract profile-level stats from the first item's author info
        author_meta = item.get("authorMeta", {})
        if author_meta and not account_data.followers:
            account_data.followers = author_meta.get("fans", 0)
            account_data.following = author_meta.get("following", 0)
            account_data.total_likes = author_meta.get("heart", 0)
            account_data.total_videos = author_meta.get("video", 0)

        # Extract video metrics
        video_id = item.get("id", "")
        create_time = item.get("createTimeISO", "")
        if not create_time:
            ts = item.get("createTime", 0)
            if ts:
                try:
                    create_time = datetime.fromtimestamp(int(ts)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except (ValueError, OSError):
                    create_time = ""

        music_meta = item.get("musicMeta", {})

        metrics = VideoMetrics(
            video_id=str(video_id),
            video_url=item.get("webVideoUrl", "")
            or f"https://www.tiktok.com/@{username}/video/{video_id}",
            caption=item.get("text", ""),
            views=item.get("playCount", 0),
            likes=item.get("diggCount", 0),
            comments=item.get("commentCount", 0),
            shares=item.get("shareCount", 0),
            post_date=create_time,
            music=music_meta.get("musicName", ""),
        )
        account_data.videos.append(metrics)

    return account_data


def scrape_account(
    username: str,
    label: str = "",
    category: str = "",
    max_videos: int = None,
) -> AccountData:
    """
    Scrape video metrics from a single TikTok account using Apify.

    Args:
        username: TikTok username (without @)
        label: Friendly label for the account
        max_videos: Max number of videos to fetch (default from config)

    Returns:
        AccountData with video metrics
    """
    if max_videos is None:
        max_videos = config.MAX_VIDEOS_PER_ACCOUNT

    # Remove @ prefix if present
    username = username.lstrip("@")

    try:
        client = ApifyClient(config.APIFY_API_TOKEN)

        logger.info(f"Scraping account: @{username} via Apify...")

        # Run the TikTok scraper Actor
        run_input = {
            "profiles": [f"https://www.tiktok.com/@{username}"],
            "resultsPerPage": max_videos,
            "shouldDownloadCovers": False,
            "shouldDownloadVideos": False,
            "shouldDownloadSubtitles": False,
        }

        run = client.actor(TIKTOK_SCRAPER_ACTOR).call(run_input=run_input)

        # Fetch results from the dataset
        items = list(
            client.dataset(run["defaultDatasetId"]).iterate_items()
        )

        if not items:
            logger.warning(f"  ⚠ No results returned for @{username}")
            return AccountData(
                username=username,
                label=label or username,
                category=category,
                scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error=f"No data returned for @{username}",
            )

        account_data = _parse_apify_results(items, username, label)
        account_data.category = category

        logger.info(
            f"  ✓ @{username}: {len(account_data.videos)} videos, "
            f"{account_data.followers:,} followers"
        )
        return account_data

    except Exception as e:
        error_msg = f"Failed to scrape @{username}: {type(e).__name__}: {e}"
        logger.error(f"  ✗ {error_msg}")
        return AccountData(
            username=username,
            label=label or username,
            category=category,
            scraped_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            error=error_msg,
        )


def scrape_all_accounts() -> list[AccountData]:
    """
    Scrape all accounts defined in accounts.json.
    Adds small delays between accounts to be respectful to the API.

    Returns:
        List of AccountData for all accounts
    """
    accounts = config.load_accounts()
    results = []

    logger.info(f"Starting scrape of {len(accounts)} accounts...")
    start_time = datetime.now()

    for i, account in enumerate(accounts):
        username = account.get("username", "")
        label = account.get("label", "")
        category = account.get("category", "")

        if not username:
            logger.warning(f"Skipping account at index {i}: no username provided")
            continue

        platform = account.get("platform", "tiktok")

        if platform == "twitter":
            from twitter_scraper import scrape_twitter_account
            data = scrape_twitter_account(username, label, category)
        else:
            data = scrape_account(username, label, category)
        results.append(data)

        # Small delay between API calls
        if i < len(accounts) - 1:
            delay = random.uniform(2, 5)
            logger.info(f"  Waiting {delay:.1f}s before next account...")
            import time
            time.sleep(delay)

    elapsed = (datetime.now() - start_time).total_seconds()
    success = sum(1 for r in results if not r.error)
    failed = sum(1 for r in results if r.error)

    logger.info(
        f"Scrape complete: {success} succeeded, {failed} failed "
        f"({elapsed:.1f}s total)"
    )

    return results


def results_to_dicts(results: list[AccountData]) -> list[dict]:
    """Convert AccountData results to a list of dicts (for JSON/Sheets export)."""
    output = []
    for account in results:
        for video in account.videos:
            row = {
                "scraped_at": account.scraped_at,
                "account": account.username,
                "label": account.label,
                "followers": account.followers,
                "video_url": video.video_url,
                "caption": video.caption[:100],
                "views": video.views,
                "likes": video.likes,
                "comments": video.comments,
                "shares": video.shares,
                "post_date": video.post_date,
                "music": video.music,
            }
            output.append(row)
    return output


# --- Quick test ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "tiktok"
    result = scrape_account(target)

    if result.error:
        print(f"\n❌ Error: {result.error}")
    else:
        print(f"\n✅ @{result.username} ({result.label})")
        print(f"   Followers: {result.followers:,}")
        print(f"   Total Likes: {result.total_likes:,}")
        print(f"   Videos scraped: {len(result.videos)}")
        for v in result.videos[:5]:
            print(
                f"   - {v.views:>10,} views | "
                f"{v.likes:>8,} likes | "
                f"{v.comments:>6,} comments | "
                f"{v.caption[:50]}"
            )
