"""Build ONE dataset: daily prices for 25 large stocks and the S&P 500, with the days
when Goldman Sachs, Morgan Stanley and JPMorgan changed their rating of a stock.

Run:      python build_dataset.py
Output:   data/clean/dataset.csv      one row per stock per trading day

Data comes from one provider, Financial Modeling Prep (FMP), on its free plan.
Put your key in a file called .env next to this script:   FMP_API_KEY=your_key_here

THE STEPS (each is a short function below)
  1. get_prices()         daily open, close and volume for each stock and for the S&P 500
  2. get_ratings()        every analyst rating FMP has for each stock
  3. rating_changes()     keep Goldman, Morgan Stanley and JPMorgan; keep only real upgrades/downgrades
  4. main()               merge everything into one table and save it

Downloads are saved in data/raw/ and re-used. Set REFRESH = True to download again.
"""
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# SETTINGS - change these to change the dataset
# ---------------------------------------------------------------------------
STOCKS = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "WMT", "V", "XOM", "AMD", "JNJ", "ABBV",
          "COST", "CVX", "KO", "CSCO", "PLTR", "UNH", "BAC", "GE", "INTC", "NFLX", "WFC", "DIS"]
BANKS = {"Goldman Sachs": "gs", "Morgan Stanley": "ms", "JP Morgan": "jpm"}   # FMP's spelling -> column prefix
INDEX = "^GSPC"            # the S&P 500
START = "2010-01-01"       # first day of prices
REFRESH = False            # True = ignore the saved downloads and download again

# How we turn rating words into a 3-level scale: 2 = Positive, 1 = Neutral, 0 = Negative.
# A rating CHANGE means the level moved. Buy -> Strong Buy stays at 2, so it is not a change.
# A word that is not in this list is treated as unknown (the row is skipped and counted).
GRADE_LEVEL = {
    "buy": 2, "strong buy": 2, "outperform": 2, "overweight": 2, "positive": 2, "conviction buy": 2,
    "sector outperform": 2, "market outperform": 2,
    "hold": 1, "neutral": 1, "equal-weight": 1, "equal weight": 1, "market perform": 1, "sector perform": 1,
    "in-line": 1, "in line": 1, "peer perform": 1, "perform": 1, "sector weight": 1, "market weight": 1,
    "sell": 0, "underperform": 0, "underweight": 0, "reduce": 0, "negative": 0,
    "sector underperform": 0, "market underperform": 0,
}

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
OUT = HERE / "data" / "clean"
URL = "https://financialmodelingprep.com/stable/"
load_dotenv(HERE / ".env")
KEY = os.environ.get("FMP_API_KEY", "").strip()


# ---------------------------------------------------------------------------
# Downloading (with a saved copy so a re-run does not call FMP again)
# ---------------------------------------------------------------------------
def download(endpoint, **params):
    """Ask FMP for data and return it as a list of rows."""
    if not KEY:
        sys.exit("No FMP_API_KEY found. Put FMP_API_KEY=your_key in a file called .env next to this script.")
    reply = requests.get(URL + endpoint, params={**params, "apikey": KEY}, timeout=60)
    if reply.status_code != 200:
        raise RuntimeError("FMP said HTTP %d: %s" % (reply.status_code, " ".join(reply.text.split())[:150]))
    rows = reply.json()
    if not isinstance(rows, list) or len(rows) == 0:
        raise RuntimeError("FMP returned no rows")
    time.sleep(0.4)   # be polite to the server
    return rows


def saved_or_download(path, endpoint, **params):
    """Read the saved copy if there is one, otherwise download it and save it."""
    if path.exists() and not REFRESH:
        return pd.read_csv(path)
    table = pd.DataFrame(download(endpoint, **params))
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)          # saved exactly as received
    return table


