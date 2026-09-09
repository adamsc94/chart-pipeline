# Decision Log

One entry per real decision. Written at the time it was made, not reconstructed later.

Format: what I decided, why, what I gave up, and what would change my mind.

---

## 001 — Source: MusicBrainz + Billboard, not Spotify

**Decided:** Pull chart data from Billboard and enrich it with MusicBrainz metadata. Do not build on the Spotify Web API.

**Why:** Spotify deprecated `audio_features` and `audio_analysis` in November 2024 with no replacement, and only apps with a quota extension pending before that date still have access. February 2026 changes tightened things further — the account registering a developer app now needs an active Premium subscription, and development-mode apps are capped at five authorised listeners. A portfolio project built on that has a good chance of breaking or being un-runnable by anyone reviewing it.

**Gave up:** Tempo, key, energy, danceability, valence. Any question about the musical character of a track is off the table unless I compute it myself from audio.

**Would change my mind:** Spotify reopening those endpoints, or finding an open dataset with comparable per-track features and real coverage of current charts.

---

## 002 — Grain: one row per recording

**Decided:** The fact table is one row per MusicBrainz recording (MBID as the key), not per release or per track-on-a-release.

**Why:** A single recording appears on many releases — "Naked in Manhattan" showed up across roughly twenty, including CD, cassette, four vinyl variants, a Portuguese Pride compilation, and an Urban Outfitters pink edition. Those are the same performance and people think of them as the same song. Release grain would multiply every song by its pressing count. Recording grain also gives one authoritative `length`; the per-release track lengths disagree with each other (211053 / 211057 / 211058 / 211000 for the same recording).

**Gave up:** Anything about physical formats, regional release dates, or pressing variants. If I later want "how many vinyl variants does a charting album get," I'd need release grain.

**Known problem:** Recording grain is *not* one row per song. See 003.

---

## 003 — The mix-duplication problem, and the rule I chose

**Problem:** The same performance exists as multiple recordings with different MBIDs and different ISRCs — standard, "Dolby Atmos mix, clean", "Dolby Atmos mix, explicit". "Naked in Manhattan" alone has at least two recording IDs (`5372a62a…` / ISRC `QM24S2200264`, and `a04ab22a…` / ISRC `USUG12307526`). Nothing in the data says which one Billboard is counting.

**Decided:** Drop any recording with no ISRC, then among the survivors matching a given title + artist, keep the one with the earliest `first-release-date`.

**Why:** ISRCs are assigned on commercial distribution, so their absence is a reasonable proxy for "not a commercial release." Earliest release date favours the original over an Atmos remaster issued later.

**Gave up / known error:** This is a heuristic, not a solution. It will pick wrong when a song genuinely re-charts in a remixed form. I have not measured the error rate. Doing so would mean hand-labelling a sample of charting titles and scoring the rule against them — worth doing before claiming any precision.

---

## 004 — Filtering out live and bootleg recordings

**Decided:** Filter using `status`, `secondary-types`, and presence of `isrcs`. Do **not** filter on `disambiguation`.

**Why:** `disambiguation` is free text entered by volunteers and is populated inconsistently. The Lollapalooza 2024 "Red Wine Supernova" recording has *no* disambiguation value at all, while legitimate studio recordings have values like "Dolby Atmos mix, clean". Filtering on it would let bootlegs through and drop good rows. The structured fields agree with each other on the same record: `status: "Bootleg"`, `secondary-types: ["Live"]`, and no `isrcs` array.

**Secondary sanity check:** Live versions run noticeably longer — studio "Red Wine Supernova" is 193000 ms, the Lollapalooza recording is 233180 ms. Useful for spotting leaks, not reliable enough to filter on.

---

## 005 — Do not trust the `score` field

**Decided:** Ignore `score` entirely when deciding whether a match is correct.

**Why:** Every result in a query that returned entirely wrong artists (jasmine.4.t, The Donegal X-Press, 5uu's, Void — none of them Chappell Roan) scored 100. Score measures how well a record matches the query string, not whether the query was right. A confidently wrong join is worse than an obviously wrong one.

**Instead:** Validate matches against the artist MBID and ISRC where available.

---

## 006 — Query syntax gotcha (not a decision, but a trap worth recording)

MusicBrainz search uses Lucene syntax. `artist:Chappell Roan` parses as `artist:Chappell` plus a bare term `Roan` against the default field — which for the recording endpoint is the title. That query returned 2,893 songs *named* "Roan". The fix is to quote the phrase: `artist:"Chappell Roan"`, which returned 150.

When calling from Python, `requests` handles URL encoding — pass `'artist:"Chappell Roan"'` as a param value and don't hand-encode.

---

<!-- Next entry goes here. Add one whenever you make a real choice, especially one you rejected an alternative for. -->
