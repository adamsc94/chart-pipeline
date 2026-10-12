"""Run the full pipeline: fetch, parse, enrich, load.

Each stage hands its output path to the next, so no filenames are typed.
"""

import sys

from enrich.match_recordings import enrich_and_write
from ingest.fetch_chart import fetch_chart
from ingest.parse_chart import parse_and_write
from load.load_db import load_chart


def main():
    print("[1/4] Fetching chart", file=sys.stderr)
    raw_path = fetch_chart()

    print("[2/4] Parsing", file=sys.stderr)
    processed_path = parse_and_write(raw_path)

    print("[3/4] Enriching with MusicBrainz", file=sys.stderr)
    enrich_and_write(processed_path)

    print("[4/4] Loading into Postgres", file=sys.stderr)
    load_chart(processed_path.name)

    print(f"\nPipeline complete: {processed_path.name}", file=sys.stderr)


if __name__ == "__main__":
    main()