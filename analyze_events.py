"""Step 3 of the pipeline: compare the three banks.

Run:      python analyze_events.py        (after build_events.py, or run every step with  python run_all.py)
Input:    data/clean/events.csv           one row per rating change, with the stock's move (made by step 2)
          data/clean/event_days.csv       the abnormal return on each day around each used change
          data/clean/ordinary_days.csv    the same measurements on random days with no rating change by the three
                                          banks nearby
Output:   outputs/table_1_bank_comparison.csv   how big the stock's move is, by bank, next to ordinary days
          outputs/table_2_bank_tests.csv        is the gap between two banks real, or could it be luck?
          outputs/table_3_regression.csv        the same comparison in one regression, with controls
          outputs/table_4_direction.csv         did the stock move the way the bank said? day by day
          outputs/table_5_bank_profile.csv      what each bank's rating changes look like (stocks, years, earnings)

Step 4 (make_report.py) turns these tables into the figures and the report. This script only makes numbers.

THE KEY IDEAS
  Size of a move   The standardized move with its sign thrown away (the absolute value). 1.0 = one standard
                   deviation of that stock's moves, its usual swing (most ordinary moves are smaller), 2.0 = twice that.
                   The project asks on whose rating changes prices move MORE, not in which direction, so
                   size is the number we compare.
  Ordinary days    A size is never zero, even when nothing happens. The ordinary days (same stocks, same years,
                   no rating change by the three banks nearby) show what "nothing happened" looks like. Read
                   every size next to them.
  Clean events     Rating changes that are not next to an earnings announcement and have no other rating change
                   by these three banks next to them. There the move can most fairly be credited to one bank's
                   call, so the MAIN results use the clean events. Every result is also shown with all used
                   events. (Other brokers are not screened out of "clean"; one version below leaves out the
                   clean events that have another broker's change nearby.)
  Main window      Days -1..+1. FMP gives dates without times and some dates are a day off, more often for
                   one bank than another. Three days catch the move either way. Day 0 alone is shown beside it.
  95% interval     If history were re-run, where would the average land 95 times out of 100? We imitate that
                   by re-drawing the STOCKS at random, with repeats, 10,000 times, and keeping every event of
                   each stock drawn (a "bootstrap"). Re-drawing whole stocks, not single events, is the honest
                   way: ten rating changes on Tesla are not ten independent pieces of evidence.
                   The interval and the p-value below come from two different methods, so close to the bar
                   they can disagree; then go by the p-value. With only about 24 stocks the interval is also a
                   little too narrow (it holds the truth roughly 90 to 93 times in 100, not 95).
  p-value          The chance of seeing a gap this big if the two groups really were the same. Small (under
                   0.05) = unlikely to be luck. Three are computed for every gap between two groups:
                     p_clustered  do the AVERAGES differ, treating each stock as one block of evidence?
                                  This is the careful one. The report's YES / weak / no on the bank
                                  comparisons (tables 2 and 3) uses it.
                     p_averages   the same question with every event counted as independent (Welch t-test)
                     p_ranks      does one group TEND to have the bigger moves? (Mann-Whitney test. It only
                                  uses the order of the moves, so a few huge ones cannot swing it.)
                   Table 4 (did the stock move the way the bank said?) uses plain tests that count every
                   event as independent: its groups go down to 8 stocks, too few to treat stocks as blocks.
  Regression       All banks in one equation, holding other things equal (upgrade or downgrade, the year).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from build_dataset import BANKS
from build_events import OTHER_BROKER_DAYS             # how near another broker's change must be is set in build_events.py
from build_events import WINDOWS as EVENT_WINDOWS      # the day ranges of the run-up and the drift are set there too

# ---------------------------------------------------------------------------
# SETTINGS - change these to change the analysis
# ---------------------------------------------------------------------------
BASE_BANK = "Goldman Sachs"       # the bank every other bank is compared with
BOOTSTRAPS = 10000                # how many times the stocks are re-drawn for a confidence interval
SEED = 331                        # fixes the random re-draws, so every run gives the same intervals
POWER_FACTOR = 3.3                # a gap must be about 3.3 standard errors to be found 80% of the time by the main
                                  # test (bar p < 0.025 because two banks are compared with Goldman; about 24 stocks)

WINDOW_LABELS = {"3day": "days -1..+1", "day0": "day 0"}           # column ending in events.csv -> label
NEARBY = "a day" if OTHER_BROKER_DAYS == 1 else "%d days" % OTHER_BROKER_DAYS     # OTHER_BROKER_DAYS in words, for the labels
SAMPLES = {"clean": "clean events", "used": "all used events"}    # column in events.csv -> label

# The bank comparison is run several ways. The FIRST line is the main result, chosen before looking at
# the numbers. The others ask "does the answer survive if we measure it differently?"
#   (name, column in events.csv, which events)
VERSIONS = [
    ("MAIN: days -1..+1, clean events",                    "scar_3day",    "clean"),
    ("day 0 only",                                         "scar_day0",    "clean"),
    ("all used events (earnings and overlaps included)",   "scar_3day",    "used"),
    ("all used events, day 0 only",                        "scar_day0",    "used"),
    ("market model instead of stock minus S&P",            "scar_mm_3day", "clean"),
    ("without inconsistent histories",                     "scar_3day",    "clean_consistent"),
    ("no other broker's change within " + NEARBY,          "scar_3day",    "clean_alone"),
    ("percent move, not standardized",                     "car_3day",     "clean"),       # keep this one last
]

# Table 4: the stock's move in the bank's direction, window by window: label -> column
SINGLE_DAYS = [-3, -2, -1, 1, 2, 3]                               # day 0 is already a column in events.csv
RUNUP = "run-up, days %+d..%+d" % EVENT_WINDOWS["runup"]          # "run-up, days -10..-2"
DRIFT = "drift, days %+d..%+d" % EVENT_WINDOWS["drift"]           # "drift, days +2..+20"
MOVES = {
    RUNUP: "car_runup",
    "day -3": "day -3", "day -2": "day -2", "day -1": "day -1",
    "day 0": "car_day0",
    "day 0, overnight part (stock only)": "overnight",
    "day 0, intraday part (stock only)": "intraday",
    "day +1": "day +1", "day +2": "day +2", "day +3": "day +3",
    "days -1..+1": "car_3day",
    DRIFT: "car_drift",
}
CALLS = {"All calls": ["Upgrade", "Downgrade"], "Upgrades": ["Upgrade"], "Downgrades": ["Downgrade"]}

HERE = Path(__file__).resolve().parent
CLEAN = HERE / "data" / "clean"
OUTPUTS = HERE / "outputs"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_events():
    for name in ["events.csv", "event_days.csv", "ordinary_days.csv"]:
        if not (CLEAN / name).exists():
            sys.exit("Cannot find data/clean/%s. Run  python build_events.py  first (or  python run_all.py)." % name)
    events = pd.read_csv(CLEAN / "events.csv", parse_dates=["date"])
    events = events[events["status"] == "used"].copy()            # repeats and unmeasurable events stop here
    events["used"] = True
    if not events["clean"].any():
        sys.exit("STOP: no rating change is clean, so there is nothing to compare. This usually means the earnings dates "
                 "could not be downloaded: look for 'earnings' in logs/data_changes.csv, then run  python run_all.py  again.")
    events["clean_consistent"] = events["clean"] & ~events["inconsistent"]
    events["clean_alone"] = events["clean"] & ~events["other_broker"]     # no other broker's change nearby either

    # Add one column per single day around the event (day -3 ... day +3), from the day-by-day file.
    days = pd.read_csv(CLEAN / "event_days.csv")
    by_day = days.pivot(index="event_id", columns="day", values="abnormal")
    for day in SINGLE_DAYS:
        events["day %+d" % day] = events["event_id"].map(by_day[day])

    ordinary = pd.read_csv(CLEAN / "ordinary_days.csv", parse_dates=["date"])
    ordinary["used"] = True
    # The yardstick for clean events has no earnings days either (the same rule as for the events).
    ordinary["clean"] = ~ordinary["near_earnings"] & ordinary["earnings_known"]
    return events, ordinary


def pick(events, bank, calls):
    """The events of one bank ("All banks" = every bank) and one kind of call."""
    part = events[events["change"].isin(CALLS[calls])]
    return part if bank == "All banks" else part[part["bank"] == bank]


def sizes_of(events, column):
    """A small table with the size of each event's move (sign thrown away) and its stock."""
    scale = 100 if column.startswith("car_") else 1               # a plain return is shown in percent
    return pd.DataFrame({"ticker": events["ticker"], "size": events[column].abs() * scale}).dropna()


