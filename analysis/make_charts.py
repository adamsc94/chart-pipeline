"""Run the findings queries and save one chart per finding.

Each finding has a .sql file in this folder. This script runs the three that
feed a chart and writes a PNG for each into analysis/charts/.

    pip install -r analysis/requirements.txt
    python analysis/make_charts.py

Needs DATABASE_URL in .env, the same one the pipeline uses. The connection is
opened read-only, so nothing here can change the data.
"""

import os
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files, no window needed

import matplotlib.pyplot as plt
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ANALYSIS_DIR = Path(__file__).resolve().parent
CHARTS_DIR = ANALYSIS_DIR / "charts"

# One small palette for all three charts.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3de"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
GREY = "#a3a29b"

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": MUTED,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": INK,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
    }
)


# --- database -------------------------------------------------------------


def run_query(conn, filename):
    """Run one .sql file from this folder and return its rows as dicts."""
    sql = (ANALYSIS_DIR / filename).read_text(encoding="utf-8")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        return cur.fetchall()


# --- shared helpers -------------------------------------------------------


def week_positions(chart_dates):
    """Place chart weeks on the x axis by real date, one unit per week.

    A missing week leaves an empty slot, so the gap in the data shows up as a
    gap in the chart and the weeks either side are not drawn as neighbours.
    """
    days = sorted({date.fromisoformat(d) for d in chart_dates})
    return {d.isoformat(): (d - days[0]).days / 7 for d in days}


def label_weeks(ax, positions):
    """Label collected weeks on the x axis and mark any gap as 'no data'."""
    ax.set_xticks(list(positions.values()))
    ax.set_xticklabels(
        [f"{date.fromisoformat(d):%b} {date.fromisoformat(d).day}" for d in positions]
    )
    ax.grid(axis="x", visible=False)

    slots = sorted(positions.values())
    for left, right in zip(slots, slots[1:]):
        if right - left > 1:
            ax.axvspan(left + 0.5, right - 0.5, color=GRID, alpha=0.5, linewidth=0)
            ax.text(
                (left + right) / 2,
                0.5,
                "no data",
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="center",
                color=MUTED,
                fontsize=9,
            )


def unbroken_runs(points):
    """Split (x, y) points into runs of consecutive weeks.

    Lines are drawn one run at a time so no line crosses the gap and implies
    values for weeks that were never collected.
    """
    runs, current = [], [points[0]]
    for point in points[1:]:
        if point[0] - current[-1][0] > 1:
            runs.append(current)
            current = []
        current.append(point)
    runs.append(current)
    return runs


def save(fig, filename):
    path = CHARTS_DIR / filename
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path.relative_to(ANALYSIS_DIR.parent)}")


# --- finding 1: collaborations --------------------------------------------


def chart_collaborations(rows):
    positions = week_positions(r["chart_date"] for r in rows)
    collab = {r["chart_date"]: r for r in rows if r["credit_type"] == "collaboration"}
    solo = {r["chart_date"]: r for r in rows if r["credit_type"] == "solo"}

    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 4.2))

    # Left: how many of the 100 slots are collaborations.
    for chart_date, x in positions.items():
        slots = collab[chart_date]["chart_slots"]
        left.bar(x, slots, width=0.7, color=BLUE)
        left.text(x, slots + 0.6, str(slots), ha="center", va="bottom")
    left.set_ylim(0, 30)
    left.set_ylabel("Songs out of 100")
    left.set_title("Collaborations on the chart each week")
    label_weeks(left, positions)

    # Right: where each group sits on the chart, on the full 1-100 scale.
    for group, colour, name in ((solo, GREY, "Solo"), (collab, BLUE, "Collaborations")):
        points = [(x, float(group[d]["median_rank"])) for d, x in positions.items()]
        for run in unbroken_runs(points):
            xs, ys = zip(*run)
            right.plot(xs, ys, color=colour, linewidth=2, marker="o", markersize=6)
        right.plot([], [], color=colour, linewidth=2, marker="o", markersize=6, label=name)
    right.set_ylim(100, 1)
    right.set_yticks([1, 25, 50, 75, 100])
    right.set_ylabel("Median chart position")
    right.set_title("Typical position, solo vs. collaborations")
    right.legend(frameon=False, loc="lower left")
    label_weeks(right, positions)

    fig.tight_layout(w_pad=3)
    save(fig, "01_collaborations.png")