# ---------------------------------------------------------------------------
# Step 1: prices
# ---------------------------------------------------------------------------
def get_prices(ticker):
    """Daily adjusted open, close and volume. 'Adjusted' = corrected for stock splits and dividends,
    so the change from one close to the next is the real return."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()    # today's bar is not finished yet
    if ticker.startswith("^"):                                    # an index has nothing to adjust
        endpoint, open_col, close_col = "historical-price-eod/full", "open", "close"
    else:
        endpoint, open_col, close_col = "historical-price-eod/dividend-adjusted", "adjOpen", "adjClose"
    path = RAW / "fmp_prices" / (ticker.replace("^", "_") + ".csv")
    raw = saved_or_download(path, endpoint, symbol=ticker, **{"from": START, "to": yesterday})

    prices = pd.DataFrame({"date": pd.to_datetime(raw["date"]), "adj_open": raw[open_col],
                           "adj_close": raw[close_col], "volume": raw["volume"]})
    prices = prices.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    prices["ret"] = prices["adj_close"].pct_change()               # today's close / yesterday's close - 1
    return prices


# ---------------------------------------------------------------------------
# Steps 2 and 3: ratings
# ---------------------------------------------------------------------------
def get_ratings(ticker):
    """Every analyst rating FMP has for the stock: date, firm, previous grade, new grade."""
    return saved_or_download(RAW / "fmp_ratings" / (ticker + ".csv"), "grades", symbol=ticker)


def rating_changes(ratings, ticker, trading_days):
    """Keep our three banks' real upgrades and downgrades, dated on a trading day.

    Returns (changes, counts). `counts` says how many rows we skipped and why, so nothing
    disappears without being counted.
    """
    banks = ratings[ratings["gradingCompany"].isin(BANKS)].copy()
    banks["from_level"] = banks["previousGrade"].astype(str).str.strip().str.lower().map(GRADE_LEVEL)
    banks["to_level"] = banks["newGrade"].astype(str).str.strip().str.lower().map(GRADE_LEVEL)
    moved = banks["to_level"] - banks["from_level"]          # blank if either grade is unknown

    counts = {"bank rows": len(banks),
              "unknown grade (skipped)": int(moved.isna().sum()),
              "same level, e.g. a reiteration (skipped)": int((moved == 0).sum())}
    changes = banks[moved.notna() & (moved != 0)].copy()
    changes["change"] = np.where(moved[changes.index] > 0, "Upgrade", "Downgrade")

    # FMP dates can fall on a weekend or holiday. Move those to the next day the market was open.
    listed = pd.to_datetime(changes["date"])
    position = np.searchsorted(trading_days, listed.values)   # first trading day on or after the date
    in_range = position < len(trading_days)
    changes["date"] = pd.NaT
    changes.loc[in_range, "date"] = trading_days[position[in_range]]
    counts["moved to next trading day"] = int((changes.loc[in_range, "date"] != listed[in_range]).sum())
    counts["after our last price day (dropped)"] = int((~in_range).sum())
    changes = changes[in_range]

    changes = changes.rename(columns={"gradingCompany": "bank", "previousGrade": "from_grade", "newGrade": "to_grade"})
    changes["ticker"] = ticker
    return changes[["ticker", "date", "bank", "change", "from_grade", "to_grade"]], counts


# ---------------------------------------------------------------------------
# Step 4: merge everything into one table
# ---------------------------------------------------------------------------
def main():
    # The S&P 500 gives us the list of trading days and the "market" columns.
    market = get_prices(INDEX).rename(columns={"adj_open": "sp500_open", "adj_close": "sp500_close",
                                               "ret": "sp500_ret"}).drop(columns="volume")
    trading_days = market["date"].values

    stock_tables, change_tables, counts = [], [], {}
    for ticker in STOCKS:
        try:
            prices = get_prices(ticker)
            changes, counts[ticker] = rating_changes(get_ratings(ticker), ticker, trading_days)
        except Exception as err:                              # one bad stock should not stop the others
            print("SKIPPED %s: %s" % (ticker, err))
            continue
        prices.insert(0, "ticker", ticker)
        stock_tables.append(prices)
        change_tables.append(changes)

    data = pd.concat(stock_tables, ignore_index=True)
    data = data.merge(market, on="date", how="left")          # add the S&P 500 columns to every row
    changes = pd.concat(change_tables, ignore_index=True)

    # Add three columns per bank. A blank means the bank did not change its rating that day.
    for bank, prefix in BANKS.items():
        mine = changes[changes["bank"] == bank].drop_duplicates(["ticker", "date"])   # 1 per stock-day
        mine = mine.rename(columns={"change": prefix + "_change", "from_grade": prefix + "_from",
                                    "to_grade": prefix + "_to"})
        data = data.merge(mine[["ticker", "date", prefix + "_change", prefix + "_from", prefix + "_to"]],
                          on=["ticker", "date"], how="left")

    OUT.mkdir(parents=True, exist_ok=True)
    data.sort_values(["ticker", "date"]).to_csv(OUT / "dataset.csv", index=False, date_format="%Y-%m-%d")

    # ---- Say what is in the file, and make sure no rating change went missing.
    print("\nSaved data/clean/dataset.csv: %s rows, %d stocks, %s to %s" % (
        "{:,}".format(len(data)), data["ticker"].nunique(), data["date"].min().date(), data["date"].max().date()))
    print("\nRating changes (upgrades + downgrades) by bank:")
    for bank, prefix in BANKS.items():
        found = int((changes["bank"] == bank).sum())
        placed = int(data[prefix + "_change"].notna().sum())
        up = int((data[prefix + "_change"] == "Upgrade").sum())
        print("  %-15s %3d found | in the dataset: %d (%d upgrades, %d downgrades)%s" % (
            bank, found, placed, up, placed - up,
            "" if found == placed else " | %d dropped: FMP listed the same stock-day twice, kept the first" % (found - placed)))
    totals = pd.DataFrame(counts).T.sum()
    print("\nBank rows we did NOT turn into a change:")
    for reason in ("same level, e.g. a reiteration (skipped)", "unknown grade (skipped)", "after our last price day (dropped)"):
        print("  %-45s %d" % (reason, totals[reason]))
    print("  Dates moved off a weekend/holiday to the next trading day: %d" % totals["moved to next trading day"])


if __name__ == "__main__":
    main()
