-- SQLite schema for the chart pipeline.
-- Standard SQL where possible, so the move to PostgreSQL later is small.

-- Raw Billboard HTML, kept in the database because the GitHub Actions
-- filesystem is thrown away after each run. chart_date stays NULL until
-- the chart date has been read from the page.
CREATE TABLE IF NOT EXISTS raw_charts (
    fetched_at  TIMESTAMPTZ NOT NULL,
    url         TEXT NOT NULL,
    html_gz     BYTEA NOT NULL,
    chart_date  TEXT,
    PRIMARY KEY (fetched_at)
);

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