# FIN-331-Group-Project: Team Free Agents

FIN 331 group project. Question: do upgrades and downgrades from Goldman Sachs produce larger
abnormal stock returns than those from Morgan Stanley or JPMorgan (Womack 1996)?

## The pipeline: one command

```bash
python run_all.py
```

rebuilds everything from scratch, in four steps. Each step is its own script and can also be run on its own.
After changing a setting or pulling new code, run `python run_all.py`: a single step re-uses the files the earlier steps made.

| Step | Script | What it does | What it writes |
|---|---|---|---|
| 1 | `build_dataset.py` | Downloads prices, analyst ratings and earnings dates from FMP and merges them | `data/raw/` (the downloads, saved as tables) and `data/clean/dataset.csv` |
| 2 | `build_events.py` | Lists every upgrade and downgrade by the three banks and measures the stock's move around it | `data/clean/events.csv`, `event_days.csv`, `ordinary_days.csv` |
| 3 | `analyze_events.py` | Compares the banks: averages, confidence intervals, tests, a regression | `outputs/table_1` ... `table_5` (.csv) |
| 4 | `make_report.py` | Draws the figures and writes the findings in plain words | `outputs/report.txt`, `outputs/figure_1_event_study.png`, `outputs/figure_2_bank_comparison.png` |

**Read `outputs/report.txt` first.** It starts with the caveats, then answers the project's questions in plain
sentences, then shows the tables, and ends with a paper trail of every place where data was left out, changed or
flagged (also saved as `logs/data_changes.csv`).

* Every run deletes the `.csv`, `.png` and `.txt` files in `data/clean/`, `outputs/` and `logs/` and builds them
  again. Do not keep hand-made files there.
* The downloads in `data/raw/` are re-used if they exist, so a second run does not call FMP and gives exactly the
  same numbers. On a new computer `data/raw/` is empty, so the first run downloads everything (76 requests;
  FMP's free plan allows 250 a day).
* `python run_all.py --fresh` deletes the saved downloads too and downloads everything again. The numbers can
  then change, because FMP adds new days and sometimes revises its ratings history.
* Everything you might want to change is in the SETTINGS block at the top of each script.

## Set up

Needs Python 3.12 or newer (check with `python --version`).

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Every teammate needs their own free FMP key (sign up at financialmodelingprep.com). Copy `.env.example`
to a new file called `.env` next to the scripts and paste your key in (never share it or commit it):

```
FMP_API_KEY=your_key_here
```

Make `.env` by copying `.env.example`. Do not create it with `echo ... > .env` in PowerShell: that saves it in an
encoding Python cannot read.

## The dataset (step 1)

`build_dataset.py` builds **one table**, `data/clean/dataset.csv`: a row for every trading day of 25 large stocks,
with the stock's prices, the S&P 500's prices, the days when **Goldman Sachs, Morgan Stanley or JPMorgan changed
their rating** of that stock, the days the company announced earnings, and how many rating changes by other
brokers FMP lists that day. It prints how many rating changes each bank made and stops if any went missing.

## The columns

| Column | Meaning |
|---|---|
| `ticker`, `date` | stock and trading day |
| `adj_open`, `adj_close`, `volume` | open, close and volume. Prices are corrected for splits and dividends |
| `ret` | the stock's return: today's close / yesterday's close - 1 |
| `sp500_open`, `sp500_close`, `sp500_ret` | the same for the S&P 500 index |
| `gs_change`, `ms_change`, `jpm_change` | `Upgrade` or `Downgrade` if that bank changed its rating of the stock that day, blank otherwise |
| `gs_from` / `gs_to` (and `ms_`, `jpm_`) | the rating before and after, in the bank's own words |
| `earnings` | `Yes` on a day the company announced quarterly earnings, blank otherwise |
| `other_changes` | how many upgrades or downgrades by brokers other than the three banks FMP lists for the stock that day (0 = none). FMP often lists one change twice, under two spellings of the broker's name, so 2 does not always mean two brokers |

## What to change

Everything you might edit is in the SETTINGS block at the top of each script. In `build_dataset.py`:
the `STOCKS` list, the first date, and the word-to-level table that decides what counts as an upgrade or
downgrade (Positive > Neutral > Negative; Buy to Strong Buy is not a change). To go further back than the saved
downloads, change `START` and run `python run_all.py --fresh`. In `build_events.py`: the rules for repeats,
overlaps and earnings, and the run-up and drift days. The number of banks (three) and the two main windows
(day 0 and days -1..+1) are fixed: the report is worded for them, and the scripts stop with a message if the number
of banks or a main window is changed.

## Things to know about the data

* **Dates only.** FMP gives the day of each rating, not the time. Most ratings come out before the open,
  so the change normally shows up in that day's return. A rating dated on a weekend or holiday is moved to
  the next trading day (the script counts these).
* **FMP can list a change twice** on consecutive days. The dataset keeps what FMP lists; step 2 counts such a pair
  once and keeps the later date.
* **Other brokers change ratings too.** About 15% of the banks' clean rating changes have another broker's upgrade
  or downgrade within a day. Step 2 flags them and step 3 re-checks the main result without them.
* **A few earnings dates are wrong.** FMP lists Wells Fargo's January 2017 and January 2018 announcements on 1 March,
  and Walmart's February 2010 and February 2011 announcements on 30 March. Step 2 notices a missing earnings date
  (none in the 100 trading days before a rating change) but cannot notice a wrong one.
* **Some changes are missing from FMP.** A "from" rating sometimes does not match the bank's previous "to" rating.
* **Earnings dates have no time of day either.** Many companies report after the close, so the stock reacts on the
  next trading day. Step 2 therefore treats a rating change dated from 1 trading day before to 2 after an earnings
  date as "near earnings" and keeps it out of the main results.
* **Terms of use.** FMP's free plan is for personal use and bars sharing the data. That is why `data/` and `.env`
  are not in this repo: each teammate builds their own `dataset.csv` with their own key. Do not commit or post the data.
  `outputs/` is not in the repo either: the tables, figures and report are built from the same data, and
  `report.txt` names a few single events. Run `python run_all.py` to make your own copy.
