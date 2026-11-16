# Instructor audit: Team Free Agents, Checkpoint 2

**Repo:** viw999/FIN-331-Group-Project · **Audited commit:** `b85ffd1` (2026-11-14, merge of PR #3 into `main`) · **Seed:** 7, do analyst upgrades move prices, and does the broker matter?

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

The event-study code is careful. It prespecifies a main test, separates confounded events, clusters by stock, and tests itself on a made-up stock. When I fed steps 2 and 3 a synthetic dataset with effects I built in, they ran end to end, recovered those effects, and matched my own independent calculation exactly. But the Checkpoint 2 submission is incomplete, and nobody outside your laptops can check a single result. There is no self-audit, `STATUS.md`, `specs_tried.md`, threats section or dashboard link (A1). The data needs a personal FMP key, and no data, sample or output is committed (A2). Fix those two before anything else. The next most important issue: your main measure (the size of the move, ignoring direction) is not the question your `PROPOSAL.md` asks (A3).

| Check | Result |
|---|---|
| Reruns from scratch | ❌ `run_all.py` stops at once: "no saved downloads … and no FMP key" (A2). Steps 2–3 run on synthetic data |
| Inputs have provenance | ⚠️ the source (FMP endpoints) is in the code, but no pull date is recorded, and nothing is pinned or saved (A2) |
| Keys unique, merges validated | ⚠️ duplicates are dropped and counted, but there is no `assert` on (ticker, date) and no `validate=` on the five merges in `build_dataset.py` (A6) |
| No look-ahead / survivorship | ⚠️ the 25 stocks are today's large caps applied back to 2010 (A5). The estimation window ends at day −11 ✅ |
| LLM leakage handled | n/a, no LLM in the pipeline |
| `specs_tried.md` complete | ❌ missing. The `VERSIONS` list in `analyze_events.py:76-87` is a good start (A1) |
| Magnitudes discussed | ❌ no results in any committed file |
| Hand checks | ⚠️ `build_events.self_check()` passes (10 of 10 on a made-up stock). There is no check on real data |
| Threats to validity | ❌ no section. "Things to know about the data" (README) and PROPOSAL §4 cover part of it |
| Every number traces to `outputs/` | ❌ `outputs/` is not committed. The README's "About 15%" has no source file (A1, A2) |

## What holds up

- **Measurement code is right, as far as I could test it.** I wrote a synthetic `data/clean/dataset.csv`: 25 fake stocks, 750 rating changes, and an injected day-0 move of 3, 1.5 and 0 standard deviations for GS, MS and JPM. On it, `build_events.py` and `analyze_events.py` ran without error. My own code (written separately, same definitions) reproduced table 1 exactly:

  | Mean size, days −1..+1, clean events | Your `table_1_bank_comparison.csv` | Auditor | n |
  |---|---|---|---|
  | Goldman Sachs | 1.7741 | 1.7741 | 226 |
  | Morgan Stanley | 1.0160 | 1.0160 | 239 |
  | JP Morgan | 0.8647 | 0.8647 | 240 |

  The ordering matches the injected effects.
- **Your self-check works.** `build_events.self_check()` passes all 10 checks: windows not off by one, and the typical day doesn't peek at the event.
- **Seed 7, confounds:** changes from 1 day before to 2 days after earnings are flagged and left out of the "clean" main sample. So are overlaps with another of the three banks, and stocks with gaps in FMP's earnings list. Other brokers' calls are flagged, and the result is re-checked without them.
- **Seed 7, timestamps:** your main window is −1..+1 precisely because FMP has no times. Day 0 is split into overnight and intraday parts. As an outside check, yfinance's `upgrades_downgrades` for your 25 stocks lists 197 GS/MS/JPM upgrades and downgrades (2012–2026) with times of day. If those times are UTC (not verified), 186 are before 9:30 ET, 6 during market hours and 5 after the close, which supports your "mostly before the open" assumption.
- **Seed 7, few calls ranked by noise:** you compare three prespecified banks with Goldman as the base, label the main version as chosen before seeing the numbers, and cluster by stock. That is the right design.

## Findings

### A1 · Blocking · Required Checkpoint 2 files are missing

**Evidence:**
- No `audits/01_self_audit.md`, `STATUS.md` or `specs_tried.md` exists on any branch. I checked every commit with `git ls-tree` across all branches and PRs.
- `README.md` has no "threats to validity" section and no dashboard link.
- `PROPOSAL.md:56` and `:58` still hold the template placeholders "[Insert 3–5 actual rows …]" and "[confirm final date from dataset]".

**Why it matters:** These are the Checkpoint 2 deliverables. Without the self-audit and the specs log, there's no record of what you checked or tried.

**Fix:**
- Add `audits/01_self_audit.md`: run the Skeptical review prompt and record the result item by item.
- Add `STATUS.md` and `specs_tried.md`. List every row of `VERSIONS` and every setting you changed, with dates.
- Add a "Threats to validity" section to the README (much of it can come from "Things to know about the data"), and the dashboard URL.
- Fill in the PROPOSAL placeholders.

**How to show it's fixed:** The auditor will check that each file exists on `main` and that `specs_tried.md` matches `VERSIONS` and the SETTINGS blocks.

### A2 · Blocking · Nobody without your FMP key can run or check anything

**Evidence:**
- `run_all.py` in a fresh clone (Python 3.12, `requirements.txt` installed) exits with code 1 in 0.07 s: "There are no saved downloads in data/raw/ and no FMP key in a file called .env, so nothing can be built."
- `.gitignore` excludes `data/raw/*`, `data/clean/` and `outputs/`, so no data, sample or result is committed.
- Numbers in the code and README, such as "About 15% of the banks' clean rating changes have another broker's … within a day" (README) and "all 5 pairs are one trading day apart" (`build_events.py:162`), come from a local "November 2026 build" that isn't in the repo.
- The dashboard's Results page reads `outputs/*.png` (`app.py:52-64`), so a deployed copy shows "Results will appear after the data pipeline runs."

**Why it matters:** Checkpoint 2 requires the pipeline to run end to end for an outside auditor, and every number shown must trace to `outputs/`. Today the results can't be reproduced or checked.

**Fix:** Pick one, and say which in the README.
- (a) Switch the ratings and prices to yfinance (`yf.Ticker(t).upgrades_downgrades`, the seed's suggested source, which also has times of day) so anyone can run it.
- (b) Keep FMP, but do what seed 15 does with private data: commit a small **fake** `dataset.csv` with the same columns, so `run_all.py` runs without a key. Ask Prof. Bowen whether aggregated outputs (tables 1–5 hold averages, not FMP rows) may be committed.

Either way, record a pull date for each download.

**How to show it's fixed:** The auditor will clone fresh, run `python run_all.py` with no key, and expect it to finish and write `outputs/`.

### A3 · Major · The main measure (move size, either direction) isn't the question in `PROPOSAL.md`

**Evidence:**
- `PROPOSAL.md:96`, `:98` and `:146` ask whether GS upgrades lead to larger **positive**, and GS downgrades to larger **negative**, abnormal returns, using CAR(−1,+1).
- The main result is `scar_3day` turned into a size by taking its absolute value (`analyze_events.py:16-19`, `:76`). A GS upgrade followed by a −5% move therefore counts as a large reaction to Goldman.
- The signed version exists only in table 4 ("did the stock move the way the bank said?"), and it uses plain tests that treat every event as independent (`analyze_events.py:326`).

**Why it matters:** With size as the outcome, any unscreened news inside the window (a lawsuit, a macro day) counts as the bank's influence. A bank whose calls happen to land on volatile days looks influential. Proposal and code also disagree on what the project tests.

**Fix:** Choose the main outcome before seeing the real-data results, and write the choice and the reason in `specs_tried.md`. The natural choice for the proposal's question is the signed move in the call's direction (`direction × SCAR[−1,+1]`), compared across banks with the same stock-clustered test you already use. Keep size as a robustness check. Then make `PROPOSAL.md` and the README say the same thing.

**How to show it's fixed:** Table 2's main row uses the outcome named in `PROPOSAL.md`, and `specs_tried.md` records the choice.

### A4 · Minor · Dates without times: check FMP's dates against a timestamped source

**Evidence:**
- FMP's `grades` endpoint gives dates only (`build_dataset.py:141-143`). Your own docstring says "some dates are a day off, more often for one bank than another" (`analyze_events.py:29-30`). The README records wrong FMP earnings dates (WFC 2017/2018, WMT 2010/2011), which would let earnings-day events count as "clean".
- yfinance lists the same banks' calls with times (see "What holds up").

**Why it matters:** This is the timestamp item on this seed's audit list. The −1..+1 window protects the main result, but your day-0 version and the earnings filter depend on the dates being right.

**Fix:** Match FMP's GS/MS/JPM rating changes to yfinance's by stock, bank and direction within ±3 days. Report the hit rate and the share with a date difference, by bank. Use the yfinance time to place day 0 where it disagrees. Hand-check the earnings dates of 10 clean events against the companies' press releases.

**How to show it's fixed:** A match table in `outputs/` with hit rates by bank, and the hand check in the self-audit.

### A5 · Minor · The 25 stocks are today's largest firms, applied back to 2010

**Evidence:** `build_dataset.py:41-42` lists today's mega caps, including PLTR (listed in 2020) and NVDA. Prices start in 2010 (`START`).

**Why it matters:** Choosing stocks by where they ended up (survivorship) selects winners and the most-covered firms. Over a 3-day window the bias in the average is small, but the sample is not "large stocks at the time", and coverage by the three banks may differ across these firms.

**Fix:** Either pick the 25 by market cap at the start of each year, or keep the list and state the selection rule and its consequence in the threats section.

**How to show it's fixed:** The README states the rule, and the code applies it.

### A6 · Minor · Keys and merges aren't checked, and the market return excludes dividends

**Evidence:**
- `build_dataset.py:277, 284, 296, 302, 309` merge on `date` or (`ticker`, `date`) with no `validate=`, and there is no `assert` that `dataset.csv` is unique on (`ticker`, `date`).
- `build_dataset.py:121-123` uses the S&P 500 price index (no dividends) as the market while stock returns are dividend-adjusted. So the abnormal return on a stock's ex-dividend day is off by the index's dividend yield for that day. Today this is noted only in a code comment.

**Fix:** Add `validate="many_to_one"` or `"one_to_one"` to each merge, and `assert not data.duplicated(["ticker","date"]).any()` before saving. Use a total-return proxy for the market (for example SPY adjusted closes), or note the dividend mismatch in the threats section.

**How to show it's fixed:** The auditor will grep for `validate=` and the assert, and rerun.

## How to respond

This audit is `audits/02_instructor_audit.md` in your repo. Fix what you can, then add `audits/03_audit_response.md`, replying to each finding ID: fixed (the commit), disputed (why), or disclosed as a limitation (where).

**Deadline: Saturday, November 21, 2026.**
