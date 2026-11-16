-- Pressure tests for the three findings in the README.
--
-- These are the checks behind the caveats: sample sizes, MusicBrainz match
-- coverage, and whether each result survives a stricter cut. Run them one at
-- a time. All are read-only.


-- 1. Coverage. How many chart rows have a MusicBrainz match each week, and
--    do the unmatched songs sit at different ranks from the matched ones?
--    If unmatched songs clustered at the top or bottom, the length finding
--    would be looking at a skewed slice of the chart.
SELECT
    chart_date,
    COUNT(*)                                                    AS chart_rows,
    COUNT(mb_recording_id)                                      AS matched_rows,
    ROUND(AVG(rank) FILTER (WHERE mb_recording_id IS NOT NULL), 1) AS avg_rank_matched,
    ROUND(AVG(rank) FILTER (WHERE mb_recording_id IS NULL), 1)     AS avg_rank_unmatched
FROM chart_entries
GROUP BY chart_date
ORDER BY chart_date;


-- 2. Collaborations at song level. The weekly numbers in 01 count a song
--    once per week it charts, so this repeats the comparison with each song
--    counted once. This is the real sample size for finding 1.
WITH songs AS (
    SELECT
        title,
        artist,
        (
            artist ~ '( Featuring | & | With | X |, )'
            AND artist NOT IN ('Earth, Wind & Fire')
        )                    AS is_collab,
        MIN(peak)            AS peak,
        MAX(weeks_on_chart)  AS weeks_on_chart
    FROM chart_entries
    GROUP BY title, artist
)
SELECT
    CASE WHEN is_collab THEN 'collaboration' ELSE 'solo' END       AS credit_type,
    COUNT(*)                                                       AS songs,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY peak)              AS median_peak,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY weeks_on_chart)    AS median_weeks_on_chart,
    COUNT(*) FILTER (WHERE peak <= 10)                             AS songs_peaking_top_10
FROM songs
GROUP BY is_collab;


-- 3. Does the collaboration rule agree with MusicBrainz? MusicBrainz joins
--    credited artists with " + ", which gives an independent second opinion
--    for every matched song. Any row where the two disagree is listed.
WITH songs AS (
    SELECT
        c.title,
        c.artist,
        (
            c.artist ~ '( Featuring | & | With | X |, )'
            AND c.artist NOT IN ('Earth, Wind & Fire')
        )                                      AS billboard_says_collab,
        BOOL_OR(r.artist_credit LIKE '% + %')  AS musicbrainz_says_collab
    FROM chart_entries AS c
    JOIN recordings AS r
        ON r.mb_recording_id = c.mb_recording_id
    GROUP BY c.title, c.artist
)
SELECT
    billboard_says_collab,
    musicbrainz_says_collab,
    COUNT(*)                         AS songs,
    STRING_AGG(artist, ' | ')
        FILTER (WHERE billboard_says_collab <> musicbrainz_says_collab) AS disagreements
FROM songs
GROUP BY billboard_says_collab, musicbrainz_says_collab;


-- 4. Length vs rank, one week at a time. Each week is a clean sample of
--    about 90 matched songs with no song counted twice. Negative means
--    longer songs rank higher (closer to number 1). spearman is the same
--    correlation computed on ranks, which a few very long songs cannot move.
WITH ranked AS (
    SELECT
        c.chart_date,
        c.rank,
        r.length_ms,
        RANK() OVER (PARTITION BY c.chart_date ORDER BY r.length_ms) AS length_rank
    FROM chart_entries AS c
    JOIN recordings AS r
        ON r.mb_recording_id = c.mb_recording_id
)
SELECT
    chart_date,
    COUNT(*)                                       AS matched_songs,
    ROUND(CORR(rank, length_ms)::numeric, 2)       AS pearson,
    ROUND(CORR(rank, length_rank)::numeric, 2)     AS spearman
FROM ranked
GROUP BY chart_date
ORDER BY chart_date;


-- 5. Length vs position at song level, with and without doubtful matches.
--    A match is doubtful here when the MusicBrainz title is not the same as
--    the Billboard title once case and punctuation are stripped, for example
--    a remix or an extended version with a different running time.
WITH songs AS (
    SELECT
        c.title,
        c.artist,
        r.length_ms,
        MIN(c.peak) AS peak,
        MIN(c.rank) AS best_rank_seen,
        LOWER(REGEXP_REPLACE(c.title, '[^a-zA-Z0-9]', '', 'g'))
            <> LOWER(REGEXP_REPLACE(r.title, '[^a-zA-Z0-9]', '', 'g')) AS title_differs
    FROM chart_entries AS c
    JOIN recordings AS r
        ON r.mb_recording_id = c.mb_recording_id
    GROUP BY c.title, c.artist, r.length_ms, r.title
),
samples AS (
    SELECT 'all matched songs' AS sample, * FROM songs
    UNION ALL
    SELECT 'titles agree only' AS sample, * FROM songs WHERE NOT title_differs
),
with_ranks AS (
    SELECT
        sample,
        RANK() OVER (PARTITION BY sample ORDER BY length_ms)      AS length_rank,
        RANK() OVER (PARTITION BY sample ORDER BY peak)           AS peak_rank,
        RANK() OVER (PARTITION BY sample ORDER BY best_rank_seen) AS best_rank_rank
    FROM samples
)
SELECT
    sample,
    COUNT(*)                                               AS songs,
    ROUND(CORR(peak_rank, length_rank)::numeric, 2)        AS spearman_vs_peak,
    ROUND(CORR(best_rank_rank, length_rank)::numeric, 2)   AS spearman_vs_best_rank_seen
FROM with_ranks
GROUP BY sample
ORDER BY sample;


-- 6. Week-to-week retention, consecutive weeks only. The pair on either
--    side of the gap (Oct 10 to Oct 31) is three weeks apart, so it is left
--    out and not treated as a normal week.
SELECT
    this_week.chart_date,
    COUNT(*)                 AS chart_rows,
    COUNT(last_week.title)   AS also_on_chart_the_week_before
FROM chart_entries AS this_week
LEFT JOIN chart_entries AS last_week
    ON  last_week.title  = this_week.title
    AND last_week.artist = this_week.artist
    AND last_week.chart_date::date = this_week.chart_date::date - 7
WHERE EXISTS (
    SELECT 1
    FROM chart_entries AS prior
    WHERE prior.chart_date::date = this_week.chart_date::date - 7
)
GROUP BY this_week.chart_date
ORDER BY this_week.chart_date;


-- 7. Re-entries and tenure per week: how many songs came back, how high the
--    best one landed, and how long the typical song on that week's chart has
--    been charting. weeks_on_chart is a lifetime total that includes earlier
--    runs, which is why it is reported as a median and not an average.
SELECT
    chart_date,
    COUNT(*) FILTER (WHERE last_week IS NULL AND weeks_on_chart > 1)      AS re_entries,
    MIN(rank) FILTER (WHERE last_week IS NULL AND weeks_on_chart > 1)     AS best_re_entry_rank,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rank)
        FILTER (WHERE last_week IS NULL AND weeks_on_chart > 1)           AS median_re_entry_rank,
    COUNT(*) FILTER (WHERE weeks_on_chart = 1)                            AS debuts,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY weeks_on_chart)           AS median_weeks_on_chart
FROM chart_entries
GROUP BY chart_date
ORDER BY chart_date;
