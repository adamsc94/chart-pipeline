# Decision Log

One entry per real decision. Written at the time it was made, not reconstructed later.

Format: what I decided, why, what I gave up, and what would change my mind.

---

## 001 — Source: MusicBrainz + Billboard, not Spotify

**Decided:** Pull chart data from Billboard and enrich it with MusicBrainz metadata. Do not build on the Spotify Web API.

**Why:** Spotify deprecated `audio_features` and `audio_analysis` in November 2024 with no replacement, and only apps with a quota extension pending before that date still have access. February 2026 changes tightened things further: the account registering a developer app now needs an active Premium subscription, and development-mode apps are capped at five authorised listeners. A portfolio project built on that has a good chance of breaking or being un-runnable by anyone reviewing it.

**Gave up:** Tempo, key, energy, danceability, valence. Any question about the musical character of a track is off the table unless I compute it myself from audio.

**Would change my mind:** Spotify reopening those endpoints, or finding an open dataset with comparable per-track features and real coverage of current charts.

---

## 002 — Grain: one row per recording

**Decided:** The fact table is one row per MusicBrainz recording (MBID as the key), not per release or per track-on-a-release.

**Why:** A single recording appears on many releases: "Naked in Manhattan" showed up across roughly twenty, including CD, cassette, four vinyl variants, a Portuguese Pride compilation, and an Urban Outfitters pink edition. Those are the same performance and people think of them as the same song. Release grain would multiply every song by its pressing count. Recording grain also gives one authoritative `length`; the per-release track lengths disagree with each other (211053 / 211057 / 211058 / 211000 for the same recording).

**Gave up:** Anything about physical formats, regional release dates, or pressing variants. If I later want "how many vinyl variants does a charting album get," I'd need release grain.

**Known problem:** Recording grain is *not* one row per song. See 003.

---

## 003 — The mix-duplication problem, and the rule I chose

**Problem:** The same performance exists as multiple recordings with different MBIDs and different ISRCs: standard, "Dolby Atmos mix, clean", "Dolby Atmos mix, explicit". "Naked in Manhattan" alone has at least two recording IDs (`5372a62a…` / ISRC `QM24S2200264`, and `a04ab22a…` / ISRC `USUG12307526`). Nothing in the data says which one Billboard is counting.

**Decided:** Drop any recording with no ISRC, then among the survivors matching a given title + artist, keep the one with the earliest `first-release-date`.

**Why:** ISRCs are assigned on commercial distribution, so their absence is a reasonable proxy for "not a commercial release." Earliest release date favours the original over an Atmos remaster issued later.

**Gave up / known error:** This is a heuristic, not a solution. It will pick wrong when a song genuinely re-charts in a remixed form. I have not measured the error rate. Doing so would mean hand-labelling a sample of charting titles and scoring the rule against them, which is worth doing before claiming any precision.

---

## 004 — Filtering out live and bootleg recordings

**Decided:** Filter using `status`, `secondary-types`, and presence of `isrcs`. Do **not** filter on `disambiguation`.

**Why:** `disambiguation` is free text entered by volunteers and is populated inconsistently. The Lollapalooza 2024 "Red Wine Supernova" recording has *no* disambiguation value at all, while legitimate studio recordings have values like "Dolby Atmos mix, clean". Filtering on it would let bootlegs through and drop good rows. The structured fields agree with each other on the same record: `status: "Bootleg"`, `secondary-types: ["Live"]`, and no `isrcs` array.

**Secondary sanity check:** Live versions run noticeably longer: studio "Red Wine Supernova" is 193000 ms, the Lollapalooza recording is 233180 ms. Useful for spotting leaks, not reliable enough to filter on.

---

## 005 — Do not trust the `score` field

**Decided:** Ignore `score` entirely when deciding whether a match is correct.

