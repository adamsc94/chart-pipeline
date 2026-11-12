"""Match charted songs to MusicBrainz recordings.

Searches by primary artist + title, then verifies the returned credits
contain the other artists Billboard listed. Unmatched songs are skipped
and counted by reason.
"""

import csv
import logging
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

CONTACT = os.environ.get("MB_CONTACT")
if not CONTACT:
    raise SystemExit("Set MB_CONTACT in .env")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("Set DATABASE_URL in .env")

logger = logging.getLogger(__name__)

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


def search(artist, title, attempts=6):
    """Query MusicBrainz, retrying on 503 rate limiting."""
    query = f'artist:"{artist}" AND recording:"{title}"'

    for attempt in range(attempts):
        time.sleep(2.5)
        try:
            r = requests.get(
                f"{BASE}/recording",
                params={"query": query, "fmt": "json", "limit": 10},
                headers=HEADERS,
                timeout=15,
            )
        except (requests.Timeout, requests.ConnectionError) as e:
            print(f"    network error, retrying: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
            continue

        if r.status_code == 503:
            time.sleep(5 * (attempt + 1))
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

    # Earliest release favours the original over a later remaster. Ties on
    # date are broken by MBID so the same candidates always give the same
    # pick; MusicBrainz's result order is not stable between calls (DECISIONS 015)
    best = min(
        full_credit,
        key=lambda r: (r.get("first-release-date") or "9999", r["id"]),
    )
    return best, "matched"


def existing_ranks(outfile):
    """Ranks already written to the output file, so a rerun can skip them."""
    if not outfile.exists():
        return set()
    with outfile.open(encoding="utf-8") as f:
        return {row["rank"] for row in csv.DictReader(f)}


def load_cache():
    """(title, artist) -> stored recording for every pair already in Postgres.

    Value is a dict of the mb_* output fields, or None when the pair has
    appeared before without a match. If a pair has several rows that disagree,
    the most recent chart_date wins. A missing table (first ever run) just
    means an empty cache.
    """
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            result = conn.execute(
                """
                SELECT DISTINCT ON (c.title, c.artist)
                    c.title, c.artist, c.mb_recording_id,
                    r.title, r.artist_credit, r.length_ms,
                    r.first_release_date, r.isrc
                FROM chart_entries c
                LEFT JOIN recordings r USING (mb_recording_id)
                ORDER BY c.title, c.artist, c.chart_date DESC
                """
            ).fetchall()
    except psycopg.errors.UndefinedTable:
        return {}

    cache = {}
    for title, artist, mbid, mb_title, credit, length, released, isrc in result:
        cache[(title, artist)] = (
            None
            if mbid is None
            else {
                "mb_recording_id": mbid,
                "mb_title": mb_title,
                "mb_artist_credit": credit,
                "mb_length_ms": length,
                "mb_first_release_date": released,
                "mb_isrc": isrc,
            }
        )
    return cache


def enrich_and_write(csv_path):
    """Enrich one processed chart CSV, writing each row as it is matched.

    Rows are appended and flushed immediately, so a crash keeps whatever
    was already done. Rerunning skips ranks already present in the output.
    """
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    outfile = ENRICHED_DIR / csv_path.name

    done = existing_ranks(outfile)
    if done:
        print(f"Resuming: {len(done)} rows already written", file=sys.stderr)

    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    cache = load_cache()
    logger.info("Cache holds %d known (title, artist) pairs", len(cache))

    reasons = Counter()
    n_entries = n_cached = n_new = n_new_matched = 0
    is_new = not outfile.exists()

    with outfile.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        if is_new:
            writer.writeheader()

        for i, row in enumerate(rows, 1):
            if row["rank"] in done:
                continue

            n_entries += 1
            key = (row["title"], row["artist"])

            # Seen before: reuse the stored answer, including "no match" (None)
            if key in cache:
                n_cached += 1
                cached = cache[key]
                if cached is not None:
                    writer.writerow(
                        {
                            "chart_date": row["chart_date"],
                            "rank": row["rank"],
                            "title": row["title"],
                            "artist": row["artist"],
                            **cached,
                        }
                    )
                    f.flush()
                continue

            n_new += 1
            artists = split_credit(row["artist"])
            recordings = search(artists[0], row["title"])
            match, reason = pick_match(recordings, artists)
            reasons[reason] += 1

            print(
                f"  [{i}/{len(rows)}] {row['title'][:40]:42} {reason}",
                file=sys.stderr,
            )

            if match is None:
                continue

            n_new_matched += 1
            writer.writerow(
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
            f.flush()  # straight to disk, so a crash does not lose buffered rows

    if reasons:
        total = sum(reasons.values())
        print(f"\nProcessed {total} songs this run", file=sys.stderr)
        for reason, n in reasons.most_common():
            print(f"  {reason:20} {n}", file=sys.stderr)
    logger.info(
        "Of %d entries, %d are new (%d matched), %d reused from the database "
        "and skipped the MusicBrainz call",
        n_entries,
        n_new,
        n_new_matched,
        n_cached,
    )
    print(f"\nWrote {outfile}", file=sys.stderr)

    return outfile


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    enrich_and_write(Path(sys.argv[1]))