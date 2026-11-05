# FIN-331-Group-Project: Team Free Agents

FIN 331 group project. Question: do upgrades and downgrades from Goldman Sachs produce larger
abnormal stock returns than those from Morgan Stanley or JPMorgan (Womack 1996)?

## Analyst rating changes and stock prices: one dataset

`build_dataset.py` builds **one table**: a row for every trading day of 25 large stocks, with
the stock's prices, the S&P 500's prices, and the days when **Goldman Sachs, Morgan Stanley or
JPMorgan changed their rating** of that stock.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Every teammate needs their own free FMP key (sign up at financialmodelingprep.com). Copy `.env.example`
to a new file called `.env` next to the script and paste your key in (never share it or commit it):

```
FMP_API_KEY=your_key_here
```

```bash
python build_dataset.py
```

Output: `data/clean/dataset.csv`. The script prints how many rating changes each bank made and
confirms none went missing. Downloads are saved in `data/raw/` and re-used; set `REFRESH = True`
at the top of the script to download again.

## The columns

| Column | Meaning |
|---|---|
| `ticker`, `date` | stock and trading day |
| `adj_open`, `adj_close`, `volume` | open, close and volume. Prices are corrected for splits and dividends |
| `ret` | the stock's return: today's close / yesterday's close - 1 |
| `sp500_open`, `sp500_close`, `sp500_ret` | the same for the S&P 500 index |
| `gs_change`, `ms_change`, `jpm_change` | `Upgrade` or `Downgrade` if that bank changed its rating of the stock that day, blank otherwise |
| `gs_from` / `gs_to` (and `ms_`, `jpm_`) | the rating before and after, in the bank's own words |

## What to change

Everything you might edit is in the SETTINGS block at the top of `build_dataset.py`:
the `STOCKS` list, the banks, the first date, and the word-to-level table that decides what
counts as an upgrade or downgrade (Positive > Neutral > Negative; Buy to Strong Buy is not a change).

## Things to know about the data

* **Dates only.** FMP gives the day of each rating, not the time. Most ratings come out before the open,
  so the change normally shows up in that day's return. A rating dated on a weekend or holiday is moved to
  the next trading day (the script counts these).
* **FMP can list a change twice** on consecutive days. We keep what FMP lists. Check for repeats before you count events.
* **Some changes are missing from FMP.** A "from" rating sometimes does not match the bank's previous "to" rating.
* **Terms of use.** FMP's free plan is for personal use and bars sharing the data. That is why `data/` and `.env`
  are not in this repo: each teammate builds their own `dataset.csv` with their own key. Do not commit or post the data.
