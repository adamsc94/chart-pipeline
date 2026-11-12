"""Fetch the Billboard Hot 100 page and save the raw HTML to disk and Postgres."""

import gzip
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from load.load_db import connect

load_dotenv()

CONTACT = os.environ.get("MB_CONTACT")
if not CONTACT:
    raise SystemExit("Set MB_CONTACT in .env")

CHART_URL = "https://www.billboard.com/charts/hot-100/"
USER_AGENT = f"chart-pipeline/0.1 ( {CONTACT} )"
RAW_DIR = Path("data/raw")


def fetch_chart():
    response = requests.get(
        CHART_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    outfile = RAW_DIR / f"hot100_{date.today().isoformat()}.html"
    outfile.write_text(response.text, encoding="utf-8")
    print(f"Saved {len(response.text):,} characters to {outfile}", file=sys.stderr)

    # GitHub Actions throws its files away after each run, so keep a copy in
    # Postgres. No try/except: a failed insert should fail the run, because
    # silently losing the page is worse. chart_date is filled in later by parsing.
    html_gz = gzip.compress(outfile.read_bytes())
    with connect() as conn:  # saves (commits) at the end of the block
        conn.execute(
            "INSERT INTO raw_charts (fetched_at, url, html_gz, chart_date) "
            "VALUES (%s, %s, %s, NULL)",
            (datetime.now(timezone.utc), CHART_URL, html_gz),
        )
    print(f"Stored {len(html_gz):,} compressed bytes in raw_charts", file=sys.stderr)

    return outfile

if __name__ == "__main__":
    fetch_chart()
