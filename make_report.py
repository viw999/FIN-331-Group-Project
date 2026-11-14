"""Step 4 of the pipeline: turn the tables into two figures and one report in plain words.

Run:      python make_report.py           (after analyze_events.py, or run every step with  python run_all.py)
Input:    outputs/table_1 ... table_5     the numbers (made by step 3)
          data/clean/events.csv, data/clean/event_days.csv, data/clean/dataset.csv, logs/data_changes.csv
Output:   outputs/report.txt                     READ THIS FIRST. It also prints on the screen.
          outputs/figure_1_event_study.png       the average path of the stock from day -10 to day +20
          outputs/figure_2_bank_comparison.png   the size of the move by bank, next to ordinary days

THE REPORT HAS FOUR PARTS
  1. CAVEATS             what to be careful about, with this run's numbers and a cheap check where one exists
  2. THE SHORT VERSION   the project's questions answered in plain sentences
  3. THE DETAILS         the tables behind the answers
  4. THE PAPER TRAIL     every place where data was left out, changed or flagged

This script computes nothing new about the banks. The bank comparisons are read from the tables that
step 3 saved, so the report and the tables cannot disagree. The counts in the caveats and the list of
the biggest moves come from data/clean/events.csv and from the log. The wording is chosen by the numbers
(for example "YES" only when the p-value is small), so it stays right when the data is rebuilt.

A NOTE ON WORDS
  The report says prices "move more on a bank's rating-change days". It does not say the bank "caused" the
  move: analysts often change a rating because of news, and that news moves the price too.
"""
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # draw straight to a file; no window needed
import matplotlib.pyplot as plt
import pandas as pd

from analyze_events import BASE_BANK, DRIFT, NEARBY, RUNUP, VERSIONS
from build_dataset import BANKS, BREAK_TEXT, STOCKS, TWICE_TEXT
from build_events import (CHART_DAYS, EARNINGS_DAYS_AFTER, EARNINGS_DAYS_BEFORE, ESTIMATION, MIN_ESTIMATION_DAYS,
                          OTHER_BROKER_DAYS, QUIET_DAYS, REPEAT_DAYS, REPEAT_KEEP, WINDOWS)
from data_log import LOG_FILE, read_log

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
SIGNIFICANCE = 0.05          # a p-value below this counts as "statistically significant" (YES)
WEAK = 0.10                  # below this: "weak" (borderline)
MAIN_TESTS = 2               # Goldman is compared with TWO banks, so each of those comparisons gets half the usual allowance
                             # (POWER_FACTOR in analyze_events.py, and the words "missed about 1 time in 5" in caveat 4, are
                             #  worked out for SIGNIFICANCE / MAIN_TESTS = 0.025: if you change either one, change those too)
WIDTH = 100                  # characters per line of the report

MAIN, MAIN_COLUMN, MAIN_EVENTS = VERSIONS[0]     # the first version in analyze_events.py is the main one
MAIN_SAMPLE, ALL_SAMPLE = "clean events", "all used events"
MAIN_WINDOW = "days -1..+1"
OTHERS = [bank for bank in BANKS if bank != BASE_BANK]
RUNUP_DAYS = WINDOWS["runup"][1] - WINDOWS["runup"][0] + 1       # how many trading days the run-up window holds
DRIFT_DAYS = WINDOWS["drift"][1] - WINDOWS["drift"][0] + 1

# Chart colours (checked for colour-blind safety). One fixed colour per bank, the same in both figures.
BANK_COLOR = dict(zip(BANKS, ["#2a78d6", "#eb6834", "#1baf7a"]))
SURFACE, INK, INK_SOFT, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"

HERE = Path(__file__).resolve().parent
CLEAN = HERE / "data" / "clean"
OUTPUTS = HERE / "outputs"
REPORT = []                  # every line we print is also kept here, so it can be saved to a file


# ---------------------------------------------------------------------------
# Small helpers for printing
# ---------------------------------------------------------------------------
def say(text=""):
    """Print a line and remember it for the saved report."""
    text = text.rstrip()                      # no stray spaces at the end of a table row
    print(text)
    REPORT.append(text)


def say_wrapped(text, first="", rest=""):
    """Print a long sentence, wrapped onto several lines. `first` indents line 1, `rest` indents the others."""
    for line in textwrap.wrap(text, width=WIDTH, initial_indent=first, subsequent_indent=rest):
        say(line)


def heading(text, mark="="):
    say(mark * WIDTH)
    say(text)
    say(mark * WIDTH)


def one(table, **where):
    """The single row of a table that matches, e.g. one(sizes, bank="Goldman Sachs", calls="All calls")."""
    rows = table
    for column, value in where.items():
        rows = rows[rows[column] == value]
    if len(rows) != 1:
        sys.exit("Expected exactly one row for %s but found %d. Was a table changed without changing make_report.py?" % (where, len(rows)))
    return rows.iloc[0]


def show_p(p):
    """A p-value for a table cell. Very small values print as '<0.001' instead of '0.000'."""
    if p < 0.001:
        return "<0.001"
    bars = [SIGNIFICANCE, WEAK, SIGNIFICANCE / MAIN_TESTS, WEAK / MAIN_TESTS]
    if round(p, 4) in bars:                  # 0.02496 would still print as 0.0250: show all six decimals of the table
        return "%.6f" % p
    if round(p, 3) in bars:                  # 0.0249 must not print as 0.025 next to a YES that needs "under 0.025"
        return "%.4f" % p
    return "%.3f" % p


def verdict(p, tests=1):
    """Turn a p-value into a plain word: YES = unlikely to be luck, weak = borderline, no = could easily be luck.
    When `tests` comparisons share one question, each gets 1/tests of the allowance (0.05 / 2 = 0.025 for two)."""
    if p < SIGNIFICANCE / tests:
        return "YES"
    if p < WEAK / tests:
        return "weak"
    return "no"


def verdict_cell(p, tests=1):
    """For the tables, e.g. 'YES (0.009)' or 'no (0.250)'."""
    return "%s (%s)" % (verdict(p, tests), show_p(p))


def bigger_or_smaller(gap):
    """Say a gap in words, e.g. '0.15 smaller' or '0.30 bigger'."""
    return "%.2f %s" % (abs(gap), "bigger" if gap > 0 else "smaller")


def version_named(column, sample):
    """The name of the version in analyze_events.VERSIONS that uses this column of events.csv and these events."""
    for name, its_column, its_sample in VERSIONS:
        if (its_column, its_sample) == (column, sample):
            return name
    sys.exit("make_report.py needs a version with column %s and events %s in analyze_events.VERSIONS." % (column, sample))


def and_list(words):
    """'a, b and c'"""
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def missing_stocks(prices):
    """The stocks in the STOCKS setting that are not in the dataset (their download failed in step 1)."""
    return sorted(set(STOCKS) - set(prices["ticker"]))


