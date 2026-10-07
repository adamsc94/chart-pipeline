"""Parse a saved Billboard Hot 100 HTML file into structured rows."""

import csv
import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROW_CLASS = "o-chart-results-list-row-container"
REQUIRED_LABELS = ["LW", "PEAK", "WEEKS ON CHART"]

PROCESSED_DIR = Path("data/processed")

FIELDNAMES = [
    "chart_date",
    "rank",
    "title",
    "artist",
    "last_week",
    "peak",
    "weeks_on_chart",
    "weeks_at_no_1",
]

# last_week is null for songs debuting on the chart - they have no previous
# position. Every other field must always carry a value.
NULLABLE_FIELDS = {"last_week"}


def extract_chart_date(soup):
    """Pull the chart's own week from the date picker, e.g. 2026-10-03.

    This is NOT the fetch date - the chart dated Oct 3 is live on Oct 2.
    Naming output by chart date keeps re-fetches idempotent and makes
    weeks joinable later.
    """
    el = soup.find("div", class_="a-show-on-hover-on-tab")
    if el is None:
        raise ValueError("Could not find chart date element")

    text = el.get_text().strip()
    match = re.search(r"Week of (\w+ \d{1,2}, \d{4})", text)
    if match is None:
        raise ValueError(f"Could not parse chart date from: {text!r}")

    return datetime.strptime(match.group(1), "%B %d, %Y").date()


def parse_chart(html_path):
    html = Path(html_path).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    # Anchor on the 100 row containers first; searching the whole page for
    # titles would return ~615 matches from sidebars and promo modules.
    rows = soup.find_all("div", class_=ROW_CLASS)
    print(f"Found {len(rows)} row containers", file=sys.stderr)

    songs = []
    for row in rows:
        # row.find, not soup.find - scoped to this one song
        title_el = row.find("h3", id="title-of-a-story")
        if title_el is None:
            continue

        # artist span sits directly after the title at the same level
        artist_el = title_el.find_next_sibling("span")

        # Pair each stat label with the value that follows it. Songs that have
        # hit no. 1 carry an extra "WEEKS AT NO. 1" column, so fixed positions
        # would silently shift the later values on those rows.
        stats = {}
        for label_el in row.find_all("span", class_="c-span"):
            label = label_el.get_text().strip()
            value_el = label_el.find_next_sibling()
            if value_el is not None:
                value = value_el.get_text().strip()
                # Desktop and mobile variants both render, so every label
                # appears twice. Tolerate that, but catch real conflicts.
                if label in stats:
                    if stats[label] != value:
                        raise ValueError(
                            f"Conflicting values for {label!r}: "
                            f"{stats[label]!r} vs {value!r}"
                        )
                    continue
                stats[label] = value

        missing = [lbl for lbl in REQUIRED_LABELS if lbl not in stats]
        if missing:
            raise ValueError(
                f"Missing expected stat labels {missing!r} in row. "
                f"Found: {list(stats)!r}. Billboard may have changed the layout."
            )

        # rank has no label of its own, so it stays positional - it is the
        # first c-label in the row, before the artist
        rank_el = row.find("span", class_="c-label")

        songs.append(
            {
                "rank": int(rank_el.get_text().strip()),
                "title": title_el.get_text().strip(),
                "artist": artist_el.get_text().strip() if artist_el else None,
                # "-" means the song was not on last week's chart: genuinely
                # absent, so null rather than 0 (rank 0 does not exist).
                "last_week": int(stats["LW"]) if stats["LW"].isdigit() else None,
                "peak": int(stats["PEAK"]),
                "weeks_on_chart": int(stats["WEEKS ON CHART"]),
                # Column is omitted entirely for songs that never hit no. 1,
                # which is a measured zero, not a missing value.
                "weeks_at_no_1": int(stats.get("WEEKS AT NO. 1", 0)),
            }
        )

    return songs


def write_csv(songs, chart_date):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    outfile = PROCESSED_DIR / f"hot100_{chart_date.isoformat()}.csv"

    with outfile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for song in songs:
            row = {"chart_date": chart_date.isoformat(), **song}

            # DictWriter silently writes an empty cell for any fieldname the
            # row does not contain, so check before handing it over.
            missing = [f for f in FIELDNAMES if f not in row]
            if missing:
                raise ValueError(f"Row is missing fields {missing!r}: {row!r}")

            empty = [
                f
                for f in FIELDNAMES
                if f not in NULLABLE_FIELDS and row[f] in (None, "")
            ]
            if empty:
                raise ValueError(
                    f"Row has empty non-nullable fields {empty!r}: {row!r}"
                )

            writer.writerow(row)

    return outfile


if __name__ == "__main__":
    html_path = sys.argv[1]  # argv[1] = filename you pass in
    html = Path(html_path).read_text(encoding="utf-8")
    chart_date = extract_chart_date(BeautifulSoup(html, "html.parser"))

    results = parse_chart(html_path)
    outfile = write_csv(results, chart_date)
    print(f"Wrote {len(results)} rows for {chart_date} to {outfile}", file=sys.stderr)