# ---------------------------------------------------------------------------
# Confidence intervals: re-draw whole stocks
# ---------------------------------------------------------------------------
def draw_stocks(stocks):
    """BOOTSTRAPS random re-draws of the stock list, with repeats. Each row holds the positions of the stocks drawn.
    The random numbers start from SEED on every call, so an interval depends only on its own data, not on
    which other intervals were computed before it."""
    return np.random.default_rng(SEED).integers(0, len(stocks), size=(BOOTSTRAPS, len(stocks)))


def redrawn_averages(sizes, stocks, draws):
    """The average size in every re-draw. A stock drawn twice brings all of its events twice.

    Example with 3 stocks: if one row of `draws` is [2, 0, 2], that re-draw holds stock 2 twice and stock 0
    once, so its average is (2 x total of stock 2 + total of stock 0) / (2 x count of stock 2 + count of stock 0).
    `total[draws]` looks up the total of every stock drawn, for all 10,000 re-draws at once."""
    total = sizes.groupby("ticker")["size"].sum().reindex(stocks, fill_value=0).to_numpy()
    count = sizes.groupby("ticker")["size"].count().reindex(stocks, fill_value=0).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):          # a re-draw with no event at all gives a blank
        return total[draws].sum(axis=1) / count[draws].sum(axis=1)


