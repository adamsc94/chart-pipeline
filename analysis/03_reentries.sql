-- Finding 3: where do songs land when they come back onto the chart?
--
-- A re-entry is a song with no rank last week (last_week IS NULL) that has
-- charted before (weeks_on_chart > 1). A NULL last_week with
-- weeks_on_chart = 1 is a debut, which is a different thing.
--
-- Both fields are Billboard's own, printed on the chart page. They do not
-- depend on which weeks this pipeline happened to collect, so the two-week
-- gap in the data cannot create or hide a re-entry in a week that was
-- collected. Re-entries that happened during the gap are simply not here.
--
-- No MusicBrainz columns are used. Returns one row per re-entry.

SELECT
    chart_date,
    rank,
    title,
    artist,
    weeks_on_chart,
    peak
FROM chart_entries
WHERE last_week IS NULL
  AND weeks_on_chart > 1
ORDER BY chart_date, rank;
