"""Compare two matching strategies against MusicBrainz.

Strategy A: full Billboard credit string + title
Strategy B: primary artist only (text before first separator) + title

Prints what each returns so we can judge which matches better.
"""

import csv
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()  # read .env into environment variables

CONTACT = os.environ.get("MB_CONTACT")
if not CONTACT:
    raise SystemExit(
        "Set MB_CONTACT to a contact address, e.g.\n"
        "  export MB_CONTACT='you@example.com'"
    )

HEADERS = {"User-Agent": f"chart-pipeline/0.1 ( {CONTACT} )"}
BASE = "https://musicbrainz.org/ws/2"


SEPARATOR_RE = re.compile(r"\s+(?:Featuring|With|&|X|x)\s+|,")


def primary_artist(credit):
    """Everything before the first separator."""
    return SEPARATOR_RE.split(credit)[0].strip()


def search(artist, title, attempts=3):
    """Query MusicBrainz, retrying on 503 (their rate limiter)."""
    query = f'artist:"{artist}" AND recording:"{title}"'

    for attempt in range(attempts):
        time.sleep(1.5)  # before the request, not after
        r = requests.get(
            f"{BASE}/recording",
            params={"query": query, "fmt": "json", "limit": 3},
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 503:
            time.sleep(3 * (attempt + 1))  # back off further each try
            continue        
        r.raise_for_status()
        return [
            (
                rec["title"],
                " + ".join(
                    c["name"] for c in rec["artist-credit"] if isinstance(c, dict)
                ),
                rec.get("length"),
            )
            for rec in r.json().get("recordings", [])
        ]

    raise RuntimeError(f"Gave up after {attempts} attempts: {query}")


if __name__ == "__main__":
    # Pull messy rows out of the processed CSVs
    rows = []
    for path in sorted(Path("data/processed").glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))

    messy = [r for r in rows if SEPARATOR_RE.search(r["artist"])][:5]

    for row in messy:
        title, credit = row["title"], row["artist"]
        print(f"\n{'=' * 70}\nBillboard: {credit} - {title}")

        print(f"\n  A) full credit string:")
        for t, a, ln in search(credit, title):
            print(f"     {t!r} by {a!r} ({ln})")

        primary = primary_artist(credit)
        print(f"\n  B) primary artist {primary!r}:")
        for t, a, ln in search(primary, title):
            print(f"     {t!r} by {a!r} ({ln})")