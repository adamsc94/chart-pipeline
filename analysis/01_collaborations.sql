-- Finding 1: how much of the Hot 100 is collaborations, and do they chart
-- any differently from solo songs?
--
-- A collaboration is any artist credit that joins two or more acts. Billboard
-- writes the joiner with a capital letter ("Featuring", "With", "X") or as
-- " & " or ", ", so the match is case-sensitive on purpose. That keeps band
-- names like "Dexter And The Moonrocks" and "Dan + Shay" out.
--
-- The one band name the pattern does catch is listed by hand below. That list
-- will need a new entry if an act like "Tyler, The Creator" charts.
--
-- Uses only Billboard's own credit string, so MusicBrainz match errors cannot
-- affect it. Returns two rows per chart week: one for solo, one for
-- collaborations.

WITH classified AS (
    SELECT
        chart_date,
        rank,
        (
            artist ~ '( Featuring | & | With | X |, )'
            AND artist NOT IN ('Earth, Wind & Fire')
        ) AS is_collab
    FROM chart_entries
)

SELECT
    chart_date,
    CASE WHEN is_collab THEN 'collaboration' ELSE 'solo' END AS credit_type,
    COUNT(*)                                                AS chart_slots,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rank)       AS median_rank,
    COUNT(*) FILTER (WHERE rank <= 40)                      AS top_40_slots
FROM classified
GROUP BY chart_date, is_collab
ORDER BY chart_date, credit_type;
