"""Step 2 of the pipeline: list every rating change and measure how the stock moved around it.

Run:      python build_events.py          (after build_dataset.py, or run every step with  python run_all.py)
Input:    data/clean/dataset.csv
Output:   data/clean/events.csv           one row per rating change: is it used, is it doubtful, how the stock moved
          data/clean/event_days.csv       the stock's abnormal return on each day from -10 to +20 around each used change
          data/clean/ordinary_days.csv    the same measurements on random days with no rating change by the three
                                          banks nearby (the yardstick). Its event_id numbers the ordinary days;
                                          matched_event_id is the rating change each one was drawn for
          logs/data_changes.csv           every place where events were left out or flagged, with the count

THE KEY IDEAS
  Day 0            The trading day of the rating change. Day -1 is the trading day before it, day +1 the one after.
  Abnormal return  The stock's return minus the S&P 500's return on the same day (AR). It is the part of the move
                   that the overall market does not explain.
  Window           A run of days, for example -1..+1. The abnormal returns in the window are added up. Finance
                   calls that total the cumulative abnormal return (CAR).
  Typical day      How much the stock's abnormal return normally bounces around: its standard deviation over the
                   240 trading days that END 11 days before the rating change (days -250..-11). We stop 11 days
                   early so that the rating change itself, and any news just before it, is not in the yardstick.
  Standardized     The move divided by the stock's typical day (SAR for one day, SCAR for a window). 3% is a
                   shock for Coca-Cola and an ordinary day for AMD. Dividing puts every stock on one scale:
                   2.0 means "twice the size of a typical day for this stock". Without this step a bank that
                   happens to rate jumpy stocks would look more influential.
  Market model     A second way to get the abnormal return, used as a check. Instead of assuming the stock moves
                   one-for-one with the S&P 500, we estimate how it really moves with it over the same 240 days
                   (return = alpha + beta x S&P return) and subtract that prediction. Columns ending in _mm.
  Ordinary days    Random days of the same stocks, in the same years, with no rating change by our three banks
                   nearby. Even with no news a stock moves, so the SIZE of a move is never zero. The ordinary
                   days tell us how big "nothing happened" is. A rating change only matters if it beats that.

THE STEPS (each is a short function below)
  0. check_settings() and self_check()   stop early on a setting the pipeline cannot handle, and test the
                          measuring code on a made-up stock with a known answer
  1. load_data()          read the dataset; work out the abnormal return of every stock on every day
  2. find_events()        one row per rating change
  3. flag_repeats()       leave out a change that FMP listed twice
  4. flag_inconsistent()  mark a change that does not start where the bank's last change ended
  5. flag_overlaps()      mark a change with another of our banks' rating changes on the same stock right next to it
  6. flag_earnings()      mark a change that came out right around the company's earnings announcement
  7. flag_other_brokers() mark a change with an upgrade or downgrade by some OTHER broker right next to it
  8. measure()            the typical day, and the stock's move in each window
  9. pick_ordinary_days() the yardstick sample, measured with the very same code
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from build_dataset import BANKS, grade_level          # the three banks and the word-to-level table live in build_dataset.py
from data_log import log_change, start_step

# ---------------------------------------------------------------------------
# SETTINGS - change these to change the study
# ---------------------------------------------------------------------------
REPEAT_DAYS = 5              # same bank, same stock, same direction again within this many trading days = one change listed twice
REPEAT_KEEP = "later"        # which listing of a repeated change is kept: "later" or "first" (see flag_repeats)
OVERLAP_DAYS = 2             # another rating change on the same stock within this many trading days = an overlap
                             # (2, because two -1..+1 windows that are 2 days apart still share a day)
EARNINGS_DAYS_BEFORE = 1     # flag a change dated up to this many trading days BEFORE an earnings date ...
EARNINGS_DAYS_AFTER = 2      # ... or up to this many AFTER it (2, because after-the-close earnings move the stock a day later)
EARNINGS_MAX_GAP = 100       # companies report every quarter: about 63 trading days apart, up to 96 for a long fiscal
                             # quarter (Costco). No earnings date in the 100 trading days before a change means FMP's
                             # list has a hole there: "earnings unknown"
OTHER_BROKER_DAYS = 1        # an upgrade or downgrade by a broker outside our three banks within this many trading
                             # days = "another broker nearby" (1 = inside the -1..+1 window)

ESTIMATION = (-250, -11)     # the days used to learn the stock's typical day and its market model
MIN_ESTIMATION_DAYS = 120    # fewer usable days than this in ESTIMATION: no typical day, so the event cannot be used

CHART_DAYS = (-10, 20)       # the days saved for the event-study chart (every window must fit inside)
WINDOWS = {                  # name: (first day, last day)
    "day0": (0, 0),          # the day of the rating change            } these two must stay as they are: the tables
    "3day": (-1, 1),         # the day before to the day after         } and the report are worded for these days
    "runup": (-10, -2),      # before the change: news, leaks, or the bank following the price   (can be changed)
    "drift": (2, 20),        # after the change: does the stock keep moving?                      (can be changed)
}
MAIN_WINDOWS = ["day0", "3day"]   # an event needs both of these to be used

ORDINARY_PER_EVENT = 20      # ordinary days drawn for every rating change (same stock, same calendar year)
QUIET_DAYS = 5               # an ordinary day is more than this many trading days away from any rating change by our banks
                             # (a bigger number leaves too few days to draw from in a busy year: Tesla had 8 changes in 2020).
                             # So an ordinary day's -1..+1 window is free of our banks' changes, but its long windows are
                             # not: in the November 2026 build about 1 ordinary day in 8 had one somewhere in days +2..+20.
SEED = 331                   # fixes the random draw, so every run picks the same ordinary days

STEP = "2 build_events"
HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "data" / "clean" / "dataset.csv"
OUT = HERE / "data" / "clean"


# ---------------------------------------------------------------------------
# Step 0: stop early on a setting the pipeline cannot handle
# ---------------------------------------------------------------------------
def check_settings():
    """Say in plain words which setting is the problem, instead of failing later with a confusing error."""
    if REPEAT_KEEP not in ("later", "first"):
        sys.exit('SETTINGS: REPEAT_KEEP must be "later" or "first", not "%s".' % REPEAT_KEEP)
    if WINDOWS["day0"] != (0, 0) or WINDOWS["3day"] != (-1, 1):
        sys.exit('SETTINGS: WINDOWS["day0"] must stay (0, 0) and WINDOWS["3day"] must stay (-1, 1). '
                 "The tables and the report are worded for these days. The run-up and the drift can be changed.")
    outside = [name for name, (first, last) in WINDOWS.items() if first < CHART_DAYS[0] or last > CHART_DAYS[1]]
    if outside:
        sys.exit("SETTINGS: the window %s reaches outside CHART_DAYS %s. Widen CHART_DAYS or shorten the window."
                 % (" and ".join(outside), CHART_DAYS))
    if ESTIMATION[1] - ESTIMATION[0] + 1 < MIN_ESTIMATION_DAYS:
        sys.exit("SETTINGS: ESTIMATION %s holds %d days, fewer than MIN_ESTIMATION_DAYS (%d), so no rating change could be used."
                 % (ESTIMATION, ESTIMATION[1] - ESTIMATION[0] + 1, MIN_ESTIMATION_DAYS))
    if CHART_DAYS[0] <= ESTIMATION[1]:
        sys.exit("SETTINGS: CHART_DAYS starts on day %d, but ESTIMATION only ends on day %d. The days used to learn "
                 "the stock's typical day must end before the days we measure." % (CHART_DAYS[0], ESTIMATION[1]))


# ---------------------------------------------------------------------------
# Step 1: load the data
# ---------------------------------------------------------------------------
def load_data():
    if not DATA_FILE.exists():
        sys.exit("Cannot find data/clean/dataset.csv. Run  python build_dataset.py  first (or  python run_all.py).")
    data = pd.read_csv(DATA_FILE, parse_dates=["date"])
    data = data.sort_values(["ticker", "date"]).reset_index(drop=True)
    data["abnormal"] = data["ret"] - data["sp500_ret"]           # the stock beat (or lagged) the market by this much
    data["day_number"] = data.groupby("ticker").cumcount()       # 0 on the stock's first day, 1 on the next, ...
    # Do not drop rows of `data` after this line: day_number is also the row position that measure() uses.
    return data


# ---------------------------------------------------------------------------
# Step 2: one row per rating change
# ---------------------------------------------------------------------------
def find_events(data):
    """The dataset has three columns per bank. Stack them into one row per rating change."""
    tables = []
    for bank, prefix in BANKS.items():
        rows = data[data[prefix + "_change"].notna()]             # the days this bank changed its rating
        tables.append(pd.DataFrame({
            "ticker": rows["ticker"], "date": rows["date"], "day_number": rows["day_number"], "bank": bank,
            "change": rows[prefix + "_change"],                   # Upgrade or Downgrade
            "from_grade": rows[prefix + "_from"], "to_grade": rows[prefix + "_to"],
        }))
    events = pd.concat(tables, ignore_index=True).sort_values(["ticker", "date", "bank"]).reset_index(drop=True)
    events.insert(0, "event_id", range(1, len(events) + 1))
    events["direction"] = np.where(events["change"] == "Upgrade", 1, -1)        # +1 upgrade, -1 downgrade
    events["from_level"] = grade_level(events["from_grade"])      # 2 positive, 1 neutral, 0 negative
    events["to_level"] = grade_level(events["to_grade"])
    events["levels_moved"] = (events["to_level"] - events["from_level"]).abs()  # 1 = one step, 2 = Buy <-> Sell
    events["status"] = "used"                                     # later steps change this if the event is left out
    return events


# ---------------------------------------------------------------------------
# Steps 3 to 7: events that are repeats, or that are doubtful
# ---------------------------------------------------------------------------
def flag_repeats(events):
    """FMP sometimes lists one change twice, a day or so apart. Count it once.

    Which listing is the real day? We keep the LATER one (REPEAT_KEEP = "later"). FMP's older rows are
    sometimes dated a day early (some even fall on a Sunday), and the stock agrees: main() prints, for every
    pair, how much the stock moved on each of the two dates. The first listing is usually a quiet day.
    In the November 2026 build all 5 pairs are one trading day apart, so the -1..+1 window covers both dates
    and the main results barely depend on this choice. The day-0-only check on all used events does depend
    on it: for two Goldman pairs (AMZN April 2012, TSLA May 2013) the first listing is the earnings date and
    the later one is the day the stock reacted to the earnings."""
    same_call = ["ticker", "bank", "change"]
    ordered = events.sort_values(same_call + ["day_number"])     # `ordered` keeps the row labels of `events`: do not reset the index
    days_since_previous = ordered.groupby(same_call)["day_number"].diff()        # trading days since this bank last moved this stock the same way
    starts_run = days_since_previous.isna() | (days_since_previous > REPEAT_DAYS)  # True for a first listing (blank), or one long after the previous
    run = starts_run.cumsum()                                                     # listings that follow each other closely share one run number
    keep = "last" if REPEAT_KEEP == "later" else "first"
    kept = ordered.groupby(run)["event_id"].transform(keep)                       # the listing of each run that is kept
    repeats = ordered.index[ordered["event_id"] != kept]                          # every other listing of the run is dropped
    events.loc[repeats, "status"] = "repeat listing"
    events["repeat_of"] = kept[repeats]                                           # blank unless this row is a repeat
    log_change(STEP, "REMOVED", len(repeats), len(events), "rating changes that FMP listed twice",
               "same bank, stock and direction within %d trading days; the %s listing is kept" % (REPEAT_DAYS, REPEAT_KEEP))
    return events


def flag_inconsistent(events):
    """A bank's change should start from the level its previous change ended on (Buy -> Hold, then Hold -> ...).
    When it does not, FMP either missed a change in between or listed something wrong. We keep the event
    (we cannot tell which) and flag it, so the results can be checked without these events.
    (The previous change counts even if it is later left out for having too little price history.)"""
    events["inconsistent"] = False
    live = events[events["status"] == "used"].sort_values(["ticker", "bank", "day_number"])
    previous_end = live.groupby(["ticker", "bank"])["to_level"].shift()      # blank for a bank's first change in a stock
    mismatch = previous_end.notna() & (previous_end != live["from_level"])
    events.loc[mismatch[mismatch].index, "inconsistent"] = True
    log_change(STEP, "FLAGGED", int(mismatch.sum()), len(live), "rating changes that do not start where the bank's previous change ended",
               "FMP missed a change in between, or listed one wrongly; kept, and the results are re-checked without them")
    return events


def flag_overlaps(events):
    """Another rating change on the same stock right next to this one (by any of our three banks, repeats not
    counted). The two changes share the same price move, so we cannot say which bank moved the stock.
    Brokers outside our three banks are handled separately, in flag_other_brokers()."""
    events["overlap"] = False
    live = events[events["status"] == "used"].sort_values(["ticker", "day_number"])
    days_to_previous = live.groupby("ticker")["day_number"].diff()
    days_to_next = -live.groupby("ticker")["day_number"].diff(-1)
    close = (days_to_previous <= OVERLAP_DAYS) | (days_to_next <= OVERLAP_DAYS)
    events.loc[close[close].index, "overlap"] = True
    log_change(STEP, "FLAGGED", int(close.sum()), len(live), "rating changes with another rating change by our three banks on the same stock within %d trading day(s)" % OVERLAP_DAYS,
               "the two changes share one price move; kept, and the results are re-checked without them")
    return events


def flag_earnings(events, data):
    """Banks often change a rating right after a company reports earnings, and then the earnings news is in the
    price move too. FMP gives the earnings DATE but not the time. A company that reports after the close moves
    its stock on the next trading day, so we look one day further back than forward."""
    earnings = data[data["earnings"].notna()]
    earnings_days = {ticker: rows["day_number"].values for ticker, rows in earnings.groupby("ticker")}

    near, known = [], []
    for _, event in events.iterrows():
        days = earnings_days.get(event["ticker"], np.array([]))       # empty if the stock has no earnings dates at all
        days_after = event["day_number"] - days                       # +1 = the rating came 1 trading day after earnings
        is_near = bool(((days_after >= -EARNINGS_DAYS_BEFORE) & (days_after <= EARNINGS_DAYS_AFTER)).any())
        near.append(is_near)
        # We only trust "not near earnings" if the list covers this stretch: the previous quarter's date must be there.
        known.append(is_near or bool(((days_after >= 0) & (days_after <= EARNINGS_MAX_GAP)).any()))
    events["near_earnings"] = near
    events["earnings_known"] = known
    return events


def flag_other_brokers(events, data):
    """Our three banks are not the only brokers. If some OTHER broker upgraded or downgraded the stock inside
    the -1..+1 window, that call is in the price move too. We keep the event and flag it, and analyze_events.py re-checks
    the main result without these events. (An event can be "clean" and still carry this flag.)"""
    busy = data[data["other_changes"] > 0]
    busy_days = {ticker: rows["day_number"].values for ticker, rows in busy.groupby("ticker")}

    flags = []
    for _, event in events.iterrows():
        days = busy_days.get(event["ticker"], np.array([]))           # empty if no other broker ever changed its rating
        flags.append(bool((np.abs(days - event["day_number"]) <= OTHER_BROKER_DAYS).any()))
    events["other_broker"] = flags
    return events


def log_earnings(events):
    """Called after the unmeasurable events are gone, so the counts are out of the USED rating changes."""
    live = events[events["status"] == "used"]
    log_change(STEP, "FLAGGED", int(live["near_earnings"].sum()), len(live),
               "rating changes dated from %d trading day(s) before to %d after an earnings announcement" % (EARNINGS_DAYS_BEFORE, EARNINGS_DAYS_AFTER),
               "the earnings news is in the same price move; kept, and the results are re-checked without them")
    log_change(STEP, "FLAGGED", int((~live["earnings_known"]).sum()), len(live),
               "rating changes with no earnings date for that stock in the %d trading days before" % EARNINGS_MAX_GAP,
               "FMP's earnings list has a hole there, so we cannot tell whether these were near earnings; they are NOT counted as clean")


# ---------------------------------------------------------------------------
# Step 8: measure the stock's move around each event
# ---------------------------------------------------------------------------
def typical_day(stock, day0):
    """What a normal day looks like for this stock just before the event (days -250..-11).
    Returns the typical day (standard deviation of the abnormal return) and the market model."""
    first = max(day0 + ESTIMATION[0], 0)                              # a young stock may not have 250 earlier days
    last = max(day0 + ESTIMATION[1] + 1, 0)                           # +1 because a Python slice stops one early
    calm = stock.iloc[first:last].dropna(subset=["ret", "sp500_ret"])

    result = {"calm_days": len(calm), "typical_day": np.nan, "alpha": np.nan, "beta": np.nan, "typical_day_mm": np.nan}
    if len(calm) >= MIN_ESTIMATION_DAYS:
        result["typical_day"] = calm["abnormal"].std()
        beta, alpha = np.polyfit(calm["sp500_ret"], calm["ret"], 1)   # the straight line: ret = alpha + beta x sp500_ret
        unexplained = calm["ret"] - (alpha + beta * calm["sp500_ret"])
        result["alpha"], result["beta"] = alpha, beta
        result["typical_day_mm"] = unexplained.std(ddof=2)            # ddof=2: the line used up two estimates
    return result


def days_around(stock, day0, typical):
    """The abnormal return on each day from -10 to +20 (fewer days if the price history stops)."""
    around = stock.iloc[max(day0 + CHART_DAYS[0], 0): day0 + CHART_DAYS[1] + 1]
    expected = typical["alpha"] + typical["beta"] * around["sp500_ret"]       # blank when there is no market model
    return pd.DataFrame({"day": around["day_number"].values - day0,
                         "abnormal": around["abnormal"].values,
                         "abnormal_mm": (around["ret"] - expected).values})


def window_total(days, name, first, last, typical):
    """Add up the abnormal returns from day `first` to day `last`. Blank if any of those days is missing."""
    length = last - first + 1
    inside = days[(days["day"] >= first) & (days["day"] <= last)]
    car = inside["abnormal"].sum(min_count=length)                    # min_count: blank unless every day is there
    car_mm = inside["abnormal_mm"].sum(min_count=length)
    # A total over N days bounces around sqrt(N) times as much as one day, so that is what we divide by.
    spread = np.sqrt(length)
    return {"car_" + name: car, "scar_" + name: car / (typical["typical_day"] * spread),
            "car_mm_" + name: car_mm, "scar_mm_" + name: car_mm / (typical["typical_day_mm"] * spread)}


def day0_split(stock, day0):
    """Split the stock's own day-0 return into the overnight part (yesterday's close to today's open)
    and the intraday part (today's open to today's close)."""
    if day0 < 1:
        return {"overnight": np.nan, "intraday": np.nan}
    today, yesterday = stock.iloc[day0], stock.iloc[day0 - 1]
    return {"overnight": today["adj_open"] / yesterday["adj_close"] - 1,
            "intraday": today["adj_close"] / today["adj_open"] - 1}


def measure(events, data):
    """Add the measurements to every event. Returns (events, event_days)."""
    stocks = {ticker: rows.reset_index(drop=True) for ticker, rows in data.groupby("ticker")}
    results, daily_tables = [], []
    for _, event in events.iterrows():
        stock = stocks[event["ticker"]]
        day0 = int(event["day_number"])                               # the row of the stock's table that is the event day
        typical = typical_day(stock, day0)
        days = days_around(stock, day0, typical)

        result = {"event_id": event["event_id"], **typical}
        for name, (first, last) in WINDOWS.items():
            result.update(window_total(days, name, first, last, typical))
        result.update(day0_split(stock, day0))
        results.append(result)

        days.insert(0, "event_id", event["event_id"])
        daily_tables.append(days)
    return events.merge(pd.DataFrame(results), on="event_id"), pd.concat(daily_tables, ignore_index=True)


def drop_unmeasurable(events):
    """An event is only used if we could measure its main windows on the standardized scale."""
    live = events["status"] == "used"
    total = int(live.sum())

    no_typical = live & events["typical_day"].isna()
    events.loc[no_typical, "status"] = "too little price history"
    log_change(STEP, "REMOVED", int(no_typical.sum()), total,
               "rating changes with fewer than %d usable trading days in the %d..%d estimation period" % (MIN_ESTIMATION_DAYS, ESTIMATION[0], ESTIMATION[1]),
               "too few earlier prices (the stock is new, or the change comes soon after the first day of prices): "
               "its typical day cannot be measured, so the move cannot be put on the common scale")

    live = events["status"] == "used"
    total = int(live.sum())                                           # the events that are still in
    no_window = live & events[["scar_" + name for name in MAIN_WINDOWS]].isna().any(axis=1)
    events.loc[no_window, "status"] = "at the edge of the price history"
    log_change(STEP, "REMOVED", int(no_window.sum()), total, "rating changes on the first or last day of the stock's prices",
               "the day before or the day after is missing, so the -1..+1 window is incomplete")

    live = events["status"] == "used"
    total = int(live.sum())
    for name in ["runup", "drift"]:
        first, last = WINDOWS[name]
        log_change(STEP, "FLAGGED", int((live & events["car_" + name].isna()).sum()), total,
                   "used rating changes without a complete %+d..%+d window" % (first, last),
                   "too close to the start or end of the prices; they are missing from that window's averages "
                   "(figure 1 leaves out a change without all days %+d..%+d and says how many)" % CHART_DAYS)
    return events


# ---------------------------------------------------------------------------
# Step 9: the yardstick - ordinary days with no rating change by our banks
# ---------------------------------------------------------------------------
def pick_ordinary_days(events, data):
    """For every used rating change, draw random days of the SAME stock in the SAME calendar year that are more
    than QUIET_DAYS trading days away from every rating change by our three banks. Matching the stock and the
    year means the ordinary days are a fair yardstick: same companies, same market conditions, just no rating
    change by these banks. (Other brokers' changes are not screened out; they are flagged afterwards.)"""
    random = np.random.default_rng(SEED)
    data = data.assign(year=data["date"].dt.year)
    last_day = data.groupby("ticker")["day_number"].transform("max")
    enough_room = (data["day_number"] >= -ESTIMATION[0]) & (data["day_number"] <= last_day - CHART_DAYS[1])

    # Mark the days that are too close to a rating change (repeat listings count too: something happened there).
    quiet = pd.Series(True, index=data.index)
    for _, event in events.iterrows():
        close = (data["ticker"] == event["ticker"]) & ((data["day_number"] - event["day_number"]).abs() <= QUIET_DAYS)
        quiet[close] = False
    candidates = data[quiet & enough_room]

    picks = []
    for _, event in events[events["status"] == "used"].iterrows():
        pool = candidates[(candidates["ticker"] == event["ticker"]) & (candidates["year"] == event["date"].year)]
        chosen = pool.loc[random.choice(pool.index, size=min(ORDINARY_PER_EVENT, len(pool)), replace=False)]
        picks.append(pd.DataFrame({"ticker": chosen["ticker"], "date": chosen["date"], "day_number": chosen["day_number"],
                                   "matched_event_id": event["event_id"], "bank": event["bank"], "change": event["change"]}))

    short = [len(pick) for pick in picks if len(pick) < ORDINARY_PER_EVENT]      # events whose stock and year had too few quiet days
    log_change(STEP, "FLAGGED", len(short), len(picks), "used rating changes with fewer than %d ordinary days" % ORDINARY_PER_EVENT,
               "that stock and year have too few quiet days with %d earlier trading days; %d ordinary days are missing in all"
               % (-ESTIMATION[0], ORDINARY_PER_EVENT * len(short) - sum(short)))
    ordinary = pd.concat(picks, ignore_index=True)
    ordinary.insert(0, "event_id", range(1, len(ordinary) + 1))
    return ordinary


# ---------------------------------------------------------------------------
# A test with a known answer
# ---------------------------------------------------------------------------
def self_check():
    """Run the measuring code on a made-up stock where we know the right answer, and stop if it gets it wrong.

    The made-up stock follows the market, plus a wobble of +1% / -1% on alternate days. The wobble stops
    10 days before the event. On the event day the stock jumps 5% more than the market. So the right
    answers are: day 0 = 5%, days -1..+1 = 5%, run-up = 0, drift = 0, typical day = 1%, beta = 1.
    This catches the classic event-study bugs: windows that are one day off, and a "typical day" that
    peeks at the event (it must be the same whether the jump is 5% or 50%).
    If it fails right after you changed a SETTING, look at the setting first: check_settings() catches the
    common mistakes, but not every one."""
    event_day = -ESTIMATION[0] + 50                                   # enough earlier days for the whole estimation period
    days = event_day + CHART_DAYS[1] + 50
    market = np.tile([0.004, -0.002, 0.001], days)[:days]
    wobble = np.where(np.arange(days) % 2 == 0, 0.01, -0.01)
    wobble[event_day + ESTIMATION[1] + 1:] = 0                        # calm from day -10 on

    def measured(jump):
        ret = market + wobble
        ret[event_day] += jump
        close = 100 * np.cumprod(1 + ret)
        previous_close = np.concatenate([[100], close[:-1]])
        fake = pd.DataFrame({"ticker": "FAKE", "day_number": range(days), "ret": ret, "sp500_ret": market,
                             "abnormal": ret - market, "adj_close": close, "adj_open": previous_close * (1 + ret / 2)})
        event = pd.DataFrame({"event_id": [1], "ticker": ["FAKE"], "day_number": [event_day]})
        return measure(event, fake)[0].iloc[0]

    small, big = measured(0.05), measured(0.50)
    day0_return = market[event_day] + 0.05
    checks = {
        "day 0 holds the whole 5% jump": abs(small["car_day0"] - 0.05) < 1e-9,
        "days -1..+1 add up to the 5% jump": abs(small["car_3day"] - 0.05) < 1e-9,
        "nothing leaks into the run-up or the drift": abs(small["car_runup"]) < 1e-9 and abs(small["car_drift"]) < 1e-9,
        "the typical day is the 1% wobble": abs(small["typical_day"] - 0.01) < 1e-4,
        "the typical day uses every day of the estimation period and no more": small["calm_days"] == ESTIMATION[1] - ESTIMATION[0] + 1,
        "the typical day does not peek at the event": small["typical_day"] == big["typical_day"],
        "the standardized move is the jump divided by the typical day": abs(small["scar_day0"] - 0.05 / small["typical_day"]) < 1e-9,
        "the 3-day standardized move is divided by sqrt(3) as well": abs(small["scar_3day"] - 0.05 / (small["typical_day"] * np.sqrt(3))) < 1e-9,
        # (the made-up wobble and market cancel exactly only when the estimation period is a multiple of 6 days
        #  long, as it is with the settings above; the looser limits let other lengths pass too)
        "the market model finds beta = 1 and the same 5%": abs(small["beta"] - 1) < 0.15 and abs(small["car_mm_day0"] - 0.05) < 0.001,
        "overnight and intraday multiply back to the day-0 return": abs((1 + small["overnight"]) * (1 + small["intraday"]) - 1 - day0_return) < 1e-9,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        sys.exit("SELF-CHECK FAILED, so nothing was saved. Wrong: " + "; ".join(failed))
    print("Self-check on a made-up stock with a known 5%% jump: all %d checks passed." % len(checks))


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------
def print_repeats(events):
    """Show each change that FMP listed twice, with the stock's move on both dates, so the choice can be checked."""
    repeats = events[events["status"] == "repeat listing"]
    if len(repeats) == 0:
        return
    kept = events.set_index("event_id")
    print("\nChanges FMP listed twice (abnormal return on the dropped date / on the kept date):")
    for _, repeat in repeats.iterrows():
        partner = kept.loc[repeat["repeat_of"]]
        print("  %-5s %-15s %-9s dropped %s (%+.2f%%)   kept %s (%+.2f%%)" % (
            repeat["ticker"], repeat["bank"], repeat["change"], repeat["date"].date(), repeat["car_day0"] * 100,
            partner["date"].date(), partner["car_day0"] * 100))


def main():
    check_settings()
    self_check()
    data = load_data()
    start_step(STEP)                          # only now: a stop above leaves the old paper trail alone

    events = find_events(data)
    print("Found %d rating changes on %d stocks." % (len(events), events["ticker"].nunique()))
    events = flag_repeats(events)
    events = flag_inconsistent(events)
    events = flag_overlaps(events)
    events = flag_earnings(events, data)
    events = flag_other_brokers(events, data)
    events, event_days = measure(events, data)
    events = drop_unmeasurable(events)
    log_earnings(events)
    # "clean" = used, not next to earnings (and its earnings dates are known), and no other rating change by our
    # three banks next to it. These are the events where the price move can most fairly be credited to ONE
    # bank's call. The main results use them.
    events["clean"] = (events["status"] == "used") & ~events["overlap"] & ~events["near_earnings"] & events["earnings_known"]
    log_change(STEP, "FLAGGED", int(((events["status"] == "used") & ~events["clean"]).sum()), int((events["status"] == "used").sum()),
               "used rating changes that are NOT clean (near earnings, earnings unknown, or overlapping another change)",
               "the main results use the clean events only; every result is also shown with these events included")
    log_change(STEP, "FLAGGED", int((events["clean"] & events["other_broker"]).sum()), int(events["clean"].sum()),
               "clean rating changes with another broker's upgrade or downgrade within %d trading day(s)" % OTHER_BROKER_DAYS,
               "that broker's call is in the same price move; kept, and the main result is re-checked without them")
    print_repeats(events)

    ordinary = pick_ordinary_days(events, data)
    ordinary = flag_earnings(ordinary, data)
    ordinary = flag_other_brokers(ordinary, data)
    log_change(STEP, "FLAGGED", int((ordinary["near_earnings"] | ~ordinary["earnings_known"]).sum()), len(ordinary),
               "ordinary days near an earnings announcement, or with earnings dates unknown",
               "kept in the file; left out of the yardstick for the clean events")
    log_change(STEP, "FLAGGED", int(ordinary["other_broker"].sum()), len(ordinary),
               "ordinary days with another broker's upgrade or downgrade within %d trading day(s)" % OTHER_BROKER_DAYS,
               "kept: brokers outside the three banks are not screened out of the yardstick")
    ordinary, _ = measure(ordinary, data)

    OUT.mkdir(parents=True, exist_ok=True)
    events.drop(columns="day_number").to_csv(OUT / "events.csv", index=False, date_format="%Y-%m-%d")
    used_ids = events.loc[events["status"] == "used", "event_id"]
    event_days[event_days["event_id"].isin(used_ids)].to_csv(OUT / "event_days.csv", index=False)
    ordinary.drop(columns="day_number").to_csv(OUT / "ordinary_days.csv", index=False, date_format="%Y-%m-%d")

    used = events[events["status"] == "used"]
    print("\nSaved data/clean/events.csv: %d rating changes, %d used, %d of those clean." % (len(events), len(used), int(events["clean"].sum())))
    print("Used rating changes by bank (upgrades / downgrades):")
    for bank in BANKS:
        mine = used[used["bank"] == bank]
        print("  %-15s %3d  (%d / %d)" % (bank, len(mine), int((mine["change"] == "Upgrade").sum()), int((mine["change"] == "Downgrade").sum())))
    print("Saved data/clean/event_days.csv (%s rows) and data/clean/ordinary_days.csv (%s ordinary days)." % (
        "{:,}".format(int(event_days["event_id"].isin(used_ids).sum())), "{:,}".format(len(ordinary))))


if __name__ == "__main__":
    main()
