"""Survey artist credit strings across all processed charts.

Throwaway inspection script, not part of the pipeline. Tells us how big the
artist-splitting problem is before we decide how much effort it deserves.
"""

import csv
from collections import Counter
from pathlib import Path

PROCESSED_DIR = Path("data/processed")

# " X " keeps its spaces so it doesn't match the letter x inside words
SEPARATORS = ["Featuring", "With", "&", ",", " X ", " x "]


def load_artists():
    """Read the artist column out of every CSV in data/processed/."""
    artists = []
    for path in sorted(PROCESSED_DIR.glob("*.csv")):
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                artists.append(row["artist"])
    return artists


if __name__ == "__main__":
    artists = load_artists()

    # Dedupe: the same artist charts across many weeks and often with several
    # songs at once. Each distinct string is one matching problem to solve.
    unique = sorted(set(artists))
    print(f"{len(artists)} rows, {len(unique)} distinct artist strings\n")

    # Counts deliberately overlap - "Karol G With Judeline & rusowsky" has both
    # "With" and "&" - because knowing which separators co-occur matters.
    counts = Counter()
    for a in unique:
        for sep in SEPARATORS:
            if sep in a:
                counts[sep] += 1

    print("Strings containing each separator (distinct strings):")
    for sep, n in counts.most_common():
        print(f"  {sep!r:14} {n}")

    # The headline number: how many artist strings are not simple
    multi = [a for a in unique if any(s in a for s in SEPARATORS)]
    print(f"\n{len(multi)} of {len(unique)} distinct strings contain a separator")

    # The counts say how big the problem is; the list shows which cases are hard
    print("\nAll strings with separators:")
    for a in sorted(multi):
        print(" ", a)