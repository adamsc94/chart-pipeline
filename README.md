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
| `rank` | int | 1–100 |
| `title` | text | |
| `artist` | text | Raw credit string, not split. See DECISIONS
