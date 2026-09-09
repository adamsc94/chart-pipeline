# Chart Pipeline

<!-- ONE SENTENCE. What this does and what question it answers. Write it last, rewrite it often. -->
A scheduled pipeline that ingests Billboard chart data, enriches it with MusicBrainz metadata, and loads it into a queryable store.

**Status:** in development

---

## The question

<!-- What are you actually trying to find out? Be specific enough that you'd know if you failed. -->

TODO

## Architecture

<!-- Diagram goes here once phase 1 runs. Mermaid renders natively on GitHub - see docs/ for a starter. -->

TODO

## Running it

<!-- Someone should be able to clone this and get it working without asking you anything. -->

TODO

## Data sources

| Source | What it provides | Access | Constraints |
|---|---|---|---|
| Billboard | Weekly chart positions | Scraped, no official API | Check robots.txt; be polite |
| MusicBrainz | Recording metadata, ISRCs, tags | Free, no key | ~1 req/sec; descriptive User-Agent required |

## Known limitations

<!-- Be honest here. This section is a strength, not a weakness. -->

- Mix-level duplication is resolved by heuristic, not solved. See [docs/DECISIONS.md](docs/DECISIONS.md) entry 003.
- Genre tags from MusicBrainz are sparse — often one or two votes per recording.

## Decisions

Every significant design choice is logged in [docs/DECISIONS.md](docs/DECISIONS.md) with the reasoning and the tradeoff.
