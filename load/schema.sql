-- SQLite schema for the chart pipeline.
-- Standard SQL where possible, so the move to PostgreSQL later is small.

CREATE TABLE IF NOT EXISTS recordings (
    mb_recording_id    TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    artist_credit      TEXT NOT NULL,
    length_ms          INTEGER,
    first_release_date TEXT,
    isrc               TEXT
);

-- One row per song per week. (chart_date, rank) is a natural key. There is
-- exactly one song at each rank in a given week, so re-running a load cannot
-- create duplicates.
CREATE TABLE IF NOT EXISTS chart_entries (
    chart_date      TEXT NOT NULL,
    rank            INTEGER NOT NULL,
    title           TEXT NOT NULL,
    artist          TEXT NOT NULL,
    last_week       INTEGER,
    peak            INTEGER NOT NULL,
    weeks_on_chart  INTEGER NOT NULL,
    weeks_at_no_1   INTEGER NOT NULL,
    mb_recording_id TEXT,
    PRIMARY KEY (chart_date, rank),
    FOREIGN KEY (mb_recording_id) REFERENCES recordings(mb_recording_id)
);