def list_banks(text_for_bank):
    """Join one short text per bank, e.g. 'Goldman Sachs 61, Morgan Stanley 78, JP Morgan 39'."""
    return ", ".join("%s %s" % (bank, text_for_bank(bank)) for bank in BANKS)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load():
    needed = ["table_1_bank_comparison.csv", "table_2_bank_tests.csv", "table_3_regression.csv", "table_4_direction.csv", "table_5_bank_profile.csv"]
    missing = [name for name in needed if not (OUTPUTS / name).exists()]
    if missing:
        sys.exit("Cannot find outputs/%s. Run  python analyze_events.py  first (or  python run_all.py)." % missing[0])
    for file in [CLEAN / "events.csv", CLEAN / "event_days.csv", CLEAN / "dataset.csv", LOG_FILE]:
        if not file.exists():
            sys.exit("Cannot find %s. Run  python run_all.py." % file.relative_to(HERE).as_posix())     # e.g. data/clean/events.csv
    tables = {name.split("_")[1]: pd.read_csv(OUTPUTS / name) for name in needed}       # "1" ... "5"
    events = pd.read_csv(CLEAN / "events.csv", parse_dates=["date"])
    days = pd.read_csv(CLEAN / "event_days.csv")
    prices = pd.read_csv(CLEAN / "dataset.csv", usecols=["ticker", "date"])
    return tables, events, days, prices, read_log()


# ---------------------------------------------------------------------------
# The figures
# ---------------------------------------------------------------------------
def style(ax):
    """The quiet look: light horizontal grid, no box, soft axis text. The data is the only loud thing."""
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_SOFT, length=0, labelsize=9)


def figure_event_study(events, days):
    """Figure 1: the average cumulative abnormal return from day -10 to day +20 around clean rating changes."""
    clean = events[events["clean"]]
    days = days.merge(clean[["event_id", "bank", "change"]], on="event_id")
    length = CHART_DAYS[1] - CHART_DAYS[0] + 1
    complete = days.groupby("event_id")["abnormal"].count() == length             # leave out events near the end of the prices
    left_out = int((~complete).sum())
    days = days[days["event_id"].isin(complete[complete].index)].sort_values(["event_id", "day"])
    days["cumulative"] = days.groupby("event_id")["abnormal"].cumsum() * 100       # add up from day -10 on, in percent

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True, facecolor=SURFACE)
    for ax, change in zip(axes, ["Upgrade", "Downgrade"]):
        style(ax)
        ax.axhline(0, color=AXIS, linewidth=1)
        ax.axvline(0, color=AXIS, linewidth=1)
        for bank in BANKS:
            mine = days[(days["bank"] == bank) & (days["change"] == change)]
            path = mine.groupby("day")["cumulative"].mean()
            ax.plot(path.index, path.values, color=BANK_COLOR[bank], linewidth=2, solid_capstyle="round",
                    label="%s (%d)" % (bank, mine["event_id"].nunique()))
        ax.set_title(change + "s", loc="left", fontsize=11, color=INK, fontweight="bold")
        ax.set_xlabel("Trading days from the rating change (day 0)", fontsize=9, color=INK_SOFT)
        ax.legend(frameon=False, fontsize=9, labelcolor=INK_SOFT, loc="upper left" if change == "Upgrade" else "upper right",
                  title="Bank (number of changes)", title_fontsize=8)
    axes[0].set_ylabel("Stock minus S&P 500, running total (%)", fontsize=9, color=INK_SOFT)
    axes[0].text(0.3, axes[0].get_ylim()[0], " day 0", fontsize=8, color=INK_SOFT, va="bottom")
    figure.suptitle("The stock's average path around a rating change", x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
    figure.text(0.01, 0.905, "Clean rating changes only (not next to earnings or to another change by these three banks). "
                "Each line is one bank's average.", fontsize=9, color=INK_SOFT)
    figure.text(0.01, 0.865, "Before and after the change, zero is not the yardstick: compare with the ordinary days in Q5 of report.txt.",
                fontsize=9, color=INK_SOFT)
    if left_out:                              # a footnote, so the counts in the legends can be matched to the report
        figure.text(0.01, 0.012, "Left out of this figure: %d recent change%s that %s not have %d later trading days yet." % (
            left_out, "" if left_out == 1 else "s", "does" if left_out == 1 else "do", CHART_DAYS[1]), fontsize=8, color=INK_SOFT)
    figure.tight_layout(rect=(0, 0.03, 1, 0.9))
    figure.savefig(OUTPUTS / "figure_1_event_study.png", dpi=150, facecolor=SURFACE)
    plt.close(figure)


def figure_bank_comparison(sizes):
    """Figure 2: the average size of the move by bank with its 95% interval, next to ordinary days."""
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True, facecolor=SURFACE)
    panels = [(MAIN_SAMPLE, "Clean rating changes (the main result)"),
              (ALL_SAMPLE, "All used rating changes (earnings days and overlaps included)")]
    for ax, (sample, title) in zip(axes, panels):
        style(ax)
        ordinary = one(sizes, events_included=sample, window=MAIN_WINDOW, bank="All banks", calls="All calls")["ordinary_mean_size"]
        ax.axhline(ordinary, color=INK_SOFT, linewidth=1)
        ax.set_xlabel("Dark line = ordinary days (%.2f)" % ordinary, fontsize=9, color=INK_SOFT)    # under the panel, so it cannot sit on a dot
        labels = []
        for position, bank in enumerate(BANKS):
            row = one(sizes, events_included=sample, window=MAIN_WINDOW, bank=bank, calls="All calls")
            ax.plot([position, position], [row["ci_low"], row["ci_high"]], color=BANK_COLOR[bank], linewidth=2, solid_capstyle="round")
            ax.plot(position, row["mean_size"], "o", color=BANK_COLOR[bank], markersize=10, markeredgecolor=SURFACE, markeredgewidth=2)
            ax.text(position + 0.09, row["mean_size"], "%.2f" % row["mean_size"], fontsize=10, color=INK, va="center")
            labels.append("%s\n%d changes" % (bank, row["events"]))
        ax.set_xticks(range(len(BANKS)))
        ax.set_xticklabels(labels, fontsize=9, color=INK_SOFT)
        ax.set_xlim(-0.5, len(BANKS) - 0.5)
        ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold")
    tallest = sizes.loc[(sizes["window"] == MAIN_WINDOW) & (sizes["calls"] == "All calls") & sizes["bank"].isin(BANKS), "ci_high"].max()
    axes[0].set_ylim(bottom=0, top=tallest * 1.08)                # a little room above the longest bar
    axes[0].set_ylabel("Size of the move (1.0 = one standard deviation)", fontsize=9, color=INK_SOFT)
    figure.suptitle("How big is the stock's move around a rating change, by bank?", x=0.01, ha="left", fontsize=13, color=INK, fontweight="bold")
    figure.text(0.01, 0.905, "Days -1..+1, stock minus S&P 500, divided by the stock's usual swing (one standard deviation), sign dropped. "
                "Dot = average. Bar = 95% interval.", fontsize=9, color=INK_SOFT)
    figure.tight_layout(rect=(0, 0, 1, 0.9))
    figure.savefig(OUTPUTS / "figure_2_bank_comparison.png", dpi=150, facecolor=SURFACE)
    plt.close(figure)


