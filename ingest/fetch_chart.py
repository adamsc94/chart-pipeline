"""Fetch the Billboard Hot 100 page and save the raw HTML to disk."""

from datetime import date
from pathlib import Path

import requests

CHART_URL = "https://www.billboard.com/charts/hot-100/"
USER_AGENT = "chart-pipeline/0.1 ( ascottchapp@gmail.com )"
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

    print(f"Saved {len(response.text):,} characters to {outfile}")


if __name__ == "__main__":
    fetch_chart()
