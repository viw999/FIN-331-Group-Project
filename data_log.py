"""A paper trail for the data.

Every time a step of the pipeline REMOVES rows, CHANGES values or FLAGS rows as doubtful, it calls
log_change(). Each call prints one line and adds one line to logs/data_changes.csv. The final report
prints the whole file, so nothing disappears without being counted.

You do not run this file. The other scripts import it.
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
LOG_FILE = HERE / "logs" / "data_changes.csv"
COLUMNS = ["step", "action", "rows", "out_of", "what", "why"]


def read_log():
    """The log as a table (empty if no step has run yet)."""
    if LOG_FILE.exists():
        return pd.read_csv(LOG_FILE)
    return pd.DataFrame(columns=COLUMNS)


def start_step(step):
    """Throw away this step's old lines, so running a step twice does not count things twice."""
    log = read_log()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log[log["step"] != step].to_csv(LOG_FILE, index=False)


def log_change(step, action, rows, out_of, what, why):
    """Add one line to the paper trail.

    step     which script is speaking, e.g. "1 build_dataset"
    action   REMOVED (rows left out), CHANGED (values altered) or FLAGGED (kept, but marked as doubtful)
    rows     how many rows this happened to
    out_of   out of how many
    what     what the rows are, in plain words
    why      the reason
    """
    line = pd.DataFrame([[step, action, int(rows), int(out_of), what, why]], columns=COLUMNS)
    log = pd.concat([read_log(), line], ignore_index=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(LOG_FILE, index=False)
    print("  [%s] %s of %s: %s" % (action, "{:,}".format(int(rows)), "{:,}".format(int(out_of)), what))
