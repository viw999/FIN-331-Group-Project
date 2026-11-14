"""Step 1 of the pipeline: build ONE dataset.

Daily prices for 25 large stocks and the S&P 500, with the days when Goldman Sachs, Morgan Stanley and
JPMorgan changed their rating of a stock, the days each company announced its earnings, and how many
rating changes by OTHER brokers FMP lists for the stock that day.

Run:      python build_dataset.py        (or run every step with  python run_all.py)
Output:   data/clean/dataset.csv         one row per stock per trading day
          logs/data_changes.csv          every place where rows were left out or changed, with the count

Data comes from one provider, Financial Modeling Prep (FMP), on its free plan.
Put your key in a file called .env next to this script:   FMP_API_KEY=your_key_here

THE STEPS (each is a short function below)
  1. get_prices()         daily open, close and volume for each stock and for the S&P 500
  2. get_ratings()        every analyst rating FMP has for each stock
  3. rating_changes()     keep Goldman, Morgan Stanley and JPMorgan; keep only real upgrades/downgrades
  4. other_broker_days()  the days some OTHER broker upgraded or downgraded the stock (build_events.py uses it as a check)
  5. get_earnings()       the days each company announced its quarterly earnings
  6. main()               merge everything into one table and save it

Downloads are saved in data/raw/ and re-used. Set REFRESH = True to download again
(or run  python run_all.py --fresh).
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

from data_log import log_change, start_step

# ---------------------------------------------------------------------------
# SETTINGS - change these to change the dataset
# ---------------------------------------------------------------------------
STOCKS = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "WMT", "V", "XOM", "AMD", "JNJ", "ABBV",
          "COST", "CVX", "KO", "CSCO", "PLTR", "UNH", "BAC", "GE", "INTC", "NFLX", "WFC", "DIS"]
BANKS = {"Goldman Sachs": "gs", "Morgan Stanley": "ms", "JP Morgan": "jpm"}   # FMP's spelling -> column prefix
                           # (the study is written for exactly these three banks: the report's wording, its
                           #  colours and its "two main comparisons" assume it, and make_report.py stops if there are not three)
INDEX = "^GSPC"            # the S&P 500
START = "2010-01-01"       # first day of prices (to go further BACK than the saved downloads: python run_all.py --fresh)
REFRESH = False            # True = ignore the saved downloads and download again

# How we turn rating words into a 3-level scale: 2 = Positive, 1 = Neutral, 0 = Negative.
# A rating CHANGE means the level moved. Buy -> Strong Buy stays at 2, so it is not a change.
# A word that is not in this list is treated as unknown (the row is skipped, and the paper trail counts it).
GRADE_LEVEL = {
    "buy": 2, "strong buy": 2, "outperform": 2, "overweight": 2, "positive": 2, "conviction buy": 2,
    "sector outperform": 2, "market outperform": 2,
    "hold": 1, "neutral": 1, "equal-weight": 1, "equal weight": 1, "market perform": 1, "sector perform": 1,
    "in-line": 1, "in line": 1, "peer perform": 1, "perform": 1, "sector weight": 1, "market weight": 1,
    "sell": 0, "underperform": 0, "underweight": 0, "reduce": 0, "negative": 0,
    "sector underperform": 0, "market underperform": 0,
}

STEP = "1 build_dataset"   # this script's name in logs/data_changes.csv
# Two lines of the log that step 4 (make_report.py) looks up by their text. They are written once, here, so
# that rewording them cannot break the report.
BREAK_TEXT = " rating rows that do not start from the level the bank's previous row ended on"    # follows the bank's name
TWICE_TEXT = "rating changes FMP listed twice for the same bank, stock and day"
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
    table.to_csv(path, index=False)          # saved as a table, nothing changed
    return table


def to_trading_days(listed, trading_days):
    """Move each date that is not a trading day (a weekend or holiday) to the next day the market was open.
    A date after our last trading day has nowhere to go and comes back blank (NaT).
    A date BEFORE our first trading day would land on the first day, so callers drop those dates first."""
    position = np.searchsorted(trading_days, listed.values)       # the first trading day on or after each date
    in_range = position < len(trading_days)
    placed = pd.Series(pd.NaT, index=listed.index)
    placed[in_range] = trading_days[position[in_range]]
    return placed


# ---------------------------------------------------------------------------
# Step 1: prices
# ---------------------------------------------------------------------------
def get_prices(ticker):
    """Daily adjusted open, close and volume. 'Adjusted' = corrected for stock splits and dividends,
    so the change from one close to the next is the real return.
    Returns (prices, how many repeated days were dropped)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()    # today's bar is not finished yet
    if ticker.startswith("^"):                                    # FMP has no dividend-adjusted index: ^GSPC is the
        # price index, so the market's return leaves out dividends while the stocks' returns include them
        endpoint, open_col, close_col = "historical-price-eod/full", "open", "close"
    else:
        endpoint, open_col, close_col = "historical-price-eod/dividend-adjusted", "adjOpen", "adjClose"
    path = RAW / "fmp_prices" / (ticker.replace("^", "_") + ".csv")
    raw = saved_or_download(path, endpoint, symbol=ticker, **{"from": START, "to": yesterday})

    prices = pd.DataFrame({"date": pd.to_datetime(raw["date"]), "adj_open": raw[open_col],
                           "adj_close": raw[close_col], "volume": raw["volume"]})
    prices = prices[prices["date"] >= START].sort_values("date")  # so START also works on the saved downloads
    repeated = int(prices.duplicated("date").sum())                # the same day listed twice: keep the first
    prices = prices.drop_duplicates("date").reset_index(drop=True)
    prices["ret"] = prices["adj_close"].pct_change()               # today's close / yesterday's close - 1
    return prices, repeated