# ---------------------------------------------------------------------------
# Facts used in more than one part of the report
# ---------------------------------------------------------------------------
def gap_story(tests, version, other):
    """The Goldman-vs-other row of one version, plus the answer in one word:
    'bigger', 'smaller' (Goldman's moves, and unlikely to be luck) or 'same' (cannot be told apart).
    Every version compares Goldman with two banks, so every version is judged with the halved bar."""
    row = one(tests, version=version, question=BASE_BANK + " vs " + other)
    if verdict(row["p_clustered"], MAIN_TESTS) != "YES":
        return row, "same"
    return row, "bigger" if row["gap"] > 0 else "smaller"


def robustness(tests):
    """For every other version: does it give the same answer as the main one, for both banks?"""
    main_answers = [gap_story(tests, MAIN, other)[1] for other in OTHERS]
    agree, differ = [], []
    for version, _, _ in VERSIONS[1:]:
        answers = [gap_story(tests, version, other)[1] for other in OTHERS]
        if answers == main_answers:
            agree.append(version)
        else:
            notes = ["%s's moves %s than %s's (p = %s)" % (BASE_BANK, answer, other, show_p(gap_story(tests, version, other)[0]["p_clustered"]))
                     if answer != "same" else "%s and %s cannot be told apart" % (BASE_BANK, other)
                     for other, answer in zip(OTHERS, answers)]
            differ.append("%s: %s" % (version, "; ".join(notes)))
    return agree, differ


def downgrade_answer(row):
    """The answer to 'are the moves bigger for downgrades than for upgrades?' from one row of table 2."""
    if verdict(row["p_clustered"]) != "YES":
        return "NO CLEAR DIFFERENCE"
    return "YES" if row["gap"] > 0 else "NO. UPGRADES ARE BIGGER"


def same_or_not(tests, version):
    """A short phrase for a CHECK sentence: does `version` answer the main question like the main version does?"""
    agree, _ = robustness(tests)
    return "the same" if version in agree else "DIFFERENT (see the short version, Q2)"


