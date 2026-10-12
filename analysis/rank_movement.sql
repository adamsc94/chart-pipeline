
---calculates rank movement from last week by joining the table on itself. 
--Commented out filters on the end check that billboard's last week field matches the calculated one. 


SELECT 

b.title
, a.rank as "LAST WEEK"
, b.rank as "THIS WEEK"
, b.rank - a.rank as "COMPUTED WEEK CHANGE"
--, b.last_week

--,b.last_week - a.rank as "last week rank check"

from chart_entries b

LEFT JOIN chart_entries a ON 
b.title = a.title 
AND b.artist = a.artist 
AND a.chart_date = '2026-10-03'

WHERE b.chart_date = '2026-10-10'

--AND b.last_week - a.rank <> 0 
--AND b.last_week - a.rank  IS NOT NULL