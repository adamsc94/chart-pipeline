-- Finding 2: does song length relate to chart position?
--
-- One row per song, not per chart week. A song that charts five weeks would
-- otherwise count five times and make the sample look bigger than it is.
--
-- Length comes from MusicBrainz, so only matched songs appear (138 of 153 at
-- the time of writing). A song is identified by Billboard's title + artist
-- string, the same key the pipeline uses.
--
-- peak is Billboard's all-time peak for the song. best_rank_seen is the best
-- rank inside the weeks this pipeline has collected.

SELECT
    c.title,
    c.artist,
    ROUND(r.length_ms / 1000.0)  AS length_seconds,
    MIN(c.peak)                  AS peak,
    MIN(c.rank)                  AS best_rank_seen,
    COUNT(*)                     AS weeks_seen
FROM chart_entries AS c
JOIN recordings AS r
    ON r.mb_recording_id = c.mb_recording_id
WHERE r.length_ms IS NOT NULL
GROUP BY c.title, c.artist, r.length_ms
ORDER BY length_seconds;