# ---------------------------------------------------------------------------
# Steps 2, 3 and 4: ratings
# ---------------------------------------------------------------------------
def get_ratings(ticker):
    """Every analyst rating FMP has for the stock: date, firm, previous grade, new grade."""
    return saved_or_download(RAW / "fmp_ratings" / (ticker + ".csv"), "grades", symbol=ticker)


def grade_level(words):
    """Turn a column of rating words into levels (2, 1 or 0). A blank or unknown word gives a blank."""
    return words.astype(str).str.strip().str.lower().map(GRADE_LEVEL)


def rating_changes(ratings, ticker, trading_days):
    """Keep our three banks' real upgrades and downgrades, dated on a trading day.

    Returns (changes, counts). `counts` says how many rows we skipped and why, so nothing
    disappears without being counted.
    """
    banks = ratings[ratings["gradingCompany"].isin(BANKS)].copy()
    banks["from_level"] = grade_level(banks["previousGrade"])
    banks["to_level"] = grade_level(banks["newGrade"])
    moved = banks["to_level"] - banks["from_level"]          # blank if either grade is unknown

    counts = {"bank rows": len(banks),
              "unknown grade": int(moved.isna().sum()),
              "same level": int((moved == 0).sum())}

    # How complete is FMP's history? Each row of a bank should start from the level its previous row ended on.
    # A row that does not is a "break": FMP missed a change in between, listed a grade wrongly, or listed
    # one change twice.
    in_time_order = banks.iloc[::-1].sort_values("date", kind="stable")       # the file is newest first
    previous_end = in_time_order.groupby("gradingCompany")["to_level"].shift()
    is_break = previous_end.notna() & (in_time_order["from_level"] != previous_end)
    for bank in BANKS:
        mine = in_time_order["gradingCompany"] == bank
        counts["rows after the first: " + bank] = int((mine & previous_end.notna()).sum())
        counts["breaks: " + bank] = int((mine & is_break).sum())
    changes = banks[moved.notna() & (moved != 0)].copy()
    changes["change"] = np.where(moved[changes.index] > 0, "Upgrade", "Downgrade")
    counts["changes"] = len(changes)

    # A change dated before our first price day has no day to sit on. Count those and leave them out.
    listed = pd.to_datetime(changes["date"])
    too_early = listed < trading_days[0]
    counts["before our first price day"] = int(too_early.sum())
    changes, listed = changes[~too_early].copy(), listed[~too_early]

    # FMP dates can fall on a weekend or holiday. Move those to the next day the market was open.
    changes["date"] = to_trading_days(listed, trading_days)
    counts["moved to next trading day"] = int((changes["date"].notna() & (changes["date"] != listed)).sum())
    counts["after our last price day"] = int(changes["date"].isna().sum())
    changes = changes[changes["date"].notna()]

    changes = changes.rename(columns={"gradingCompany": "bank", "previousGrade": "from_grade", "newGrade": "to_grade"})
    changes["ticker"] = ticker
    return changes[["ticker", "date", "bank", "change", "from_grade", "to_grade"]], counts