**Why:** Every result in a query that returned entirely wrong artists (jasmine.4.t, The Donegal X-Press, 5uu's, Void; none of them Chappell Roan) scored 100. Score measures how well a record matches the query string, not whether the query was right. A confidently wrong join is worse than an obviously wrong one.

**Instead:** Validate matches against the artist MBID and ISRC where available.

---

## 006 — Query syntax gotcha (not a decision, but a trap worth recording)

MusicBrainz search uses Lucene syntax. `artist:Chappell Roan` parses as `artist:Chappell` plus a bare term `Roan` against the default field, which for the recording endpoint is the title. That query returned 2,893 songs *named* "Roan". The fix is to quote the phrase: `artist:"Chappell Roan"`, which returned 150.

When calling from Python, `requests` handles URL encoding, so pass `'artist:"Chappell Roan"'` as a param value and don't hand-encode.

---

## 007 — Download the charts page to disk, then parse it

Rather than parsing directly from the network response, download the page to disk and run the parsing step afterwards. That saves re-pulling from the server if something goes wrong, and it makes runs idempotent and reproducible. Past weeks also cannot be re-fetched once a chart rolls over, so the saved HTML is the only copy of that week that will ever exist.

The tradeoff is another file and folder to manage. I would only consider parsing directly from the response if disk space became a real constraint.

---

## 008 — Preserve the raw artist credit string; defer splitting to enrichment

Noticed that some songs have multiple credits, for example "Dracula" by Tame Impala & JENNIE. Other separators include ",", "with", "featuring", and "and", and potentially others. So for now, the parser stores the entire artist string even when it contains more than one artist. We can separate out the "main artist" later in the enrichment step.

Deferring is safe because ingestion stores the source string unmodified. If the splitting rule turns out to be wrong, I can fix it and re-run enrichment against the HTML already on disk, with no re-scraping and no risk to past weeks I can't fetch again once the chart rolls over.

Commas are the dangerous separator, since they also appear inside single artist names. "Tyler, The Creator" and "Earth, Wind & Fire" would both shatter under a naive comma split.

When I ran it, I noticed it returned "Tame Impala&JENNIE" and not "Tame Impala & JENNIE", stripping out the whitespace around the "&". After printing the raw text and the stripped text side by side with `repr()`, I found the source HTML had the spaces all along; `get_text(strip=True)` was removing them. Once I took that out and replaced it with Python's generic `.strip()`, the string was preserved. The convenience flag had silently altered the source data.

---

## 009 — Stat fields are parsed by label lookup

I started parsing by position, but added a check that the stat labels appeared where I expected them. That check fired on the first run: some songs carry an extra "WEEKS AT NO. 1" field between PEAK and WEEKS ON CHART, which would have silently shifted every value after it.

After that I switched to a label lookup, pairing each label with the value that follows it. This added a marginal amount of complexity but made the parser much more robust, and it handles both layouts without special-casing either one.

If I were reasonably confident the layout was consistent from song to song and would stay that way, I would consider switching back to positional, but only with robust validation.

Note that RANK is still positional, making this technically a hybrid. Billboard prints no label above the rank number, so there is nothing to anchor to. No validation currently covers that field.


---

## 010 — Parse with the new October layout in mind

Billboard changed their HTML layout between September 9 and October 2, and they might change it again. For simplicity's sake I'm going to build this based on the updated October layout for now, but if the layout changes again, then I might consider making a more robust parser that will work with future changes.

I found out because the label validation from 009 raised on the September file rather than parsing it wrong. Three weeks was all it took for the fragility the README warns about to actually happen.

The difference turned out to be narrow: September uses `WEEKS` where October uses `WEEKS ON CHART`, and October adds `WEEKS AT NO. 1`. Both layouts render every stat label twice, desktop and mobile, which meant my `stats` dictionary was silently overwriting each value with its duplicate. Harmless so far since the copies agree, but the parser now raises if they ever conflict.

The September file stays in `data/raw/` but doesn't get parsed. The dataset starts from the October 3 chart.

---

## 011 — Use a hosted PostgreSQL database for data storage

To enable this pipeline to run consistently and on a schedule, I decided to host the data in an online PostgreSQL database, Neon. A scheduled cloud job destroys the machine after every run, so to do week to week analysis the data has to live somewhere else. This option requires signing up for another service, but it's free at the scale of database we need.

I rejected hosting the database locally because that means relying on my laptop being awake for the job to run, and past charts can't be re-fetched once a week rolls over. I also considered simply committing the database to the repo, but rejected it since that goes against the decision not to redistribute any Billboard data. Other hosted platforms such as Supabase were considered and ruled out on their limitations: Supabase pauses free projects after about a week of inactivity, and this project is scheduled to run once a week.

If the data got substantially larger, or I didn't want to be tied to another vendor, I would consider changing this.

The migration itself was smaller than expected. `schema.sql` needed no changes at all, because I deliberately wrote standard SQL in Phase 3 rather than SQLite-specific syntax. Only `load_db.py` needed changes, and all three were mechanical: `?` placeholders became `%s`, `INSERT OR IGNORE` became `ON CONFLICT DO NOTHING`, and `INSERT OR REPLACE` became `ON CONFLICT DO UPDATE`. I knew the migration worked when the row counts came back identical to SQLite, 91 recordings after the first week and 113 after the second.

---

## 012 — Make enrichment resumable, and handle network failures

The enrichment step calls MusicBrainz once per song, so a full chart takes about four minutes. It was keeping every match in memory and writing the file only at the end, which meant any crash threw away all the work. This happened twice in one day.

Two different failures caused them. The first was a 503, MusicBrainz rate-limiting me. I'd set the delay between requests to 1.5 seconds; raising it to 2.5 stopped the 503s entirely. The retry logic I'd written was treating the symptom, where the delay addressed the cause.

The second was a read timeout, and my retry logic couldn't catch it. I was checking the response's status code, which only works if a response arrives. When a request times out there is no response. The call raises an exception and skips past the retry loop entirely. I now catch timeouts and connection errors explicitly.

Resumability is the real fix. Each matched row is written and flushed to disk immediately rather than held in memory, and on startup the script reads which ranks are already in the output file and skips them. The flush is doing real work here: without it Python buffers the writes, and a crash would lose whatever hadn't been committed yet.

Known gap: unmatched songs aren't written to the file, so a resume re-queries them. With six failures per chart that's about fifteen wasted seconds. Fixing it properly means recording failures with a status column, but I have de-prioritized this for now.

I deferred this twice before building it. It cost me two crashes and roughly seven minutes of API calls in one day, and I was about to schedule this to run unattended, where nobody would be watching to restart it.

---

## 013 — GitHub Actions running late is OK

After inspecting the job's timestamp, I noticed the job ran 5 hours and 42 minutes late.

GitHub free runners are best-effort, meaning if a higher priority job is scheduled at the same time as yours, your job will be postponed. In the case of this pipeline, a late run is inconsequential as long as it runs at some point during the week since the data only changes once a week.

If it fails to run, and the week turns over before it is caught, the data would be lost forever, and that is a bigger problem that would be worth addressing. Some options might be to run at a less-congested hour, or to schedule a second weekly run as a backup.

For now I'm accepting the delay and leaving the schedule as it is.

---
---

## 014 — Add a Dockerfile for reproducibility, but run the scheduled job without it

I built this on an older 2017 Mac, so Docker won't run on my computer. However, I still wanted a Dockerfile for a cloned repo's setup, or to run when my local environment changes in some way.

So I set up a Dockerfile and made `build.yml`, which runs on every push and verifies the image still builds. Since I can't build locally, CI is the only thing confirming the Dockerfile is valid. Note that this only proves the image builds, not that it runs: the `CMD` line is recorded during the build, never executed. Running something inside the container would be a stronger check.

`weekly.yml` runs weekly on GitHub and does the environment setup that Docker would otherwise do. No Docker is involved. This avoids a redundant build every week and saves run time.

If I wanted the scheduled run to use the container, the right way would be to build the image once, push it to a container registry, and have the weekly job pull and run it. That's more faithful to the point of containerising, but it's more machinery than a single weekly job needs right now.

---

## 015 — Break ties on recording ID so matching is reproducible

The same song was being matched to different MusicBrainz recordings in different weeks. Across four chart weeks, 17 songs had more than one recording ID, and "Petal" by Ariana Grande got a different ID every week, four in total. Because the recordings table is keyed on MBID (002), each new ID became a new row, so about 16% of that table is duplicates of songs that are already in it.

I found it in the stored data, not in the code. The same title and artist showed up under several IDs in the database. The code had no error to show. Every pick followed the rules in 003 and 004: an ISRC, full credits, and the earliest release.

The cause was the last step of `pick_match`. It takes the recording with the earliest `first-release-date`, and when several candidates share that date, `min()` returns whichever comes first in the list. That's MusicBrainz's search result order, and it changes from one call to the next. So tied recordings were effectively chosen at random, and a song that charts for several weeks got a fresh roll each week.

The fix is to use the MBID as a secondary sort key. If the dates tie, the lowest ID wins, and the same set of candidates now always gives the same answer.

This makes the match reproducible. It doesn't make it correct. The lowest MBID has no meaning. It's just a stable choice. If tied recordings really are different (an explicit and a clean version, a single edit, a re-recording), this picks one of them the same way every time, and that one may not be the version that charted. I've traded a random answer for a consistent one, and I'll only know whether it's the right one after I check some ties by hand.

What this doesn't fix:

- **The duplicates already in the database.** The fix only stops new ones. The existing rows need deduplicating, and any chart entries pointing at them need repointing to the surviving ID.
- **A changing candidate set.** The search asks for 10 results. If MusicBrainz returns a different 10 from one week to the next, the tie-break is choosing from a different pool and can still land on a different recording. A full fix would store the first ID a song is matched to and reuse it in later weeks, so a charting song never gets re-matched.
- **Mixed date precision.** Dates are compared as strings, so a year-only date like `2024` sorts before `2024-08-30`. A recording with a vague date can beat one with a precise date for the same day.

What would change my mind: if hand-checking ties shows that some other field picks the charting version (track count, release type, or the label on the release), that field should become the tie-break, with MBID as the last resort.