# ---------------------------------------------------------------------------
# Part 1 of the report: the caveats
# ---------------------------------------------------------------------------
def print_caveats(tables, events, prices, log):
    sizes, tests, direction, profile = tables["1"], tables["2"], tables["4"], tables["5"]
    used = events[events["status"] == "used"]
    clean = used[used["clean"]]
    number = iter(range(1, 20))
    heading("#  CAVEATS - READ THESE FIRST", "#")

    # ---- what was left out (the sentence is built piece by piece, so each number sits next to its words)
    same_day = one(log, what=TWICE_TEXT)                       # step 1 dropped these, so they are not in events.csv
    listed = int(same_day["out_of"])                           # every upgrade and downgrade FMP lists for the three banks
    repeats = int((events["status"] == "repeat listing").sum())
    twice = repeats + int(same_day["rows"])
    too_new = int((events["status"] == "too little price history").sum())
    other_out = listed - len(used) - twice - too_new
    unknown = int((~used["earnings_known"]).sum())
    several = (used["near_earnings"].astype(int) + used["overlap"].astype(int) + (~used["earnings_known"]).astype(int) > 1).any()
    missing = missing_stocks(prices)

    parts = []
    if missing:
        parts.append("%d OF OUR %d STOCKS ARE MISSING because their download failed (%s): run  python run_all.py  again."
                     % (len(missing), len(STOCKS), ", ".join(missing)))
    parts.append("FMP lists %d upgrades and downgrades by the three banks, on %d of our %d stocks."
                 % (listed, events["ticker"].nunique(), len(STOCKS)))
    parts.append("%d were listed twice and are counted once." % twice)
    parts.append("%d have too few earlier prices to measure a typical day (fewer than %d trading days)." % (too_new, MIN_ESTIMATION_DAYS))
    if other_out:
        parts.append("%d more %s left out for other reasons." % (other_out, "was" if other_out == 1 else "were"))
    parts.append("That leaves %d used changes (%s)." % (len(used), list_banks(lambda bank: str(int((used["bank"] == bank).sum())))))
    reasons = ["%d near an earnings announcement" % int(used["near_earnings"].sum()),
               "%d next to another rating change by these banks on the same stock" % int(used["overlap"].sum())]
    if unknown:
        reasons.append("%d on stocks whose earnings dates could not be checked" % unknown)
    parts.append("%d of them are not clean (%s%s), so the main results rest on %d clean changes (%s)."
                 % (len(used) - len(clean), ", ".join(reasons), "; some are both" if several else "",
                    len(clean), list_banks(lambda bank: str(int((clean["bank"] == bank).sum())))))
    parts.append("Every step that drops or flags rows is listed in THE PAPER TRAIL at the end.")
    say_wrapped("%d. DATA LEFT OUT. %s" % (next(number), " ".join(parts)), rest="   ")
    say()

    # ---- earnings
    near = used[used["near_earnings"]]
    biggest = used.assign(size=used["scar_3day"].abs()).nlargest(10, "size")
    share_of_movement = near["scar_3day"].abs().sum() / used["scar_3day"].abs().sum()
    by_chance = (EARNINGS_DAYS_BEFORE + EARNINGS_DAYS_AFTER + 1) * 4 / 252
    say_wrapped("%d. EARNINGS NEWS IS MIXED IN. %d of the %d used changes (%.0f%%) came out from %d trading day before to %d after "
                "an earnings announcement (%s). By pure chance it would be about %.0f%%. Those %d changes carry %.0f%% of all the "
                "movement, and %d of the 10 biggest moves are among them. On those days the stock is reacting to the earnings, "
                "not only to the bank, so they are left out of the main results. FMP gives earnings dates without times, "
                "so the rule is deliberately wide. CHECK: with all used changes included, the answer to the main question is %s."
                % (next(number), len(near), len(used), 100 * len(near) / len(used), EARNINGS_DAYS_BEFORE, EARNINGS_DAYS_AFTER,
                   list_banks(lambda bank: "%.0f%%" % (100 * one(profile, bank=bank)["share_near_earnings"])),
                   100 * by_chance, len(near), 100 * share_of_movement, int(biggest["near_earnings"].sum()),
                   same_or_not(tests, version_named(MAIN_COLUMN, "used"))), rest="   ")
    say()

    # ---- other brokers
    shared = clean[clean["other_broker"]]
    say_wrapped("%d. OTHER BROKERS ARE MIXED IN TOO. 'Clean' only screens out earnings and these three banks. %d of the %d clean "
                "changes (%.0f%%) have an upgrade or downgrade by some OTHER broker within %d trading day%s (%s). On those days we "
                "cannot say whose call moved the stock. They are kept in the main results. "
                "CHECK: without them the answer to the main question is %s."
                % (next(number), len(shared), len(clean), 100 * len(shared) / len(clean), OTHER_BROKER_DAYS,
                   "" if OTHER_BROKER_DAYS == 1 else "s",
                   list_banks(lambda bank: "%.0f%%" % (100 * one(profile, bank=bank)["share_clean_with_other_broker"])),
                   same_or_not(tests, version_named(MAIN_COLUMN, "clean_alone"))), rest="   ")
    say()

    # ---- small sample, many tests
    all_banks = one(sizes, events_included=MAIN_SAMPLE, window=MAIN_WINDOW, bank="All banks", calls="All calls")
    detectable = {other: one(tests, version=MAIN, question=BASE_BANK + " vs " + other)["detectable_gap"] for other in OTHERS}
    p_values = sum(int(table[column].notna().sum()) for table in [tests, tables["3"], direction] for column in table.columns if column.startswith("p_"))
    say_wrapped("%d. SMALL SAMPLE, MANY TESTS. With this few clean changes, a real gap of about %.2f between %s and %s (about %.2f "
                "between %s and %s) would still be missed about 1 time in 5, and smaller gaps more often. For scale: the whole effect of a rating "
                "change is %.2f (average size %.2f against %.2f on ordinary days). So 'no significant difference' does NOT mean "
                "'the banks are the same'. The tables in outputs/ hold %d p-values, and about %d of them would be under %.2f by "
                "luck alone. Only two were named in advance as the main test (%s against each other bank), and because there "
                "are two, each needs p under %.3f to count as YES. Be suspicious of a lone YES in a small group."
                % (next(number), detectable[OTHERS[0]], BASE_BANK, OTHERS[0], detectable[OTHERS[1]], BASE_BANK, OTHERS[1],
                   all_banks["mean_size"] - all_banks["ordinary_mean_size"], all_banks["mean_size"], all_banks["ordinary_mean_size"],
                   p_values, round(p_values * SIGNIFICANCE), SIGNIFICANCE, BASE_BANK, SIGNIFICANCE / MAIN_TESTS), rest="   ")
    say()

    # ---- few stocks
    swings = []
    for other in OTHERS:
        row = one(tests, version=MAIN, question=BASE_BANK + " vs " + other)
        flips = (row["drop_one_stock_gap_low"] < 0) != (row["drop_one_stock_gap_high"] < 0)
        swings.append("the %s minus %s gap stays between %+.2f and %+.2f (%s)" % (
            BASE_BANK, other, row["drop_one_stock_gap_low"], row["drop_one_stock_gap_high"],
            "its sign CHANGES, so one stock can flip the ranking" if flips else "its sign never changes"))
    say_wrapped("%d. FEW STOCKS, AND EVENTS ARE NOT INDEPENDENT. The clean changes come from %d stocks, and each bank's are "
                "bunched in a few of them (share of its clean changes in its 3 busiest stocks: %s). Ten changes on one stock are "
                "not ten independent pieces of evidence, so the 95%% intervals and the YES / no verdicts on the bank comparisons "
                "(sections B and C) treat each stock as one block. CHECK: leaving out any one stock, %s."
                % (next(number), clean["ticker"].nunique(),
                   list_banks(lambda bank: "%.0f%%" % (100 * one(profile, bank=bank)["share_in_3_busiest_stocks_clean"])),
                   " and ".join(swings)), rest="   ")
    say()

    # ---- dates, not times
    day = {label: one(direction, events_included=MAIN_SAMPLE, bank="All banks", calls="All calls", window=label)
           for label in ["day -1", "day 0", "day +1"]}
    say_wrapped("%d. DATES, NOT TIMES. FMP gives the day of a rating change but not the time, and some days are off by one. "
                "%d changes were listed on two different days, at most %d trading days apart; we kept the %s day (step 2 prints the stock's move on both "
                "days). The average move in the bank's direction is %+.2f%% on day 0, against %+.2f%% the day before and %+.2f%% "
                "the day after. The main results use days -1..+1 so that a date that is one day off still counts. "
                "CHECK: on day 0 alone the answer to the main question is %s."
                % (next(number), repeats, REPEAT_DAYS, REPEAT_KEEP, day["day 0"]["mean_move_pct"], day["day -1"]["mean_move_pct"],
                   day["day +1"]["mean_move_pct"], same_or_not(tests, version_named("scar_day0", MAIN_EVENTS))), rest="   ")
    say()

    # ---- incomplete history
    rates = {bank: one(log, what=bank + BREAK_TEXT) for bank in BANKS}
    say_wrapped("%d. FMP'S HISTORY IS INCOMPLETE, AND NOT EQUALLY FOR EVERY BANK. The first rating change in the data is from %s, "
                "although prices start in %s. Each row of a bank's history should start from the level its previous row ended on. "
                "It does not in %s. Each such break means FMP missed a change in between, listed the same change twice or listed "
                "a grade wrongly. We cannot tell whether the missing changes had big or small moves. %d used changes are flagged "
                "for this, %d of them clean (kept in the results). CHECK: without them the answer to the main question is %s."
                % (next(number), events["date"].min().strftime("%B %Y"), prices["date"].min()[:4],
                   and_list("%.1f%% of %s's rows (%d of %s)" % (100 * rates[bank]["rows"] / rates[bank]["out_of"], bank, rates[bank]["rows"],
                                                                 "{:,}".format(rates[bank]["out_of"])) for bank in BANKS),
                   int(used["inconsistent"].sum()), int(clean["inconsistent"].sum()),
                   same_or_not(tests, version_named(MAIN_COLUMN, "clean_consistent"))), rest="   ")
    say()

    # ---- market adjustment
    apart = (used["car_day0"] - used["car_mm_day0"]).abs().idxmax()
    worst = used.loc[apart]
    say_wrapped("%d. ROUGH MARKET ADJUSTMENT. The move is 'stock minus S&P 500', which assumes every stock moves one-for-one "
                "with the market (beta = 1). That is wrong for calm stocks and for jumpy ones on big market days. The biggest "
                "disagreement is %s on %s (%s %s): on day 0 alone, %+.1f%% this way and %+.1f%% with the stock's own beta. The S&P 500 series also "
                "leaves out dividends while the stock prices include them, so every move against the market is a touch too high "
                "(well under 0.01%% a day). CHECK: with a market model (a beta for every stock) the answer to the main question is %s."
                % (next(number), worst["ticker"], worst["date"].date(), worst["bank"], worst["change"].lower(),
                   100 * worst["car_day0"], 100 * worst["car_mm_day0"],
                   same_or_not(tests, version_named(MAIN_COLUMN.replace("scar_", "scar_mm_"), MAIN_EVENTS))), rest="   ")
    say()

    # ---- not cause and effect
    runup_up = one(direction, events_included=MAIN_SAMPLE, bank="All banks", calls="Upgrades", window=RUNUP)["mean_move_pct"]
    runup_down = -one(direction, events_included=MAIN_SAMPLE, bank="All banks", calls="Downgrades", window=RUNUP)["mean_move_pct"]
    runup_usual = one(direction, events_included=MAIN_SAMPLE, bank="Ordinary days", calls="No rating change", window=RUNUP)["mean_move_pct"]
    drift = one(direction, events_included=MAIN_SAMPLE, bank="Ordinary days", calls="No rating change", window=DRIFT)["mean_move_pct"]
    say_wrapped("%d. NOT CAUSE AND EFFECT, AND A HINDSIGHT STOCK LIST. Banks often change a rating BECAUSE of news, and that news "
                "moves the price too (see the earnings caveat). So this report measures how much prices move on rating-change "
                "days, not what the rating itself caused. A bigger move on one bank's days can simply mean that bank changes "
                "ratings on bigger-news days. Had the price already moved before the change? Over the %d trading days "
                "before an upgrade the stock's move against the S&P 500 was %+.1f%%, and before a downgrade %+.1f%%, against "
                "%+.1f%% in an ordinary stretch of that length (not tested). The %d stocks are today's largest, "
                "picked with hindsight: on ordinary days they beat the S&P 500 by about %.1f%% over %d trading days, which "
                "flatters any 'drift' after upgrades. Results may not hold for smaller companies."
                % (next(number), RUNUP_DAYS, runup_up, runup_down, runup_usual, len(STOCKS), drift, DRIFT_DAYS), rest="   ")
    say()