def other_broker_days(ratings, ticker, trading_days):
    """The days on which a broker OTHER than our three banks upgraded or downgraded the stock, and how many such
    changes FMP lists that day (a broker that FMP lists twice on one day counts twice).
    Same rule as for our banks: the level moved. These are not our events. build_events.py uses them to flag a
    rating change of ours that shares its days with another broker's call.
    Returns (one row per day with that number, how many such changes there were, how many rows were skipped
    because a rating word is blank or not in GRADE_LEVEL)."""
    others = ratings[~ratings["gradingCompany"].isin(BANKS)]
    moved = grade_level(others["newGrade"]) - grade_level(others["previousGrade"])
    listed = pd.to_datetime(others.loc[moved.notna() & (moved != 0), "date"])
    inside = listed[listed >= trading_days[0]]                    # a date before our first price day has no day to sit on
    placed = to_trading_days(inside, trading_days).dropna()       # weekend or holiday -> the next trading day
    per_day = placed.value_counts().rename_axis("date").reset_index(name="other_changes")
    per_day.insert(0, "ticker", ticker)
    return per_day, len(listed), int(moved.isna().sum())


# ---------------------------------------------------------------------------
# Step 5: earnings announcement days
# ---------------------------------------------------------------------------
def get_earnings(ticker, trading_days):
    """The days the company announced its quarterly earnings, each placed on a trading day.

    FMP gives the date but NOT the time of day. Many companies report after the market closes, and then
    the stock reacts on the NEXT trading day. Step 2 (build_events.py) allows for that.
    Returns (earnings days, counts).
    """
    raw = saved_or_download(RAW / "fmp_earnings" / (ticker + ".csv"), "earnings", symbol=ticker)
    listed = pd.to_datetime(raw["date"]).drop_duplicates()
    inside = listed[(listed >= trading_days[0]) & (listed <= trading_days[-1])]    # FMP also lists the 1980s and next quarter
    placed = to_trading_days(inside, trading_days)

    counts = {"listed": len(listed), "outside our dates": len(listed) - len(inside),
              "moved to next trading day": int((placed != inside).sum()),
              "same day as another": int(placed.duplicated().sum())}     # e.g. a Saturday date moved onto a Monday that has one
    days = pd.DataFrame({"ticker": ticker, "date": placed.drop_duplicates(), "earnings": "Yes"})
    return days, counts