def interval(averages):
    """The middle 95% of the re-drawn averages."""
    low, high = np.nanpercentile(averages, [2.5, 97.5])
    return low, high


# ---------------------------------------------------------------------------
# Table 1: how big is the move, by bank, next to ordinary days?
# ---------------------------------------------------------------------------
def describe(part, ordinary, window):
    """Average and median size of the move for one group of events, and for the ordinary days matched to them."""
    sizes = sizes_of(part, "scar_" + window)
    if len(sizes) < 2:
        return {"events": len(sizes)}
    stocks = sorted(sizes["ticker"].unique())
    low, high = interval(redrawn_averages(sizes, stocks, draw_stocks(stocks)))
    matched = ordinary.loc[ordinary["matched_event_id"].isin(part["event_id"]), "scar_" + window].abs()
    percent = part["car_" + window].abs() * 100
    return {"events": len(sizes), "stocks": len(stocks), "mean_size": sizes["size"].mean(), "ci_low": low, "ci_high": high,
            "median_size": sizes["size"].median(), "ordinary_mean_size": matched.mean(), "ordinary_median_size": matched.median(),
            "times_ordinary": sizes["size"].mean() / matched.mean(),
            "mean_move_pct": percent.mean(), "median_move_pct": percent.median()}


def bank_comparison(events, ordinary):
    rows = []
    for sample, sample_label in SAMPLES.items():
        for window, window_label in WINDOW_LABELS.items():
            for bank in ["All banks"] + list(BANKS):
                for calls in CALLS:
                    part = pick(events[events[sample]], bank, calls)
                    rows.append({"events_included": sample_label, "window": window_label, "bank": bank, "calls": calls,
                                 **describe(part, ordinary[ordinary[sample]], window)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 2: is the gap between two groups real?
# ---------------------------------------------------------------------------
def clustered_gap(a, b):
    """The gap between two averages, with every stock treated as one block of evidence.
    Done as a tiny regression: size = level of group b + gap x (the event is in group a)."""
    both = pd.concat([a.assign(in_a=1), b.assign(in_a=0)], ignore_index=True)
    stock_number = pd.factorize(both["ticker"])[0]
    fit = smf.ols("size ~ in_a", data=both).fit(cov_type="cluster", cov_kwds={"groups": stock_number}, use_t=True)
    return fit.bse["in_a"], fit.pvalues["in_a"]


def compare(a, b):
    """Group a against group b: the gap between their averages, its 95% interval, and the three p-values."""
    if len(a) < 2 or len(b) < 2:
        return {"n_a": len(a), "n_b": len(b)}
    stocks = sorted(set(a["ticker"]) | set(b["ticker"]))
    draws = draw_stocks(stocks)                                   # the SAME re-draws for both groups
    low, high = interval(redrawn_averages(a, stocks, draws) - redrawn_averages(b, stocks, draws))
    standard_error, p_clustered = clustered_gap(a, b)
    ranks = stats.mannwhitneyu(a["size"], b["size"], alternative="two-sided")
    return {"n_a": len(a), "n_b": len(b), "mean_a": a["size"].mean(), "mean_b": b["size"].mean(),
            "median_a": a["size"].median(), "median_b": b["size"].median(),
            "gap": a["size"].mean() - b["size"].mean(), "gap_low": low, "gap_high": high,
            "p_clustered": p_clustered,
            "p_averages": stats.ttest_ind(a["size"], b["size"], equal_var=False).pvalue,     # Welch t-test
            "p_ranks": ranks.pvalue,                                                             # Mann-Whitney test
            "chance_a_is_larger": ranks.statistic / (len(a) * len(b)),      # pick one event from each group: how often is a's bigger?
            "detectable_gap": POWER_FACTOR * standard_error}                # a real gap of this size is found about 80% of the time; smaller gaps are missed more often


def leave_one_stock_out(sizes, bank_a, bank_b):
    """Drop each stock in turn and measure the gap again. If one stock drives the result, the gap swings a lot."""
    def gap(table):
        return table.loc[table["bank"] == bank_a, "size"].mean() - table.loc[table["bank"] == bank_b, "size"].mean()
    gaps = pd.Series({ticker: gap(sizes[sizes["ticker"] != ticker]) for ticker in sizes["ticker"].unique()})
    return {"drop_one_stock_gap_low": gaps.min(), "drop_one_stock_gap_high": gaps.max(),
            "drop_one_stock_biggest_swing": (gaps - gap(sizes)).abs().idxmax()}


def bank_tests(events):
    others = [bank for bank in BANKS if bank != BASE_BANK]
    rows = []
    for version, column, sample in VERSIONS:
        sizes = sizes_of(events[events[sample]], column).join(events[["bank", "change"]])
        by_bank = {bank: sizes[sizes["bank"] == bank] for bank in BANKS}

        # Hypothesis 1: is the move different for Goldman Sachs than for each other bank?
        for other in others:
            row = {"version": version, "question": BASE_BANK + " vs " + other, "group_a": BASE_BANK, "group_b": other,
                   **compare(by_bank[BASE_BANK], by_bank[other])}
            if version == VERSIONS[0][0]:
                row.update(leave_one_stock_out(sizes, BASE_BANK, other))
            rows.append(row)
        # ... and do the three banks differ at all? (Kruskal-Wallis: the Mann-Whitney idea for three groups)
        rows.append({"version": version, "question": "All three banks", "group_a": "", "group_b": "",
                     "p_ranks": stats.kruskal(*[table["size"] for table in by_bank.values()]).pvalue})

        # Hypothesis 2: are the moves bigger for downgrades than for upgrades?
        for bank in ["All banks"] + list(BANKS):
            rows.append({"version": version, "question": "Downgrades vs upgrades, " + bank, "group_a": "Downgrades", "group_b": "Upgrades",
                         **compare(pick(sizes, bank, "Downgrades"), pick(sizes, bank, "Upgrades"))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 3: one regression with controls
# ---------------------------------------------------------------------------
def regression(events, column, label, control_earnings):
    """size = a + b1 x (bank is Morgan Stanley) + b2 x (bank is JP Morgan) + b3 x (downgrade) + year effects

    Goldman Sachs has no term of its own, so b1 and b2 read as "this bank's moves are b bigger than Goldman's,
    holding the other things equal". Year effects let every calendar year have its own level.
    Standard errors are clustered by stock (each stock is one block of evidence)."""
    others = [bank for bank in BANKS if bank != BASE_BANK]
    table = pd.DataFrame({"size": events[column].abs(),
                          "downgrade": (events["change"] == "Downgrade").astype(int),
                          "near_earnings": events["near_earnings"].astype(int),
                          "year": events["date"].dt.year.astype(str),
                          "ticker": events["ticker"]})
    names = {"downgrade": "Downgrade vs upgrade", "near_earnings": "Near earnings vs not"}
    terms = []
    for bank in others:
        term = "is_" + BANKS[bank]
        table[term] = (events["bank"] == bank).astype(int)        # 1 if this bank made the call, else 0
        names[term] = bank + " vs " + BASE_BANK
        terms.append(term)
    terms.append("downgrade")
    if control_earnings:
        terms.append("near_earnings")
    table = table.dropna()

    stock_number = pd.factorize(table["ticker"])[0]               # one number per stock, for the clustering
    fit = smf.ols("size ~ " + " + ".join(terms) + " + C(year)", data=table).fit(
        cov_type="cluster", cov_kwds={"groups": stock_number}, use_t=True)

    limits = fit.conf_int()
    return [{"regression": label, "term": names[term], "coefficient": fit.params[term], "std_error": fit.bse[term],
             "ci_low": limits.loc[term, 0], "ci_high": limits.loc[term, 1], "p_value": fit.pvalues[term],
             "events": int(fit.nobs), "stocks": table["ticker"].nunique(), "r_squared": fit.rsquared} for term in terms]


def regressions(events):
    clean = events[events["clean"]]
    rows = regression(clean, "scar_3day", "MAIN: size, days -1..+1, clean events", control_earnings=False)
    rows += regression(clean, "scar_day0", "size, day 0, clean events", control_earnings=False)
    rows += regression(events, "scar_3day", "size, days -1..+1, all used events", control_earnings=True)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 4: did the stock move the way the bank said?
# ---------------------------------------------------------------------------
def direction_table(events, ordinary):
    """The move 'in the bank's direction': the return for an upgrade, minus the return for a downgrade.
    Positive = the stock went the way the bank said. Tested two ways: is the average different from zero
    (t-test), and is the share that moved the right way different from 50%, a coin flip (sign test)?
    Both are plain tests that count every event as independent (unlike p_clustered in table 2).

    The 'Ordinary days' rows are the plain move (no direction to flip) on the ordinary days matched to the
    same events, as in table 1. They are not zero over long windows, because these 25 stocks beat the
    S&P 500 over the sample. Compare the run-up and the drift with them."""
    rows = []
    for sample, sample_label in SAMPLES.items():
        matched = ordinary[sample] & ordinary["matched_event_id"].isin(events.loc[events[sample], "event_id"])   # the same yardstick as table 1
        for bank in ["All banks"] + list(BANKS):
            for calls in CALLS:
                part = pick(events[events[sample]], bank, calls)
                for label, column in MOVES.items():
                    move = (part[column] * part["direction"]).dropna() * 100
                    row = {"events_included": sample_label, "bank": bank, "calls": calls, "window": label, "events": len(move)}
                    if len(move) >= 2:
                        right = int((move > 0).sum())
                        row.update({"mean_move_pct": move.mean(), "median_move_pct": move.median(), "share_right": right / len(move),
                                    "p_average": stats.ttest_1samp(move, 0).pvalue,
                                    "p_share": stats.binomtest(right, len(move), 0.5).pvalue})
                    rows.append(row)
        for label, column in MOVES.items():
            if column in ordinary.columns:
                move = ordinary.loc[matched, column].dropna() * 100
                rows.append({"events_included": sample_label, "bank": "Ordinary days", "calls": "No rating change", "window": label,
                             "events": len(move), "mean_move_pct": move.mean(), "median_move_pct": move.median()})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Table 5: what do each bank's rating changes look like?
# ---------------------------------------------------------------------------
def bank_profile(events):
    """The banks do not rate the same stocks at the same times. This table shows how their events differ,
    because a gap between banks can come from WHAT and WHEN they rate, not from how much weight their view carries."""
    rows = []
    for bank in ["All banks"] + list(BANKS):
        mine = pick(events, bank, "All calls")
        clean = mine[mine["clean"]]
        busiest = mine["ticker"].value_counts()                   # stocks, busiest first
        busiest_clean = clean["ticker"].value_counts()
        rows.append({"bank": bank, "used_events": len(mine), "clean_events": len(clean),
                     "stocks": mine["ticker"].nunique(),
                     "share_in_3_busiest_stocks": busiest.head(3).sum() / len(mine),
                     "busiest_stocks": " ".join(busiest.head(3).index),       # if stocks tie for third place, the first is named; the share is the same either way
                     "stocks_clean": clean["ticker"].nunique(),
                     "share_in_3_busiest_stocks_clean": busiest_clean.head(3).sum() / len(clean),
                     "share_downgrades": (mine["change"] == "Downgrade").mean(),
                     "share_near_earnings": mine["near_earnings"].mean(),
                     "share_overlapping": mine["overlap"].mean(),
                     "share_inconsistent_history": mine["inconsistent"].mean(),
                     "share_clean_with_other_broker": clean["other_broker"].mean(),
                     "median_typical_day_pct": mine["typical_day"].median() * 100,
                     "median_year": int(mine["date"].dt.year.median()),       # a half year is rounded down
                     "first_event": mine["date"].min().date(), "last_event": mine["date"].max().date()})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------
def main():
    if len(BANKS) != 3 or BASE_BANK not in BANKS:
        sys.exit("The study is written for exactly three banks, one of them %s (BASE_BANK in analyze_events.py). "
                 "Check BANKS in build_dataset.py." % BASE_BANK)
    events, ordinary = load_events()
    OUTPUTS.mkdir(exist_ok=True)
    tables = {
        "table_1_bank_comparison.csv": bank_comparison(events, ordinary),
        "table_2_bank_tests.csv": bank_tests(events),
        "table_3_regression.csv": regressions(events),
        "table_4_direction.csv": direction_table(events, ordinary),
        "table_5_bank_profile.csv": bank_profile(events),
    }
    for name, table in tables.items():
        table.round(6).to_csv(OUTPUTS / name, index=False)        # 6 decimals: a saved p-value of 0 means "below 0.0000005"
        print("Saved outputs/%s (%d rows)" % (name, len(table)))

    main_rows = tables["table_1_bank_comparison.csv"]
    main_rows = main_rows[(main_rows["events_included"] == "clean events") & (main_rows["window"] == "days -1..+1") & (main_rows["calls"] == "All calls")]
    print("\nMAIN RESULT. Size of the stock's move over days -1..+1, clean events (1.0 = that stock's usual 3-day swing, one standard deviation):")
    print(main_rows[["bank", "events", "mean_size", "ci_low", "ci_high", "median_size", "ordinary_mean_size", "times_ordinary"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
