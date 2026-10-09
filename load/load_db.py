"""Load processed and enriched chart CSVs into SQLite.

Reads both CSVs for a given chart date: the processed one has every charting
song, the enriched one has MusicBrainz matches for the subset that matched.
"""

import csv
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/chart.db")
SCHEMA_PATH = Path("load/schema.sql")
PROCESSED_DIR = Path("data/processed")
ENRICHED_DIR = Path("data/enriched")


def connect():
    """Open the database, creating tables if they don't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  
    conn.executescript(SCHEMA_PATH.read_text())
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

    # INSERT OR IGNORE skips rows whose primary key is already present. A song
    # charting for 20 weeks only needs its recording stored once.
    conn.executemany(
        """
        INSERT OR IGNORE INTO recordings
            (mb_recording_id, title, artist_credit, length_ms,
             first_release_date, isrc)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return conn.total_changes


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

    # INSERT OR REPLACE makes re-running a load idempotent: the same
    # (chart_date, rank) overwrites rather than duplicating.
    conn.executemany(
        """
        INSERT OR REPLACE INTO chart_entries
            (chart_date, rank, title, artist, last_week, peak,
             weeks_on_chart, weeks_at_no_1, mb_recording_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)

if __name__ == "__main__":
    chart_file = sys.argv[1]  # e.g. hot100_2026-10-03.csv

    processed_rows = read_csv(PROCESSED_DIR / chart_file)
    enriched_rows = read_csv(ENRICHED_DIR / chart_file)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()

    load_recordings(conn, enriched_rows)
    n_entries = load_chart_entries(conn, processed_rows, enriched_rows)

    conn.commit()  # nothing is saved until this runs

    n_recordings = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    print(f"Loaded {n_entries} chart entries")
    print(f"Database now holds {n_recordings} recordings")

    conn.close()