# --- finding 2: song length -----------------------------------------------

TYPICAL_RANGE = (150, 240)  # 2:30 to 4:00, in seconds


def minutes_label(seconds, _position=None):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def chart_song_length(rows):
    lengths = [float(r["length_seconds"]) for r in rows]
    peaks = [r["peak"] for r in rows]
    low, high = TYPICAL_RANGE
    share = sum(low <= s <= high for s in lengths) / len(lengths)

    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.axvspan(low, high, color=BLUE, alpha=0.08, linewidth=0)
    ax.scatter(lengths, peaks, s=34, color=BLUE, alpha=0.75, edgecolor=SURFACE, linewidth=0.8)
    ax.text(
        (low + high) / 2,
        1.02,
        f"{share:.0%} of songs run {minutes_label(low)} to {minutes_label(high)}",
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="bottom",
        color=MUTED,
        fontsize=9,
    )

    ax.set_ylim(103, -2)
    ax.set_yticks([1, 25, 50, 75, 100])
    ax.set_xticks(range(90, int(max(lengths)) + 31, 60))
    ax.xaxis.set_major_formatter(minutes_label)
    ax.set_xlabel("Song length (minutes:seconds)")
    ax.set_ylabel("Peak chart position")
    ax.set_title(f"Song length vs. peak position, {len(rows)} songs", pad=22)

    save(fig, "02_song_length.png")


# --- finding 3: re-entries ------------------------------------------------

LABEL_UP_TO_RANK = 50  # name the re-entries that landed in the top half
LABEL_SPACING = 6  # minimum gap between stacked labels, in chart positions


def chart_reentries(rows, all_chart_dates):
    positions = week_positions(all_chart_dates)
    last_week = max(positions.values())

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axhspan(-2, 40.5, color=ORANGE, alpha=0.07, linewidth=0)
    ax.text(
        last_week + 2.9, 3, "Top 40", ha="right", va="top", color=MUTED, fontsize=9
    )

    for chart_date, x in positions.items():
        week = sorted((r for r in rows if r["chart_date"] == chart_date), key=lambda r: r["rank"])
        named = [r for r in week if r["rank"] <= LABEL_UP_TO_RANK]
        others = [r for r in week if r["rank"] > LABEL_UP_TO_RANK]

        ax.scatter([x] * len(others), [r["rank"] for r in others], s=42, color=GREY,
                   edgecolor=SURFACE, linewidth=0.8, zorder=3)
        ax.scatter([x] * len(named), [r["rank"] for r in named], s=54, color=ORANGE,
                   edgecolor=SURFACE, linewidth=0.8, zorder=3)

        # Labels go right of the dot, except in the second-to-last week,
        # where they go left so they don't run into the last week's dots.
        to_left = x == last_week - 1
        label_y = None
        for r in named:
            label_y = r["rank"] if label_y is None else max(r["rank"], label_y + LABEL_SPACING)
            ax.annotate(
                f"{r['title']} (#{r['rank']})",
                xy=(x, r["rank"]),
                xytext=(x - 0.18 if to_left else x + 0.18, label_y),
                ha="right" if to_left else "left",
                va="center",
                fontsize=8.5,
            )

    ax.set_xlim(-0.6, last_week + 3)
    ax.set_ylim(103, -2)
    ax.set_yticks([1, 20, 40, 60, 80, 100])
    ax.set_ylabel("Chart position on re-entry")
    ax.set_title("Where returning songs re-entered the Hot 100, by chart week")
    label_weeks(ax, positions)

    save(fig, "03_reentries.png")


# --- main -----------------------------------------------------------------


def main():
    load_dotenv()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL in .env")

    CHARTS_DIR.mkdir(exist_ok=True)

    with psycopg.connect(database_url) as conn:
        conn.read_only = True  # analysis only reads; let Postgres enforce it

        collaborations = run_query(conn, "01_collaborations.sql")
        song_lengths = run_query(conn, "02_song_length.sql")
        reentries = run_query(conn, "03_reentries.sql")

    chart_collaborations(collaborations)
    chart_song_length(song_lengths)
    # The collaborations query returns every collected week, which the
    # re-entry chart needs so a week with no re-entries still gets a slot.
    chart_reentries(reentries, [r["chart_date"] for r in collaborations])


if __name__ == "__main__":
    main()
