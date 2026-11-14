"""Rebuild everything with one command.

    python run_all.py            rebuild the dataset, the event list, the tables, the figures and the report
    python run_all.py --fresh    the same, but first delete the saved downloads and download everything again

THE PIPELINE (each step is its own script; this file only runs them in order)

    FMP, the data provider
      |
      |  step 1  build_dataset.py     download prices, ratings and earnings dates, and merge them
      v
    data/raw/                         the downloads, saved as tables (nothing changed)
    data/clean/dataset.csv            THE DATASET: one row per stock per trading day
      |
      |  step 2  build_events.py      list the rating changes and measure the stock's move around each one
      v
    data/clean/events.csv             one row per rating change
      |
      |  step 3  analyze_events.py    compare the three banks
      v
    outputs/table_1 ... table_5.csv   the numbers
      |
      |  step 4  make_report.py       draw the figures and write the report in plain words
      v
    outputs/report.txt                READ THIS FIRST
    outputs/figure_1 ... figure_2.png

WHAT "FROM SCRATCH" MEANS HERE
  Every run deletes the .csv, .png and .txt files in data/clean/, outputs/ and logs/, and builds them again.
  Do not keep hand-made files there.
  The downloads in data/raw/ are re-used if they exist, so a second run does not call FMP again and gives the
  same numbers. On a new computer data/raw/ is empty, so the first run downloads everything.
  --fresh deletes data/raw/ too. That costs 76 requests (FMP's free plan allows 250 a day), and the
  numbers can change because FMP adds new days and sometimes revises its ratings history.
"""
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The steps, in order. Each one is a script you can also run on its own.
STEPS = [
    ("build_dataset.py", "Download the data and build data/clean/dataset.csv"),
    ("build_events.py", "List the rating changes and measure the stock's move around each one"),
    ("analyze_events.py", "Compare the banks and save the tables in outputs/"),
    ("make_report.py", "Draw the figures and write the report in outputs/"),
]

# What the pipeline makes: (folder, file ending). These files are deleted at the start of every run.
GENERATED = [
    (HERE / "data" / "clean", ".csv"),
    (HERE / "outputs", ".csv"),
    (HERE / "outputs", ".png"),
    (HERE / "outputs", ".txt"),
    (HERE / "logs", ".csv"),
]
DOWNLOADS = HERE / "data" / "raw"          # only deleted with --fresh
PACKAGES = ["pandas", "numpy", "requests", "dotenv", "scipy", "statsmodels", "matplotlib"]
WIDTH = 100                                 # characters per line of the banners


def say(text=""):
    """Print straight away (so our lines and the steps' lines appear in the right order)."""
    print(text, flush=True)


def check_packages():
    """Stop with a helpful message if a package from requirements.txt is not installed."""
    missing = [name for name in PACKAGES if importlib.util.find_spec(name) is None]
    if missing:
        sys.exit("Missing Python packages: %s\nInstall them with:   pip install -r requirements.txt" % ", ".join(missing))


def have_key():
    """Is there an FMP key (in the .env file next to this script, or in the environment)?"""
    from dotenv import dotenv_values                      # imported here so check_packages() can complain first
    key = os.environ.get("FMP_API_KEY") or dotenv_values(HERE / ".env").get("FMP_API_KEY")
    return bool(key and key.strip())


def delete_files(folder, ending, subfolders=False):
    """Delete the files in `folder` whose names end with `ending`. Returns how many were deleted."""
    if not folder.exists():
        return 0
    files = list(folder.rglob("*" + ending)) if subfolders else list(folder.glob("*" + ending))
    for file in files:
        try:
            file.unlink()
        except PermissionError:                                   # on Windows, a file that is open in Excel cannot be deleted
            sys.exit("Cannot delete %s. Close it (is it open in Excel?) and run  python run_all.py  again." % file)
    return len(files)


def clean_up(fresh):
    """Delete what earlier runs made, so that everything we end up with comes from THIS run."""
    saved = len(list(DOWNLOADS.rglob("*.csv"))) if DOWNLOADS.exists() else 0
    if fresh and not have_key():
        sys.exit("--fresh downloads everything again, and that needs your FMP key in a file called .env. "
                 "No key was found, so nothing was deleted (%d saved downloads are still in data/raw/)." % saved)
    if saved == 0 and not have_key():
        sys.exit("There are no saved downloads in data/raw/ and no FMP key in a file called .env, so nothing can be built. "
                 "Nothing was deleted. See 'Set up' in README.md.")
    from build_dataset import STOCKS                           # imported here so check_packages() can complain first
    needed = 3 * len(STOCKS) + 1                               # prices, ratings and earnings for every stock, plus the S&P 500
    if saved < needed and not have_key():
        sys.exit("Only %d of the %d downloads are saved in data/raw/ and there is no FMP key in a file called .env, "
                 "so the rest cannot be downloaded. Nothing was deleted. See 'Set up' in README.md." % (saved, needed))

    deleted = sum(delete_files(folder, ending) for folder, ending in GENERATED)
    say("Deleted %d files from earlier runs (data/clean/, outputs/, logs/)." % deleted)
    if fresh:
        delete_files(DOWNLOADS, ".csv", subfolders=True)
        say("--fresh: deleted %d saved downloads from data/raw/. Everything will be downloaded again." % saved)
    elif saved > 0:
        say("Re-using %d saved downloads in data/raw/ (run with --fresh to download again)." % saved)
    else:
        say("No saved downloads in data/raw/, so step 1 will download everything.")


def run_step(number, script, purpose):
    """Run one script. Stop the whole pipeline if it fails, so a later step never uses stale files."""
    say()
    say("#" * WIDTH)
    say("#  STEP %d of %d: %s   (%s)" % (number, len(STEPS), purpose, script))
    say("#" * WIDTH)
    started = time.time()
    result = subprocess.run([sys.executable, str(HERE / script)], cwd=HERE)
    if result.returncode != 0:
        sys.exit("\nSTOPPED: %s failed (its message is above). The steps after it were not run." % script)
    say("(step %d took %.0f seconds)" % (number, time.time() - started))


def main():
    unknown = [word for word in sys.argv[1:] if word != "--fresh"]
    if unknown:
        sys.exit("Unknown option: %s\nUse:   python run_all.py   or   python run_all.py --fresh" % " ".join(unknown))
    fresh = "--fresh" in sys.argv[1:]

    check_packages()
    started = time.time()
    clean_up(fresh)
    for number, (script, purpose) in enumerate(STEPS, start=1):
        run_step(number, script, purpose)

    say()
    say("=" * WIDTH)
    say("DONE in %.0f seconds. Read outputs/report.txt first. Files in outputs/:" % (time.time() - started))
    made = [file for folder, ending in GENERATED if folder.name == "outputs" for file in folder.glob("*" + ending)]
    for file in sorted(made):                                     # only the kinds of file this pipeline makes
        say("  outputs/" + file.name)
    say("=" * WIDTH)


if __name__ == "__main__":
    main()
