"""Telegram notification module.
Sends a Daily Performance Summary with delta tracking to a Telegram chat/channel.
"""

import logging
from collections import OrderedDict
from datetime import datetime
from typing import Optional
from telegram import Bot
from telegram.constants import ParseMode

import config

logger = logging.getLogger(__name__)


def _format_number(n: int) -> str:
    """Format large numbers with comma separators."""
    return f"{n:,}"


def _format_delta(n: int) -> str:
    """Format a delta number with +/- prefix."""
    if n > 0:
        return f"+{n:,}"
    elif n < 0:
        return f"{n:,}"
    return "0"


def _format_date_short(date_str: str) -> str:
    """Convert '2026-03-03' to 'Mar 3'."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b %-d")
    except (ValueError, TypeError):
        return date_str or "N/A"


def _compute_deltas(results: list, prev_snapshot: Optional[dict]) -> list[dict]:
    """
    Compute per-account deltas between current results and previous snapshot.

    Returns a list of dicts sorted by total followers (descending):
        {
            "label": str,
            "followers": int,
            "d_followers": int,
            "d_views": int,
            "d_likes": int,
        }
    """
    prev_accounts = prev_snapshot.get("accounts", {}) if prev_snapshot else {}
    rows = []

    for account in results:
        if account.error:
            continue

        total_views = sum(v.views for v in account.videos)
        total_likes_videos = sum(v.likes for v in account.videos)

        prev = prev_accounts.get(account.username, {})
        prev_followers = prev.get("followers", account.followers)
        prev_views = prev.get("total_views", total_views)
        prev_likes = prev.get("total_likes_videos", total_likes_videos)

        rows.append({
            "label": account.label or account.username,
            "username": account.username,
            "category": getattr(account, "category", "") or "Other",
            "followers": account.followers,
            "d_followers": account.followers - prev_followers,
            "d_views": total_views - prev_views,
            "d_likes": total_likes_videos - prev_likes,
        })

    # Sort by total followers descending
    rows.sort(key=lambda r: r["followers"], reverse=True)
    return rows


def _build_insights(rows: list[dict]) -> list[str]:
    """Build the bullet-point insights section."""
    if not rows:
        return ["No data available."]

    lines = []

    # Top Gainer — most follower growth
    top_gainer = max(rows, key=lambda r: r["d_followers"])
    if top_gainer["d_followers"] > 0:
        lines.append(
            f"• <b>Top Gainer: {top_gainer['label']}</b> saw the most "
            f"significant growth with <b>{_format_delta(top_gainer['d_followers'])} "
            f"new followers</b>."
        )

    # Reach Leader — highest view increase
    reach_leader = max(rows, key=lambda r: r["d_views"])
    if reach_leader["d_views"] > 0:
        lines.append(
            f"• <b>Reach Leader: {reach_leader['label']}</b> generated the "
            f"highest view increase with <b>{_format_delta(reach_leader['d_views'])} "
            f"new views</b>."
        )

    # Engagement Peak — top accounts by like increase
    like_sorted = sorted(rows, key=lambda r: r["d_likes"], reverse=True)
    top_likers = [r for r in like_sorted if r["d_likes"] > 0][:2]
    if len(top_likers) == 2:
        lines.append(
            f"• <b>Engagement Peak: {top_likers[0]['label']}</b> and "
            f"<b>{top_likers[1]['label']}</b> led the engagement surge with "
            f"<b>{_format_delta(top_likers[0]['d_likes'])}</b> and "
            f"<b>{_format_delta(top_likers[1]['d_likes'])} likes</b> respectively."
        )
    elif len(top_likers) == 1:
        lines.append(
            f"• <b>Engagement Peak: {top_likers[0]['label']}</b> led the "
            f"engagement surge with <b>{_format_delta(top_likers[0]['d_likes'])} "
            f"new likes</b>."
        )

    # Total Leader — highest total followers
    total_leader = max(rows, key=lambda r: r["followers"])
    lines.append(
        f"• <b>Total Leader: {total_leader['label']}</b> maintains the "
        f"largest community with <b>{_format_number(total_leader['followers'])} "
        f"total followers</b>."
    )

    # Risk Alert — accounts with negative follower delta
    decliners = [r for r in rows if r["d_followers"] < 0]
    if decliners:
        names = ", ".join(r["label"] for r in decliners)
        losses = ", ".join(
            f"losing <b>{abs(r['d_followers'])} follower{'s' if abs(r['d_followers']) != 1 else ''}</b>"
            for r in decliners
        )
        if len(decliners) == 1:
            lines.append(
                f"• <b>Risk Alert: {names}</b> is the only account to "
                f"experience a decrease, {losses}."
            )
        else:
            lines.append(
                f"• <b>Risk Alert:</b> {names} experienced decreases."
            )

    return lines


def _build_table(rows):
    """
    Build a clean text-based table for the Telegram message.
    Each account gets a linked name + stats on one line.
    """
    if not rows:
        return ""

    tbl = []
    for i, r in enumerate(rows):
        username = r.get("username", "")
        label = r["label"]
        link = '<a href="https://www.tiktok.com/@' + username + '">' + label + '</a>'
        total = _format_number(r["followers"])
        d_fol = _format_delta(r["d_followers"])
        d_views = _format_delta(r["d_views"])
        d_likes = _format_delta(r["d_likes"])

        num = str(i + 1)
        line = (
            num + ". " + link
            + " \u2014 <b>" + total + "</b> fol"
        )
        detail = (
            "     \u0394Fol: " + d_fol
            + "  \u00b7  \u0394Views: " + d_views
            + "  \u00b7  \u0394Likes: " + d_likes
        )
        tbl.append(line)
        tbl.append(detail)

    return "\n".join(tbl)


def _build_daily_summary(results: list, prev_snapshot: Optional[dict]) -> str:
    """
    Build the Daily Performance Summary message.

    Args:
        results: List of AccountData objects from scraper
        prev_snapshot: Previous snapshot dict (or None for first run)

    Returns:
        Formatted HTML string for Telegram
    """
    successful = [r for r in results if not r.error]
    failed = [r for r in results if r.error]

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_short = _format_date_short(today_str)

    if prev_snapshot:
        prev_date_short = _format_date_short(prev_snapshot.get("date", ""))
        header_dates = f"{today_short} vs. {prev_date_short}"
    else:
        header_dates = f"{today_short} (first run)"

    rows = _compute_deltas(successful, prev_snapshot)

    lines = []

    # Header
    lines.append(f"\U0001f4c5 <b>Daily Performance Summary ({header_dates})</b>")
    lines.append("")

    # Insights
    if rows:
        insights = _build_insights(rows)
        lines.extend(insights)
        lines.append("")

    # Table grouped by category
    if rows:
        # Group rows by category
        categories = OrderedDict()
        for r in rows:
            cat = r.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(r)

        for cat_name, cat_rows in categories.items():
            lines.append("")
            lines.append("<b>" + cat_name + "</b>")
            lines.append(_build_table(cat_rows))

    # Failed accounts footnote
    if failed:
        lines.append("")
        lines.append(f"\u26a0\ufe0f {len(failed)} account(s) failed to scrape.")

    return "\n".join(lines)


async def send_report(results: list, prev_snapshot: Optional[dict] = None) -> bool:
    """
    Send scrape results as a Telegram message.

    Args:
        results: List of AccountData objects from scraper
        prev_snapshot: Previous snapshot dict for delta calculation

    Returns:
        True if message sent successfully
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning(
            "Telegram not configured. Set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID in .env"
        )
        return False

    try:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        report = _build_daily_summary(results, prev_snapshot)

        # Telegram has a 4096 char limit per message.
        # Split into multiple messages if needed.
        if len(report) <= 4096:
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=report,
                parse_mode=ParseMode.HTML,
            )
        else:
            chunks = _split_report(report, max_len=4096)
            for chunk in chunks:
                await bot.send_message(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                )

        logger.info("Telegram report sent successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to send Telegram report: {e}")
        return False


def _split_report(report: str, max_len: int = 4096) -> list[str]:
    """Split a long report into chunks that fit Telegram's message limit."""
    lines = report.split("\n")
    chunks = []
    current_chunk = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > max_len and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


async def send_test_message() -> bool:
    """Send a test message to verify Telegram configuration."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print(
            "\u274c Telegram not configured. "
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
        )
        return False

    try:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text="\u2705 TikTok Scraper bot connected successfully!",
        )
        print("\u2705 Test message sent!")
        return True
    except Exception as e:
        print(f"\u274c Failed: {e}")
        return False


# --- Quick test ---
if __name__ == "__main__":
    import asyncio
    asyncio.run(send_test_message())