# ---------------------------------------------------------------------------
# Part 2 of the report: the short version
# ---------------------------------------------------------------------------
def print_short_version(tables):
    sizes, tests, regression, direction = tables["1"], tables["2"], tables["3"], tables["4"]
    indent = "    "
    heading("THE SHORT VERSION  (clean rating changes, days -1..+1, unless it says otherwise)")

    # ---- Q1: is there a move at all?
    everyone = one(sizes, events_included=MAIN_SAMPLE, window=MAIN_WINDOW, bank="All banks", calls="All calls")
    signed = one(direction, events_included=MAIN_SAMPLE, bank="All banks", calls="All calls", window=MAIN_WINDOW)
    beats_ordinary = everyone["ci_low"] > everyone["ordinary_mean_size"]
    say("Q1. Do these stocks move more than usual around a rating change?   -> %s" % ("YES" if beats_ordinary else "NOT CLEARLY"))
    say_wrapped("The size of the move averaged %.2f over %d clean rating changes, against %.2f on ordinary days: %.1f times as "
                "big (95%% interval for the average: %.2f to %.2f). In percent, the middle (median) move against the S&P 500 "
                "was %.1f%%." % (everyone["mean_size"], everyone["events"], everyone["ordinary_mean_size"], everyone["times_ordinary"],
                                everyone["ci_low"], everyone["ci_high"], everyone["median_move_pct"]), indent, indent)
    say_wrapped("%.0f%% of the moves went the way the bank said (up after an upgrade, down after a downgrade). The average move "
                "in the bank's direction was %+.2f%% (significant by a plain t-test against zero: %s)."
                % (100 * signed["share_right"], signed["mean_move_pct"], verdict(signed["p_average"])), indent, indent)
    say()

    # ---- Q2: Goldman against the others (hypothesis 1)
    stories = {other: gap_story(tests, MAIN, other) for other in OTHERS}
    bigger = [other for other in OTHERS if stories[other][1] == "bigger"]
    smaller = [other for other in OTHERS if stories[other][1] == "smaller"]
    if len(bigger) == len(OTHERS):
        answer = "YES"
    elif bigger and smaller:
        answer = "BIGGER THAN %s'S, SMALLER THAN %s'S" % (" AND ".join(bigger).upper(), " AND ".join(smaller).upper())
    elif bigger:
        answer = "ONLY AGAINST " + " AND ".join(bigger).upper()
    elif smaller:
        answer = "NO. THEY ARE SMALLER THAN " + " AND ".join(smaller).upper() + "'S"
    else:
        answer = "NO. THE BANKS CANNOT BE TOLD APART"
    say("Q2. Are the moves bigger for %s than for %s?   -> %s" % (BASE_BANK, " or ".join(OTHERS), answer))
    rows = {bank: one(sizes, events_included=MAIN_SAMPLE, window=MAIN_WINDOW, bank=bank, calls="All calls") for bank in BANKS}
    by_average = ", then ".join(sorted(BANKS, key=lambda bank: rows[bank]["mean_size"], reverse=True))
    by_median = ", then ".join(sorted(BANKS, key=lambda bank: rows[bank]["median_size"], reverse=True))
    if by_average == by_median:
        order = "By the average and by the median (the middle move) the order is %s." % by_average
    else:
        order = ("By the average the order is %s. By the median (the middle move, which a few huge moves cannot swing) "
                 "it is %s. So the order on paper depends on how it is measured." % (by_average, by_median))
    say_wrapped("Average size of the move: %s. Ordinary days: %.2f. %s"
                % (list_banks(lambda bank: "%.2f (%d changes)" % (rows[bank]["mean_size"], rows[bank]["events"])),
                   everyone["ordinary_mean_size"], order), indent, indent)
    for other in OTHERS:
        row = stories[other][0]
        say_wrapped("%s against %s: %s's average is %s (95%% interval: from %s to %s). Unlikely to be luck? %s (p = %s)."
                    % (BASE_BANK, other, BASE_BANK, bigger_or_smaller(row["gap"]), bigger_or_smaller(row["gap_low"]),
                       bigger_or_smaller(row["gap_high"]), verdict(row["p_clustered"], MAIN_TESTS), show_p(row["p_clustered"])), indent, indent)
    main_regression = regression[regression["regression"] == regression["regression"].iloc[0]]
    if not bigger and not smaller:
        unlikely = []
        for other in OTHERS:
            high = stories[other][0]["gap_high"]                  # the top end of the 95% interval of the gap
            if high > 0:
                unlikely.append("more than %.2f bigger than %s's" % (high, other))
            else:
                unlikely.append("bigger than %s's at all (that whole interval is below zero, although the test is not significant)" % other)
        text = ("This is NOT proof that the banks are equal (see the caveat SMALL SAMPLE, MANY TESTS). What the two 95%% intervals "
                "above make unlikely: %s's average move being %s." % (BASE_BANK, " or ".join(unlikely)))
        if all(stories[other][0]["gap_high"] > 0 for other in OTHERS):
            # the regression of section C has its own 95% interval for the same two gaps (reading Goldman minus the other bank)
            limits = and_list("%.2f" % -one(main_regression, term=other + " vs " + BASE_BANK)["ci_low"] for other in OTHERS)
            text += " The regression in section C puts the same two limits at %s." % limits
        say_wrapped(text, indent, indent)
    agree, differ = robustness(tests)
    say_wrapped("Measured %d other ways, %d give the same answer%s." % (len(agree) + len(differ), len(agree),
                (" (" + "; ".join(agree) + ")") if agree else ""), indent, indent)
    for note in differ:
        say_wrapped("DIFFERENT ANSWER -> " + note, indent, indent + "  ")
    other_rows = [gap_story(tests, version, other)[0] for version, _, _ in VERSIONS[1:] for other in OTHERS]
    none_passes = not differ and not bigger and not smaller
    misses_zero = sum(row["gap_high"] < 0 or row["gap_low"] > 0 for row in other_rows)      # 95% intervals that do not hold zero
    text = ("Those %d other ways make %d comparisons (one per other bank). %s's average is the smaller one in %d of them%s. "
            "These are mostly the same rating changes measured again, not %d separate pieces of evidence."
            % (len(VERSIONS) - 1, len(other_rows), BASE_BANK, sum(row["gap"] < 0 for row in other_rows),
               ", but none passes the test" if none_passes else "", len(other_rows)))
    if none_passes and misses_zero:
        text += (" In %d of them the 95%% interval only just misses zero while the test does not pass (section B): "
                 "a borderline result, not a finding." % misses_zero)
    say_wrapped(text, indent, indent)
    say_wrapped("A regression that holds the year and upgrade-or-downgrade equal says: %s."
                % "; ".join("%s %+.2f, significant? %s" % (row["term"], row["coefficient"], verdict_cell(row["p_value"], MAIN_TESTS))
                            for _, row in main_regression.iterrows() if BASE_BANK in row["term"]), indent, indent)
    say()

    # ---- Q3: downgrades against upgrades (hypothesis 2)
    pooled = one(tests, version=MAIN, question="Downgrades vs upgrades, All banks")
    real = verdict(pooled["p_clustered"]) == "YES"
    answer = downgrade_answer(pooled)
    say("Q3. Are the moves bigger for downgrades than for upgrades?   -> %s" % answer)
    say_wrapped("All banks together: downgrades %.2f (%d changes), upgrades %.2f (%d). The downgrade average is %s "
                "(95%% interval: from %s to %s). Unlikely to be luck? %s (p = %s)."
                % (pooled["mean_a"], pooled["n_a"], pooled["mean_b"], pooled["n_b"], bigger_or_smaller(pooled["gap"]),
                   bigger_or_smaller(pooled["gap_low"]), bigger_or_smaller(pooled["gap_high"]),
                   verdict(pooled["p_clustered"]), show_p(pooled["p_clustered"])), indent, indent)
    by_bank = {bank: one(tests, version=MAIN, question="Downgrades vs upgrades, " + bank) for bank in BANKS}
    say_wrapped("Bank by bank the groups are small (%s downgrades), so read these as description, not as tests: "
                "the downgrade average is %s."
                % (list_banks(lambda bank: str(int(by_bank[bank]["n_a"]))),
                   list_banks(lambda bank: "%s (p = %s)" % (bigger_or_smaller(by_bank[bank]["gap"]), show_p(by_bank[bank]["p_clustered"])))), indent, indent)
    same = 0                                  # how many of the other versions answer Q3 the same way?
    for version, _, _ in VERSIONS[1:]:
        same += downgrade_answer(one(tests, version=version, question="Downgrades vs upgrades, All banks")) == answer
    say_wrapped("Measured %d other ways, %d give the same answer." % (len(VERSIONS) - 1, same), indent, indent)
    hints = regression[(regression["term"] == "Downgrade vs upgrade") & (regression["p_value"] < SIGNIFICANCE)]
    if not real:
        for _, row in hints.iterrows():
            say_wrapped("One regression in section C does show a difference (%s): there the downgrade moves are %s, p = %s. "
                        "It is one of several secondary checks, so treat it as a hint, not a finding."
                        % (row["regression"], bigger_or_smaller(row["coefficient"]), show_p(row["p_value"])), indent, indent)
    say()

    # ---- Q4: when does the stock move?
    day = {label: one(direction, events_included=MAIN_SAMPLE, bank="All banks", calls="All calls", window=label)
           for label in ["day -1", "day 0", "day +1", "day 0, overnight part (stock only)", "day 0, intraday part (stock only)"]}
    overnight, intraday = day["day 0, overnight part (stock only)"], day["day 0, intraday part (stock only)"]
    day0 = day["day 0"]
    clear_move = day0["mean_move_pct"] > 0 and verdict(day0["p_average"]) == "YES"     # is there a day-0 move in the bank's direction at all?
    on_day0 = clear_move and day0["mean_move_pct"] > 2 * max(day["day -1"]["mean_move_pct"], day["day +1"]["mean_move_pct"])
    if not clear_move:
        answer = "NO CLEAR MOVE IN THE BANK'S DIRECTION ON DAY 0"
    elif on_day0:
        answer = "ON THE DAY OF THE RATING CHANGE"
    else:
        answer = "SPREAD OVER SEVERAL DAYS"
    if on_day0 and overnight["mean_move_pct"] > intraday["mean_move_pct"]:
        answer += ", MOSTLY BEFORE THE MARKET OPENS"
    say("Q4. When does the stock move?   -> %s" % answer)
    say_wrapped("Average move in the bank's direction: %+.2f%% the day before, %+.2f%% on day 0, %+.2f%% the day after. "
                "%.0f%% of the day-0 moves went the bank's way, against %.0f%% and %.0f%% on the days around it (a coin flip is 50%%)."
                % (day["day -1"]["mean_move_pct"], day["day 0"]["mean_move_pct"], day["day +1"]["mean_move_pct"],
                   100 * day["day 0"]["share_right"], 100 * day["day -1"]["share_right"], 100 * day["day +1"]["share_right"]), indent, indent)
    say_wrapped("Inside day 0, the stock's own move in the bank's direction was %+.2f%% from the previous close to the open and "
                "%+.2f%% from the open to the close. (These two are NOT measured against the S&P 500: the index's opening value "
                "in the data is not reliable, and in 2012 and 2013 it is simply the previous close on about 1 day in 4.) "
                "Most ratings come out before the market opens, and so does overnight company news."
                % (overnight["mean_move_pct"], intraday["mean_move_pct"]), indent, indent)
    say()

    # ---- Q5: before and after
    say("Q5. Had the stock moved BEFORE the change, and did it keep moving AFTER?   -> DESCRIPTION ONLY, NOT TESTED")
    stretches = [(RUNUP, "Over the %d trading days BEFORE (days %+d..%+d)" % (RUNUP_DAYS, WINDOWS["runup"][0], WINDOWS["runup"][1])),
                 (DRIFT, "Over the %d trading days AFTER (days %+d..%+d)" % (DRIFT_DAYS, WINDOWS["drift"][0], WINDOWS["drift"][1]))]
    for label, words in stretches:
        up = one(direction, events_included=MAIN_SAMPLE, bank="All banks", calls="Upgrades", window=label)["mean_move_pct"]
        down = -one(direction, events_included=MAIN_SAMPLE, bank="All banks", calls="Downgrades", window=label)["mean_move_pct"]
        usual = one(direction, events_included=MAIN_SAMPLE, bank="Ordinary days", calls="No rating change", window=label)["mean_move_pct"]
        say_wrapped("%s the stock's move against the S&P 500 averaged %+.1f%% around upgrades and %+.1f%% around downgrades. "
                    "On ordinary days the same stocks did %+.1f%% over a stretch of that length, so compare with that, not with zero."
                    % (words, up, down, usual), indent, indent)
    say_wrapped("An ordinary day is more than %d trading days away from every rating change by the three banks, so these "
                "longer ordinary stretches can still have a rating change inside them." % QUIET_DAYS, indent, indent)
    say()


