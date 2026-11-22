# Instructor audit: viw999 (Team Free Agents), Checkpoint 3

**Repo:** viw999/FIN-331-Group-Project · **Audited commit:** `b85ffd1` (2026-11-14, `main`; no commits since Checkpoint 2 on any branch) · **Seed:** 7, do analyst upgrades move prices, and does the broker matter? · **CP2 audit:** `audits/02_instructor_audit.md` (commit `b85ffd1`, on the unmerged branch `instructor-audit-cp2`)

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

Nothing has changed in the repo since Checkpoint 2. `main` is still `b85ffd1`, the commit audited at CP2, and no branch or pull request has later work. So there is no v1 to audit, and all six CP2 findings are still open, including the two Blocking ones (missing required files; nothing runs without your FMP key).

The pipeline code is still a reasonable start. The dashboard launches, but it shows no results. The single most useful step before Dec 1 is the same as at CP2: commit the raw FMP pulls so the pipeline runs for anyone (CP2 A2). Then produce the full-sample results.

## Follow-up on your Checkpoint 2 audit

Response file: not found. The statuses below come from the repo itself.

| CP2 finding | Status | Evidence |
|---|---|---|
| A1 · Required Checkpoint 2 files are missing | unaddressed | Same commit as CP2. `audits/01_self_audit.md`, `STATUS.md` and `specs_tried.md` still don't exist on `main` or any ref |
| A2 · Nobody without your FMP key can run anything | unaddressed | `python run_all.py` on a clean export of `b85ffd1`: exit 1 in 0.1 s, "There are no saved downloads in data/raw/ and no FMP key in a file called .env, so nothing can be built." |
| A3 · Main measure isn't the question in `PROPOSAL.md` | unaddressed | `analyze_events.py` and `PROPOSAL.md` are unchanged since CP2 |
| A4 · Dates without times | unaddressed | No timestamped match table in the repo |
| A5 · Today's 25 largest firms applied back to 2010 | unaddressed | `build_dataset.py:41-42` is unchanged |
| A6 · Keys and merges unchecked; market return excludes dividends | unaddressed | `git grep -n "validate="` on `b85ffd1` finds nothing in `build_dataset.py` |

**0 of 6 fixed, 6 still open.**

## Checkpoint 3 checks

| Check | Result |
|---|---|
| Reruns from scratch (full sample) | ❌ `run_all.py` stops at once (A2). There are no outputs to compare |
| Inputs have provenance | ⚠️ unchanged since CP2 (A2) |
| Keys unique, merges validated | ⚠️ unchanged (A6) |
| No look-ahead / survivorship | ⚠️ unchanged (A5) |
| LLM leakage handled | n/a |
| `specs_tried.md` complete | ❌ missing (A1) |
| Magnitudes discussed | ❌ no results committed |
| Hand checks | ⚠️ `build_events.self_check()` on a made-up stock only (CP2) |
| Threats to validity | ❌ no README section |
| Every number traces to `outputs/` | ❌ `outputs/` is not committed |
| Dashboard matches `outputs/` | ❌ shows no results (B2) |

Steps not rerun by design: none. The run stops because the FMP downloads aren't in the repo and no key is available here.

## Getting ready for Dec 1

Presentations run only from URLs, with a hard cutoff at 9 minutes (10:45 section) or 10 minutes (12:10 section). Put your URL(s) in column G of the Team Projects sheet.

| Check | Result |
|---|---|
| Dashboard launches from a clean clone | ✅ `streamlit run app.py --server.headless true --server.port 8604` (venv from `requirements.txt`): `/_stcore/health` returned `ok` after 3 s, with no exceptions on the page or in the log |
| Dashboard shows the v1 numbers from `outputs/` | ❌ the Results page says "Results will appear after the data pipeline runs." (`app.py:63-65`), and Explore says "Interactive event data will be added when the processed results are available." (`app.py:83-86`) |
| README links the live URL(s) | ❌ no live URL in `README.md` |

**Core story for 9–10 minutes:** GS vs MS vs JPM abnormal returns for upgrades and downgrades, with confidence intervals, and the confound split (changes near earnings vs not). Everything else is backup.

## What holds up

- The pipeline's structure (`build_dataset.py` → `build_events.py` → `analyze_events.py` → `make_report.py`) ran end to end on synthetic data at CP2, and `build_events.self_check()` passes.
- `run_all.py` fails safely, with a clear message, rather than producing partial outputs.

## New findings

### B1 · Blocking · No work since Checkpoint 2, so there is no v1

**Evidence:** `git log --all --since=2026-11-15` lists only the instructor's CP2 audit commit (`95c7fc1`, on `instructor-audit-cp2`). `main` at the CP3 deadline is `b85ffd1`, the CP2 audited commit (`git rev-list --count b85ffd1..origin/main` = 0).

**Why it matters:** Checkpoint 3 was v1 on the full sample. There are no results, so there's nothing to present on Dec 1.

**Fix:** In this order:
1. Commit the raw FMP pulls (`data/raw/`, with pull dates), so `run_all.py` runs without a key (CP2 A2).
2. Run the full sample.
3. Commit `outputs/`.
4. Add `STATUS.md`, `specs_tried.md` and `audits/01_self_audit.md` (CP2 A1).

**How to show it's fixed:** On a fresh clone with no `.env`, `python run_all.py` finishes and writes `outputs/`.

### B2 · Major · The dashboard has no results and no live URL

**Evidence:** See "Getting ready for Dec 1": the Results and Explore pages show only placeholders (`app.py:63-65, 83-86`), and `README.md` has no deployed URL.

**Why it matters:** Presentations run only from URLs.

**Fix:** After B1, have `app.py` read the tables in `outputs/` (not only PNGs). Deploy it on Streamlit Community Cloud, link it at the top of the README, and put it in column G.

**How to show it's fixed:** The deployed app shows the bank comparison from `outputs/`.

## How to respond

This audit is `audits/04_instructor_audit.md` in your repo. Fix what you can, then add `audits/05_audit_response.md`, replying to each **B** finding and to each CP2 finding still open (A1–A6): fixed (the commit), disputed (why), or disclosed as a limitation (where).

There's no separate deadline for this response. Keep working through these until your final deliverables are due: the final repo is audited again then.
