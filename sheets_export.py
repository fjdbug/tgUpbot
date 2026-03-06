"""
Google Sheets export module.
Appends TikTok scrape results to a Google Sheet.
"""

import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

import config

logger = logging.getLogger(__name__)

# Google Sheets API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column headers for the metrics sheet
HEADERS = [
    "Scraped At",
    "Account",
    "Label",
    "Followers",
    "Video URL",
    "Caption",
    "Views",
    "Likes",
    "Comments",
    "Shares",
    "Post Date",
    "Music",
]


def _get_client() -> gspread.Client:
    """Authenticate and return a gspread client using service account."""
    creds = Credentials.from_service_account_file(
        config.GOOGLE_SHEETS_CREDS_PATH, scopes=SCOPES
    )
    return gspread.authorize(creds)


def _get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet,
) -> gspread.Worksheet:
    """
    Get or create a worksheet for the current month.
    Worksheet name format: 'YYYY-MM' (e.g., '2026-03')
    """
    sheet_title = datetime.now().strftime("%Y-%m")

    try:
        worksheet = spreadsheet.worksheet(sheet_title)
        logger.info(f"Using existing worksheet: {sheet_title}")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=sheet_title, rows=1000, cols=len(HEADERS)
        )
        # Add headers to new worksheet
        worksheet.update("A1", [HEADERS])
        # Bold the header row
        worksheet.format("A1:L1", {"textFormat": {"bold": True}})
        logger.info(f"Created new worksheet: {sheet_title}")

    return worksheet


def export_to_sheets(results: list) -> bool:
    """
    Export scrape results to Google Sheets.

    Args:
        results: List of AccountData objects from scraper

    Returns:
        True if export was successful
    """
    if not config.GOOGLE_SHEETS_CREDS_PATH:
        logger.warning(
            "Google Sheets not configured. "
            "Set GOOGLE_SHEETS_CREDS_PATH in .env"
        )
        return False

    try:
        client = _get_client()
        spreadsheet = client.open(config.GOOGLE_SHEET_NAME)
        worksheet = _get_or_create_worksheet(spreadsheet)

        # Build rows from results
        rows = []
        for account in results:
            if account.error:
                # Log failed accounts as a single row with error
                rows.append(
                    [
                        account.scraped_at,
                        account.username,
                        account.label,
                        "",
                        "",
                        f"ERROR: {account.error[:100]}",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                continue

            for video in account.videos:
                rows.append(
                    [
                        account.scraped_at,
                        account.username,
                        account.label,
                        account.followers,
                        video.video_url,
                        video.caption[:100],
                        video.views,
                        video.likes,
                        video.comments,
                        video.shares,
                        video.post_date,
                        video.music,
                    ]
                )

        if rows:
            # Append all rows at once
            worksheet.append_rows(rows, value_input_option="USER_ENTERED")
            logger.info(f"✓ Exported {len(rows)} rows to Google Sheets")
        else:
            logger.warning("No data to export")

        return True

    except FileNotFoundError:
        logger.error(
            f"Google credentials file not found at: "
            f"{config.GOOGLE_SHEETS_CREDS_PATH}"
        )
        return False
    except gspread.SpreadsheetNotFound:
        logger.error(
            f"Google Sheet '{config.GOOGLE_SHEET_NAME}' not found. "
            "Create it first and share with the service account email."
        )
        return False
    except Exception as e:
        logger.error(f"✗ Failed to export to Sheets: {e}")
        return False