# ---------------------------------------------------------------------------
# Step 6: merge everything into one table
# ---------------------------------------------------------------------------
def main():
    # The S&P 500 gives us the list of trading days and the "market" columns.
    market, index_repeats = get_prices(INDEX)
    market = market.rename(columns={"adj_open": "sp500_open", "adj_close": "sp500_close",
                                    "ret": "sp500_ret"}).drop(columns="volume")
    trading_days = market["date"].values

    stock_tables, change_tables, other_tables, earnings_tables = [], [], [], []
    counts, earnings_counts, skipped, no_earnings, repeated_days = {}, {}, [], [], 0
    other_listed, other_unknown = 0, 0
    for ticker in STOCKS:
        try:
            prices, repeated = get_prices(ticker)
            ratings = get_ratings(ticker)
            changes, counts[ticker] = rating_changes(ratings, ticker, trading_days)
            others, others_found, others_unknown = other_broker_days(ratings, ticker, trading_days)
        except Exception as err:                              # one bad stock should not stop the others
            print("SKIPPED %s: %s" % (ticker, err))
            skipped.append(ticker)
            continue
        prices.insert(0, "ticker", ticker)
        stock_tables.append(prices)
        change_tables.append(changes)
        other_tables.append(others)
        repeated_days += repeated
        other_listed += others_found
        other_unknown += others_unknown
        try:
            earnings, earnings_counts[ticker] = get_earnings(ticker, trading_days)
            earnings_tables.append(earnings)
        except Exception as err:                              # no earnings dates should not cost us the stock
            print("NO EARNINGS DATES for %s: %s" % (ticker, err))
            no_earnings.append(ticker)

    if not stock_tables:
        sys.exit("STOP: every stock was skipped (see the SKIPPED lines above), so there is no dataset. "
                 "Check your FMP key and FMP's daily limit, then run again.")
    data = pd.concat(stock_tables, ignore_index=True)
    data = data.merge(market, on="date", how="left")          # add the S&P 500 columns to every row
    no_market = int(data["sp500_close"].isna().sum())
    changes = pd.concat(change_tables, ignore_index=True)
    found = len(changes)

    # A change can only sit on a day the stock has a price. (One dated before the stock started trading has no row.)
    priced = data[["ticker", "date"]].assign(has_price=True)
    changes = changes.merge(priced, on=["ticker", "date"], how="left")
    no_price = changes["has_price"].isna()
    changes = changes[~no_price]
    # FMP can list the same bank, stock and day twice. Keep the first.
    twice = changes.duplicated(["ticker", "date", "bank"])
    changes = changes[~twice]

    # Add three columns per bank. A blank means the bank did not change its rating that day.
    for bank, prefix in BANKS.items():
        mine = changes[changes["bank"] == bank]
        mine = mine.rename(columns={"change": prefix + "_change", "from_grade": prefix + "_from",
                                    "to_grade": prefix + "_to"})
        data = data.merge(mine[["ticker", "date", prefix + "_change", prefix + "_from", prefix + "_to"]],
                          on=["ticker", "date"], how="left")

    # Add the earnings column: "Yes" on a day the company announced earnings, blank otherwise.
    if earnings_tables:
        earnings = pd.concat(earnings_tables, ignore_index=True)
        data = data.merge(earnings, on=["ticker", "date"], how="left")
    else:
        earnings = pd.DataFrame(columns=["ticker", "date", "earnings"])
        data["earnings"] = np.nan
    earnings_placed = int(data["earnings"].notna().sum())

    # Add the other-brokers column: how many rating changes by brokers outside our three banks FMP lists that day (0 = none).
    data = data.merge(pd.concat(other_tables, ignore_index=True), on=["ticker", "date"], how="left")
    data["other_changes"] = data["other_changes"].fillna(0).astype(int)
    other_days = int((data["other_changes"] > 0).sum())

    OUT.mkdir(parents=True, exist_ok=True)
    data.sort_values(["ticker", "date"]).to_csv(OUT / "dataset.csv", index=False, date_format="%Y-%m-%d")

    # ---- Say what is in the file, and make sure no rating change went missing.
    print("\nSaved data/clean/dataset.csv: %s rows, %d stocks, %s to %s" % (
        "{:,}".format(len(data)), data["ticker"].nunique(), data["date"].min().date(), data["date"].max().date()))
    print("\nRating changes (upgrades + downgrades) by bank, in the dataset:")
    for bank, prefix in BANKS.items():
        placed = int(data[prefix + "_change"].notna().sum())
        up = int((data[prefix + "_change"] == "Upgrade").sum())
        print("  %-15s %3d  (%d upgrades, %d downgrades)" % (bank, placed, up, placed - up))
    print("Earnings announcement days in the dataset: %s" % "{:,}".format(earnings_placed))
    print("Days with an upgrade or downgrade by another broker: %s" % "{:,}".format(other_days))

    # ---- The paper trail: every place where rows were left out or changed.
    print("\nWhat was left out or changed (also saved in logs/data_changes.csv):")
    totals = pd.DataFrame(counts).T.sum()
    no_earnings_counts = pd.Series({"listed": 0, "outside our dates": 0, "moved to next trading day": 0, "same day as another": 0})
    earnings_totals = pd.DataFrame(earnings_counts).T.sum() if earnings_counts else no_earnings_counts
    in_dataset = sum(int(data[prefix + "_change"].notna().sum()) for prefix in BANKS.values())
    if found - int(no_price.sum()) - int(twice.sum()) != in_dataset:      # every change is either placed or counted below
        sys.exit("STOP: the rating changes do not add up. Found %d, in the dataset %d." % (found, in_dataset))

    start_step(STEP)                          # only now: a stop above leaves the old paper trail alone
    log_change(STEP, "REMOVED", len(skipped), len(STOCKS), "stocks left out because a download failed" + (": " + ", ".join(skipped) if skipped else ""),
               "FMP returned an error or no rows; run again later")
    log_change(STEP, "REMOVED", index_repeats, len(market) + index_repeats, "S&P 500 rows for a day FMP listed twice", "kept the first")
    log_change(STEP, "REMOVED", repeated_days, len(data) + repeated_days, "price rows for a day FMP listed twice", "kept the first")
    log_change(STEP, "FLAGGED", no_market, len(data), "stock-days with no S&P 500 row", "no abnormal return can be computed on these days")
    log_change(STEP, "REMOVED", totals["unknown grade"], totals["bank rows"], "bank rating rows with a blank or unknown grade",
               "mostly first-time ratings, which have no previous grade, so there is no change to measure")
    log_change(STEP, "REMOVED", totals["same level"], totals["bank rows"], "bank rating rows where the level did not move",
               "a reiteration, or a move inside one level such as Buy to Strong Buy, is not an upgrade or downgrade")
    for bank in BANKS:
        log_change(STEP, "FLAGGED", totals["breaks: " + bank], totals["rows after the first: " + bank], bank + BREAK_TEXT,
                   "each one means FMP missed a change in between, listed a grade wrongly, or listed one change twice: "
                   "it shows how incomplete this bank's history is")
    log_change(STEP, "CHANGED", totals["moved to next trading day"], totals["changes"], "rating changes dated on a weekend or holiday",
               "moved to the next trading day, the first day the market could react")
    log_change(STEP, "REMOVED", totals["after our last price day"], totals["changes"], "rating changes dated after our last price day", "no price to match them to")
    log_change(STEP, "REMOVED", int(no_price.sum()) + totals["before our first price day"], totals["changes"],
               "rating changes dated before the stock's first price day", "no price to match them to")
    log_change(STEP, "REMOVED", int(twice.sum()), totals["changes"], TWICE_TEXT, "kept the first")
    log_change(STEP, "FLAGGED", other_days, len(data), "stock-days on which a broker other than the three banks upgraded or downgraded the stock",
               "%s such changes in FMP's list (%d more rows skipped: a rating word is blank or not in GRADE_LEVEL); they are not our "
               "events, but build_events.py flags a rating change of ours that has one nearby" % ("{:,}".format(other_listed), other_unknown))
    log_change(STEP, "FLAGGED", len(no_earnings), len(STOCKS) - len(skipped), "stocks with no earnings dates" + (": " + ", ".join(no_earnings) if no_earnings else ""),
               "the download failed, so rating changes on these stocks cannot be checked against earnings")
    log_change(STEP, "REMOVED", earnings_totals["outside our dates"], earnings_totals["listed"], "earnings dates before our first or after our last price day",
               "FMP's list goes back to the 1980s and includes next quarter's planned date")
    log_change(STEP, "CHANGED", earnings_totals["moved to next trading day"], earnings_totals["listed"] - earnings_totals["outside our dates"],
               "earnings dates on a weekend or holiday", "moved to the next trading day")
    log_change(STEP, "REMOVED", earnings_totals["same day as another"], earnings_totals["listed"] - earnings_totals["outside our dates"],
               "earnings dates that land on a trading day that already has one", "two dates on one trading day are counted once")
    log_change(STEP, "REMOVED", len(earnings) - earnings_placed, earnings_totals["listed"] - earnings_totals["outside our dates"],
               "earnings dates before the stock's first price day", "no price row to put them on")


if __name__ == "__main__":
    main()
