"""Run the full pipeline: fetch, parse, enrich, load.

Each stage hands its output path to the next, so no filenames are typed.
"""

import logging
import sys

from enrich.match_recordings import enrich_and_write
from ingest.fetch_chart import fetch_chart
from ingest.parse_chart import parse_and_write
from load.load_db import load_chart

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)

logger = logging.getLogger(__name__)

def main():
    logger.info("[1/4] Fetching chart")
    raw_path = fetch_chart()

    logger.info("[2/4] Parsing")
    processed_path = parse_and_write(raw_path)

    logger.info("[3/4] Enriching with MusicBrainz")
    enrich_and_write(processed_path)

    logger.info("[4/4] Loading into Postgres")
    load_chart(processed_path.name)

    logger.info("Pipeline complete: %s", processed_path.name)
    # Clement: What is %s

if __name__ == "__main__":
    main()