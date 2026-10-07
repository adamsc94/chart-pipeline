"""Match charted songs to MusicBrainz recordings.

Searches by primary artist + title, then verifies the returned credits
contain the other artists Billboard listed. Unmatched songs are skipped
and counted by reason.
"""

import csv
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CONTACT = os.environ.get("MB_CONTACT")
if not CONTACT:
    raise SystemExit("Set MB_CONTACT in .env")

HEADERS = {"User-Agent": f"chart-pipeline/0.1 ( {CONTACT} )"}
BASE = "https://musicbrainz.org/ws/2"

SEPARATOR_RE = re.compile(r"\s+(?:Featuring|With|&|X|x)\s+|,\s*")

PROCESSED_DIR = Path("data/processed")
ENRICHED_DIR = Path("data/enriched")

OUT_FIELDS = [
    "chart_date",
    "rank",
    "title",
    "artist",
    "mb_recording_id",
    "mb_title",
    "mb_artist_credit",
    "mb_length_ms",
    "mb_first_release_date",
    "mb_isrc",
]


def split_credit(credit):
    """Billboard credit string -> list of artist names."""
    return [p.strip() for p in SEPARATOR_RE.split(credit) if p.strip()]


def search(artist, title, attempts=3):
    """Query MusicBrainz, retrying on 503 rate limiting."""
    query = f'artist:"{artist}" AND recording:"{title}"'

    for attempt in range(attempts):
        time.sleep(1.5)
        r = requests.get(
            f"{BASE}/recording",
            params={"query": query, "fmt": "json", "limit": 10},
            headers=HEADERS,
            timeout=15,
        )
        if r.status_code == 503:
            time.sleep(3 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json().get("recordings", [])

    raise RuntimeError(f"Gave up after {attempts} attempts: {query}")


def credited_names(rec):
    """All artist names on a recording, lowercased."""
    return {
        c["name"].lower() for c in rec.get("artist-credit", []) if isinstance(c, dict)
    }


def pick_match(recordings, expected_artists):
    """Choose the best recording, or return (None, reason).

    Applies the rules from DECISIONS 003 and 004: drop anything without an
    ISRC, require the credits to contain every artist Billboard listed, then
    take the earliest release among what survives.
    """
    if not recordings:
        return None, "no_results"

    # No ISRC means not commercially released - bootlegs, fan uploads
    with_isrc = [r for r in recordings if r.get("isrcs")]
    if not with_isrc:
        return None, "no_isrc"

    # Every artist Billboard credited must appear in MusicBrainz's credits.
    # This is what stops solo "Dracula" matching the Tame Impala & JENNIE one.
    expected = {a.lower() for a in expected_artists}
    full_credit = [r for r in with_isrc if expected <= credited_names(r)]
    if not full_credit:
        return None, "credits_mismatch"

    # Earliest release favours the original over a later remaster
    best = min(full_credit, key=lambda r: r.get("first-release-date") or "9999")
    return best, "matched"


def enrich_chart(csv_path):
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    reasons = Counter()
    out_rows = []

    for i, row in enumerate(rows, 1):
        artists = split_credit(row["artist"])
        recordings = search(artists[0], row["title"])
        match, reason = pick_match(recordings, artists)
        reasons[reason] += 1

        print(f"  [{i}/{len(rows)}] {row['title'][:40]:42} {reason}", file=sys.stderr)

        if match is None:
            continue

        out_rows.append(
            {
                "chart_date": row["chart_date"],
                "rank": row["rank"],
                "title": row["title"],
                "artist": row["artist"],
                "mb_recording_id": match["id"],
                "mb_title": match["title"],
                "mb_artist_credit": " + ".join(sorted(credited_names(match))),
                "mb_length_ms": match.get("length"),
                "mb_first_release_date": match.get("first-release-date"),
                "mb_isrc": match["isrcs"][0],
            }
        )

    return out_rows, reasons


if __name__ == "__main__":
    csv_path = Path(sys.argv[1])

    out_rows, reasons = enrich_chart(csv_path)

    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    outfile = ENRICHED_DIR / csv_path.name
    with outfile.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        writer.writeheader()
        writer.writerows(out_rows)

    total = sum(reasons.values())
    print(
        f"\nMatched {len(out_rows)}/{total} ({len(out_rows) / total:.0%})",
        file=sys.stderr,
    )
    for reason, n in reasons.most_common():
        print(f"  {reason:20} {n}", file=sys.stderr)
    print(f"\nWrote {outfile}", file=sys.stderr)