# ---------------------------------------------------------------------------
# Part 3 of the report: the details
# ---------------------------------------------------------------------------
def print_sizes(sizes, sample, window):
    say("  %-15s %-11s %7s  %8s  %-14s %7s  %9s  %8s  %9s" % ("", "", "", "Average", "95% interval", "Median", "Ordinary", "Times", "Median"))
    say("  %-15s %-11s %7s  %8s  %-14s %7s  %9s  %8s  %9s" % ("Bank", "Calls", "Changes", "size", "of the average", "size", "days", "ordinary", "move in %"))
    for bank in ["All banks"] + list(BANKS):
        for calls in ["All calls", "Upgrades", "Downgrades"]:
            row = one(sizes, events_included=sample, window=window, bank=bank, calls=calls)
            say("  %-15s %-11s %7d  %8.2f  %-14s %7.2f  %9.2f  %8.1f  %8.1f%%" % (
                bank.upper() if bank == "All banks" else bank, calls, row["events"], row["mean_size"],
                "%.2f to %.2f" % (row["ci_low"], row["ci_high"]), row["median_size"], row["ordinary_mean_size"],
                row["times_ordinary"], row["median_move_pct"]))
        say()


def print_details(tables, events):
    sizes, tests, regression, direction, profile = tables["1"], tables["2"], tables["3"], tables["4"], tables["5"]
    heading("THE DETAILS")
    say("How to read the tables")
    guide = [
        ("Size", "The stock's move against the S&P 500 over the window, divided by that stock's usual swing (one standard "
                 "deviation), sign dropped. 1.0 = one usual swing, 2.0 = twice that. Most ordinary moves are below 1.0. "
                 "The one-day version of this swing is called the stock's typical day."),
        ("Ordinary days", "The same measurement on random days of the same stocks in the same years, with no rating change by "
                          "these three banks nearby. This is what 'nothing happened' looks like."),
        ("95% interval", "Where the average would probably land if history were re-run. It is found by re-drawing whole stocks at "
                         "random (in section C it comes from the regression instead). An interval that only just misses zero can "
                         "sit next to 'weak' or 'no': the interval and the 'significant?' verdict are worked out in different ways, "
                         "and the %s comparisons use a stricter bar than 95%%. Read that as borderline, and go by the verdict." % BASE_BANK),
        ("significant?", "Could the number be luck? YES = unlikely (p under %.2f). weak = borderline (under %.2f). no = could easily be "
                         "luck. The p-value in brackets is the chance of a result this big if there were really no difference. "
                         "For every comparison of %s with one other bank the bars are halved (%.3f and %.3f), because "
                         "the two comparisons share one question."
                         % (SIGNIFICANCE, WEAK, BASE_BANK, SIGNIFICANCE / MAIN_TESTS, WEAK / MAIN_TESTS)),
    ]
    for term, text in guide:
        say_wrapped(text, first="  %-15s" % term, rest=" " * 17)
    say()

    say("A. HOW BIG IS THE MOVE?  Clean rating changes, days -1..+1: the main result  (table_1_bank_comparison.csv)")
    print_sizes(sizes, MAIN_SAMPLE, MAIN_WINDOW)
    say("   The same average size, measured three other ways (all calls):")
    for sample, window in [(MAIN_SAMPLE, "day 0"), (ALL_SAMPLE, MAIN_WINDOW), (ALL_SAMPLE, "day 0")]:
        rows = {bank: one(sizes, events_included=sample, window=window, bank=bank, calls="All calls") for bank in BANKS}
        say("     %-30s %s   (ordinary days %.2f)" % (sample + ", " + window + ":", list_banks(lambda bank: "%.2f" % rows[bank]["mean_size"]),
                                                      one(sizes, events_included=sample, window=window, bank="All banks", calls="All calls")["ordinary_mean_size"]))
    say()

    say("B. IS THE GAP BETWEEN BANKS REAL?  (table_2_bank_tests.csv)")
    say("   Gap = %s's average size minus the other bank's. Negative = %s's moves are smaller." % (BASE_BANK, BASE_BANK))
    say("   'significant?' treats each stock as one block of evidence, with the halved bars (YES needs p under %.3f)." % (SIGNIFICANCE / MAIN_TESTS))
    say("   The last two columns are the p-values of the usual textbook tests (t-test on averages, Mann-Whitney on")
    say("   ranks), which treat every change as independent. The 95% interval (re-drawn stocks) and 'significant?'")
    say("   (stocks as blocks) are two methods: near the bar they can disagree, and then the row is borderline.")
    say("  %-49s %-10s %6s  %-16s %-14s %7s %7s" % ("How it is measured", "Against", "Gap", "95% interval", "significant?", "t-test", "ranks"))
    for version, _, _ in VERSIONS:
        for other in OTHERS:
            row = one(tests, version=version, question=BASE_BANK + " vs " + other)
            say("  %-49s %-10s %+6.2f  %-16s %-14s %7s %7s" % (
                version[:49], BANKS[other].upper(), row["gap"], "%+.2f to %+.2f" % (row["gap_low"], row["gap_high"]),
                verdict_cell(row["p_clustered"], MAIN_TESTS), show_p(row["p_averages"]), show_p(row["p_ranks"])))
    say("   (%s. The last two lines are in percent, not in sizes: they show" % ", ".join("%s = %s" % (BANKS[other].upper(), other) for other in OTHERS))
    say("   what happens WITHOUT dividing by each stock's usual swing, so a bank that rates jumpy stocks looks bigger.)")
    say()
    say("   Downgrades against upgrades (gap = downgrade average minus upgrade average; main version).")
    say("   Only the all-banks line is a test, with the usual bars (YES needs p under %.2f)." % SIGNIFICANCE)
    say("   The bank lines are small groups: description only.")
    for bank in ["All banks"] + list(BANKS):
        row = one(tests, version=MAIN, question="Downgrades vs upgrades, " + bank)
        tested = "significant? " + verdict_cell(row["p_clustered"]) if bank == "All banks" else "description only (p = %s)" % show_p(row["p_clustered"])
        say("     %-15s downgrades %.2f (%d)   upgrades %.2f (%d)   gap %+.2f   %s" % (
            bank, row["mean_a"], row["n_a"], row["mean_b"], row["n_b"], row["gap"], tested))
    say()

    say("C. THE SAME COMPARISON AS A REGRESSION  (table_3_regression.csv)")
    say("   Each number says how much bigger (+) or smaller (-) the size is, holding the other things and the year equal.")
    say("   A bank against %s is judged with the halved bars, the other lines with the usual ones." % BASE_BANK)
    for name in regression["regression"].unique():
        rows = regression[regression["regression"] == name]
        say("   %s  (%d changes on %d stocks)" % (name, rows["events"].iloc[0], rows["stocks"].iloc[0]))
        for _, row in rows.iterrows():
            say("     %-33s %+6.2f   95%% interval %+.2f to %+.2f   significant? %s" % (
                row["term"], row["coefficient"], row["ci_low"], row["ci_high"],
                verdict_cell(row["p_value"], MAIN_TESTS if BASE_BANK in row["term"] else 1)))       # a bank against Goldman: halved bars
    say()

    say("D. DID THE STOCK MOVE THE WAY THE BANK SAID?  Clean rating changes, all banks  (table_4_direction.csv)")
    say("   Average move in the bank's direction, in %: + means up after an upgrade or down after a downgrade.")
    say("  %-36s %10s %12s %10s   %-18s %-14s" % ("Window", "Upgrades", "Downgrades", "All calls", "Share moved right", "significant?"))
    for label in direction["window"].unique():
        row = {calls: one(direction, events_included=MAIN_SAMPLE, bank="All banks", calls=calls, window=label) for calls in ["Upgrades", "Downgrades", "All calls"]}
        say("  %-36s %+9.2f%% %+11.2f%% %+9.2f%%   %-18s %-14s" % (
            label, row["Upgrades"]["mean_move_pct"], row["Downgrades"]["mean_move_pct"], row["All calls"]["mean_move_pct"],
            "%.0f%%" % (100 * row["All calls"]["share_right"]), verdict_cell(row["All calls"]["p_average"])))
    say("   ('significant?' asks whether the all-calls average differs from zero. It is a plain t-test that counts")
    say("   every change as independent, unlike sections B and C. For the run-up and the drift, zero is the wrong")
    say("   yardstick: see the caveat NOT CAUSE AND EFFECT and the short version, Q5.)")
    say()
    say("   By bank, days -1..+1 (clean rating changes):")
    for bank in BANKS:
        row = one(direction, events_included=MAIN_SAMPLE, bank=bank, calls="All calls", window=MAIN_WINDOW)
        say("     %-15s %+5.2f%% in the bank's direction, %.0f%% moved the right way (%d changes)" % (
            bank, row["mean_move_pct"], 100 * row["share_right"], row["events"]))
    say()

    say("E. WHAT EACH BANK'S RATING CHANGES LOOK LIKE  (all used changes; table_5_bank_profile.csv)")
    say("   A gap between banks can come from WHAT and WHEN they rate. These are the things that differ.")
    say("  %-15s %5s %6s %7s  %-22s %6s %9s %9s %8s %7s" % ("Bank", "Used", "Clean", "Stocks", "3 busiest stocks", "Down-", "Near", "Over-", "Typical", "Median"))
    say("  %-15s %5s %6s %7s  %-22s %6s %9s %9s %8s %7s" % ("", "", "", "", "(share of changes)", "grades", "earnings", "lapping", "day", "year"))
    for _, row in profile.iterrows():
        say("  %-15s %5d %6d %7d  %-22s %5.0f%% %8.0f%% %8.0f%% %7.2f%% %7d" % (
            row["bank"], row["used_events"], row["clean_events"], row["stocks"],
            "%s (%.0f%%)" % (row["busiest_stocks"], 100 * row["share_in_3_busiest_stocks"]), 100 * row["share_downgrades"],
            100 * row["share_near_earnings"], 100 * row["share_overlapping"], row["median_typical_day_pct"], row["median_year"]))
    say("   (Typical day = the stock's usual daily swing against the S&P 500: one standard deviation of its daily moves over")
    say("   the %d trading days before the change. The table shows the median over the bank's changes.)" % (ESTIMATION[1] - ESTIMATION[0] + 1))
    say()

    say("F. THE 10 BIGGEST MOVES among all used rating changes (days -1..+1)")
    say("  %-6s %-11s %-15s %-10s %9s %6s   %s" % ("Stock", "Date", "Bank", "Call", "Move", "Size", "Clean?"))
    used = events[events["status"] == "used"]
    for _, row in used.assign(size=used["scar_3day"].abs()).nlargest(10, "size").iterrows():
        doubts = [text for flag, text in [("near_earnings", "near earnings"), ("overlap", "overlaps another change")] if row[flag]]
        if not row["earnings_known"]:
            doubts.append("earnings dates unknown")
        if doubts:
            is_clean = "no: " + ", ".join(doubts)
        else:
            is_clean = "yes (another broker within %s)" % NEARBY if row["other_broker"] else "yes"
        say("  %-6s %-11s %-15s %-10s %+8.1f%% %6.1f   %s" % (row["ticker"], row["date"].date(), row["bank"], row["change"],
                                                            100 * row["car_3day"], row["size"], is_clean))
    say()


