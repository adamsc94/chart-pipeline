# Chart Pipeline

Ingests the Billboard Hot 100 each week and parses it into validated, structured data, with MusicBrainz enrichment planned.

**Status:** Phase 1 (fetching and parsing) complete and working end to end. Have yet to build enrichment, loading, and scheduling.

---

## The question

What identifiable traits such as genre, song length, solo versus collaboration are trending in hit music?

## Architecture

1. **Fetch** the live chart page and save the raw HTML to `data/raw/`, named by fetch date.
2. **Parse** the 100 chart rows, validating structure before extracting any values.
3. **Write** a validated CSV to `data/processed/`, named by the chart's own week.

Raw HTML is saved to disk before any parsing so the parser can be iterated on offline, against bytes that are already captured, without re-requesting the page. Past weeks cannot be re-fetched once a chart rolls over.

## Running it

**1. Clone the repo**

```bash
git clone https://github.com/adamsc94/chart-pipeline.git
cd chart-pipeline
```

**2. Set up the virtual environment and install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Activation is per-session; you must run `source .venv/bin/activate` again in each new terminal. On Windows the command is `.venv\Scripts\activate`.

**3. Fetch and parse a chart**

```bash
python ingest/fetch_chart.py
```

The fetcher writes a dated file to `data/raw/`. Check that folder for the filename, then pass it to the parser:

```bash
python ingest/parse_chart.py data/raw/hot100_2026-10-02.html
```

Output lands in `data/processed/` as a CSV named by the chart's own week, which is not the same as the fetch date.

## Output

One row per charting song, per week:

| Column | Type | Notes |
|---|---|---|
| `chart_date` | date | The chart's own week, parsed from the page |
| `rank` | int | 1-100 |
| `title` | text | |
| `artist` | text | Raw credit string, not split. See DECISIONS 008 |
| `last_week` | int or null | Null for debuts and re-entries, since rank 0 does not exist |
| `peak` | int | Best position reached |
| `weeks_on_chart` | int | |
| `weeks_at_no_1` | int | 0 for songs that never topped the chart |

## Data sources

| Source | What it provides | Access | Constraints |
|---|---|---|---|
| Billboard | Weekly chart positions | Scraped, no official API | robots.txt permits `/charts/`; one request per week, honest User-Agent |
| MusicBrainz | Recording metadata, ISRCs, tags | Free, no key | ~1 req/sec; descriptive User-Agent required |

Collected data is not redistributed. `data/` is gitignored, so this repo holds the code that fetches the charts, not a copy of them.

## Known limitations

**Shipped**

- The parser depends on Billboard's current CSS class names, so a redesign will break it. It validates structure before extracting values and raises rather than writing bad rows, so a break fails loudly instead of producing wrong data silently.
- Six songs per week carry an extra "weeks at no. 1" column that the other 94 do not. Stat values are looked up by label rather than by position to handle this. See DECISIONS 009.
- The parser takes an explicit filename and does not yet find the most recent chart on its own.

**Planned phases**

- Mix-level duplication in MusicBrainz is resolved by heuristic, not solved. See [docs/DECISIONS.md](docs/DECISIONS.md) entry 003.
- Genre tags from MusicBrainz are sparse, often one or two votes per recording.

## Decisions

Every significant design choice is logged in [docs/DECISIONS.md](docs/DECISIONS.md) with the reasoning and the tradeoff.

## Roadmap

- **Phase 2, Enrichment:** done. Matches chart entries to MusicBrainz recordings by primary artist + title, verifying that the returned credits contain every artist Billboard listed. 91% match rate on the first chart; unmatched songs are skipped and counted by reason.
- **Phase 3, Load:** move processed and enriched CSVs into SQLite, with a chart table and a recordings table joined on recording ID.
- **Phase 4, Orchestration:** scheduling, retry handling, containerisation, and a migration from SQLite to PostgreSQL.

**Deeper enrichment, later.** The matcher currently uses only what MusicBrainz's search endpoint returns. Their lookup endpoint can also provide community genre tags, artist attributes such as country of origin and whether the act is a person or a group, and relationship data covering producers and writers. Each costs an extra API call per song, so it is probably only worth doing once the pipeline runs end to end.
