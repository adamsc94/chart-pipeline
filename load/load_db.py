"""Load processed and enriched chart CSVs into Postgres.

Reads both CSVs for a given chart date: the processed one has every charting
song, the enriched one has MusicBrainz matches for the subset that matched.
"""

import csv
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("Set DATABASE_URL in .env")

SCHEMA_PATH = Path("load/schema.sql")
PROCESSED_DIR = Path("data/processed")
ENRICHED_DIR = Path("data/enriched")


def connect():
    """Open the database, creating tables if they don't exist yet."""
    conn = psycopg.connect(DATABASE_URL)
    conn.execute(SCHEMA_PATH.read_text())
    return conn


def read_csv(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_int(value):
    """CSV gives us strings; empty cells become None."""
    return int(value) if value not in ("", None) else None


def load_recordings(conn, enriched_rows):
    """Insert MusicBrainz recordings, ignoring ones already stored."""
    rows = [
        (
            r["mb_recording_id"],
            r["mb_title"],
            r["mb_artist_credit"],
            to_int(r["mb_length_ms"]),
            r["mb_first_release_date"] or None,
            r["mb_isrc"] or None,
        )
        for r in enriched_rows
    ]

    # ON CONFLICT DO NOTHING skips rows whose primary key is already present.
    # A song charting for 20 weeks only needs its recording stored once.
    conn.cursor().executemany(
        """
        INSERT INTO recordings
            (mb_recording_id, title, artist_credit, length_ms,
             first_release_date, isrc)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (mb_recording_id) DO NOTHING
        """,
        rows,
    )
    return len(rows)


def load_chart_entries(conn, processed_rows, enriched_rows):
    """Insert one row per charting song, linked to its recording if matched."""
    # rank -> recording id, for the subset that matched
    matches = {r["rank"]: r["mb_recording_id"] for r in enriched_rows}

    rows = [
        (
            r["chart_date"],
            int(r["rank"]),
            r["title"],
            r["artist"],
            to_int(r["last_week"]),
            int(r["peak"]),
            int(r["weeks_on_chart"]),
            int(r["weeks_at_no_1"]),
            matches.get(r["rank"]),  # None when the song didn't match
        )
        for r in processed_rows
    ]

    # ON CONFLICT ... DO UPDATE makes re-running a load idempotent: the same
    # (chart_date, rank) overwrites rather than duplicating. EXCLUDED refers
    # to the row we tried to insert.
    conn.cursor().executemany(
        """
        INSERT INTO chart_entries
            (chart_date, rank, title, artist, last_week, peak,
             weeks_on_chart, weeks_at_no_1, mb_recording_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (chart_date, rank) DO UPDATE SET
            title           = EXCLUDED.title,
            artist          = EXCLUDED.artist,
            last_week       = EXCLUDED.last_week,
            peak            = EXCLUDED.peak,
            weeks_on_chart  = EXCLUDED.weeks_on_chart,
            weeks_at_no_1   = EXCLUDED.weeks_at_no_1,
            mb_recording_id = EXCLUDED.mb_recording_id
        """,
        rows,
    )
    return len(rows)


def load_chart(chart_file):
    """Load one chart's processed and enriched CSVs into Postgres."""
    processed_rows = read_csv(PROCESSED_DIR / chart_file)
    enriched_rows = read_csv(ENRICHED_DIR / chart_file)

    conn = connect()
    load_recordings(conn, enriched_rows)
    n_entries = load_chart_entries(conn, processed_rows, enriched_rows)
    conn.commit()  # nothing is saved until this runs

    n_recordings = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    print(f"Loaded {n_entries} chart entries", file=sys.stderr)
    print(f"Database now holds {n_recordings} recordings", file=sys.stderr)

    conn.close()
    return n_entries


if __name__ == "__main__":
    load_chart(sys.argv[1])