# ---------------------------------------------------------------------------
# Part 4 of the report: the paper trail
# ---------------------------------------------------------------------------
def print_paper_trail(log):
    heading("THE PAPER TRAIL: every place where data was left out, changed or flagged  (logs/data_changes.csv)")
    say("REMOVED = left out.  CHANGED = a value was altered.  FLAGGED = kept, but marked as doubtful.")
    for step in sorted(log["step"].unique()):                    # step 1 first, even if a single step was re-run later
        say()
        say("Step " + step)
        for _, row in log[log["step"] == step].iterrows():
            say("  %-8s %7s of %-8s %s" % (row["action"], "{:,}".format(row["rows"]), "{:,}".format(row["out_of"]), row["what"]))
            say_wrapped("why: " + row["why"], first=" " * 30, rest=" " * 35)
    say()


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------
def main():
    if len(BANKS) != 3:
        sys.exit("make_report.py is written for exactly three banks (its wording, its colours and its two main "
                 "comparisons). BANKS in build_dataset.py has %d." % len(BANKS))
    tables, events, days, prices, log = load()
    figure_event_study(events, days)
    figure_bank_comparison(tables["1"])

    used = events[events["status"] == "used"]
    heading("ARE PRICE MOVES BIGGER WHEN %s CHANGES A RATING THAN WHEN %s DOES?" % (BASE_BANK.upper(), " OR ".join(OTHERS).upper()))
    say_wrapped("Upgrades and downgrades of %d large US stocks by %s, %s to %s. Built from Financial Modeling Prep (FMP) "
                "data that ends %s. The numbers change only when the data is downloaded again (python run_all.py --fresh)."
                % (used["ticker"].nunique(), and_list(BANKS), used["date"].min().strftime("%B %Y"), used["date"].max().strftime("%B %Y"),
                   prices["date"].max()))
    say()
    everyone = one(tables["1"], events_included=MAIN_SAMPLE, window=MAIN_WINDOW, bank="All banks", calls="All calls")
    say("HOW A MOVE IS MEASURED")
    words = [
        ("Move", "The stock's return minus the S&P 500's return, added up over the day before the rating change, the day itself "
                 "and the day after (days -1..+1)."),
        ("Size", "The move divided by that stock's usual 3-day swing (one standard deviation of its moves over the %d trading "
                 "days before), with the sign dropped. 1.0 = one usual swing, 2.0 = twice that. Most ordinary moves are smaller "
                 "than 1.0. This puts calm stocks and jumpy stocks on one scale. The one-day version of this swing is called "
                 "the stock's typical day." % (ESTIMATION[1] - ESTIMATION[0] + 1)),
        ("Ordinary days", "A size is never 0, even when nothing happens. On ordinary days (same stocks, same years, no rating "
                          "change by these three banks nearby) it averages %.2f. A rating change only matters if it beats that."
                          % everyone["ordinary_mean_size"]),
        ("Clean", "A rating change that is not next to an earnings announcement and has no other rating change by these three "
                  "banks next to it. The main results use the %d clean changes. Results with all %d used changes are shown "
                  "beside them." % (int(used["clean"].sum()), len(used))),
    ]
    for term, text in words:
        say_wrapped(text, first="  %-15s" % term, rest=" " * 17)
    say()

    print_caveats(tables, events, prices, log)
    print_short_version(tables)
    print_details(tables, events)
    print_paper_trail(log)
    say("FILES: outputs/report.txt (this report), outputs/table_1 ... table_5 (.csv), outputs/figure_1_event_study.png,")
    say("outputs/figure_2_bank_comparison.png. One row per rating change, to check any single event: data/clean/events.csv")

    (OUTPUTS / "report.txt").write_text("\n".join(REPORT) + "\n", encoding="utf-8")
    print("\nSaved outputs/report.txt, outputs/figure_1_event_study.png and outputs/figure_2_bank_comparison.png")
    missing = missing_stocks(prices)
    if missing:                               # the last thing on the screen, so it cannot scroll past unseen
        print("\nWARNING: %d of the %d stocks are missing because their download failed (%s). The results above are "
              "incomplete. Run  python run_all.py  again." % (len(missing), len(STOCKS), ", ".join(missing)))


if __name__ == "__main__":
    main()
