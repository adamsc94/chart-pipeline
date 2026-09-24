"""Parse a saved Billboard Hot 100 HTML file into structured rows."""

import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROW_CLASS = "o-chart-results-list-row-container"


def parse_chart(html_path):
    html = Path(html_path).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    # Anchor on the 100 row containers first; searching the whole page for
    # titles would return 616 matches from sidebars and promo modules.
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

        songs.append({
            "title":     title_el.get_text().strip(),
            "artist": artist_el.get_text().strip() if artist_el else None,
        })

    return songs


if __name__ == "__main__":
    results = parse_chart(sys.argv[1])  # argv[1] = filename you pass in
    print(json.dumps(results[:10], indent=2))
    # print(json.dumps(results, indent=2))
    print(f"\nTotal parsed: {len(results)}", file=sys.stderr)