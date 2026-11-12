"""One-off: load the raw pages fetched before raw_charts existed.

Run from the project root:  python -m load.backfill_raw_charts

Only files in data/raw/ dated before the oldest row already in raw_charts are
loaded; anything newer was stored by fetch_chart itself. Safe to re-run:
a page already in the table is skipped.

Songs are not parsed here. Those weeks are already in chart_entries.
"""

import gzip
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from ingest.parse_chart import extract_chart_date
from load.load_db import connect

RAW_DIR = Path("data/raw")

# Same page fetch_chart requests. Written out here rather than imported, so the
# backfill doesn't need MB_CONTACT set.
CHART_URL = "https://www.billboard.com/charts/hot-100/"


def file_date(path):
    """The fetch date in a name like hot100_2026-10-02.html."""
    return date.fromisoformat(path.stem.removeprefix("hot100_"))


def backfill():
    with connect() as conn:  # saves (commits) at the end of the block
        oldest = conn.execute("SELECT MIN(fetched_at) FROM raw_charts").fetchone()[0]
        files = sorted(
            p for p in RAW_DIR.glob("hot100_*.html")
            if oldest is None or file_date(p) < oldest.date()
        )

        inserted = 0
        for path in files:
            html_bytes = path.read_bytes()

            # The real fetch time was never recorded for these pages. The file's
            # modification time is the best stand-in: fetch wrote the file, and
            # each one matches the date in its name. Approximate, not exact.
            fetched_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

            try:
                soup = BeautifulSoup(html_bytes.decode("utf-8"), "html.parser")
                chart_date = extract_chart_date(soup).isoformat()
            except ValueError as e:
                # NULL means the date couldn't be read, same as for live rows.
                chart_date = None
                print(f"WARNING: {path.name}: no chart date ({e})", file=sys.stderr)

            result = conn.execute(
                "INSERT INTO raw_charts (fetched_at, url, html_gz, chart_date) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (fetched_at) DO NOTHING",
                (fetched_at, CHART_URL, gzip.compress(html_bytes), chart_date),
            )
            status = "inserted" if result.rowcount == 1 else "already stored, skipped"
            inserted += result.rowcount
            print(
                f"{path.name}: fetched_at={fetched_at.isoformat()} "
                f"chart_date={chart_date} -> {status}",
                file=sys.stderr,
            )

    print(f"Inserted {inserted} of {len(files)} pages", file=sys.stderr)


if __name__ == "__main__":
    backfill()
