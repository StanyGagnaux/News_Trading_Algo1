"""
run_rung.py -- push one cost-ladder rung's score files through the UNCHANGED
frozen pipeline (ladder note of 24 Oct 2026, item d): the event study
(training and test), risk calibration on training only (calibrate_risk.py),
and strategies A/B/C vs momentum (run_both_strategies.py, designed governor,
N = 155 trials).

The frozen scripts write fixed names (risk_calibration_llm.csv,
results_both_strategies_llm_calibrated*). The official 18 Oct files with those
names are backed up first, the rung's outputs renamed to *_<rung>*, and the
originals restored and verified by SHA-256.

USAGE (from the project root):
  python3 src/run_rung.py --rung embed_minilm \
      --train-file data_sources/news_scored_embed_minilm.csv \
      --full-file data_sources/news_scored_embed_minilm_incl_test.csv
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from paths import OUTPUTS, ROOT
from newsdrift import Config, PrecomputedScorer
import event_study as es
from calibrate_scorer import load_training, TRAIN_END, DATA_START

N_TRIALS = 155
STAMP = "2026-10-24"
LOG = OUTPUTS / "logs"
CAL = OUTPUTS / "risk_calibration_llm.csv"
RUNNER_OUT = [OUTPUTS / f"results_both_strategies_llm_calibrated{s}" for s in
              (".csv", "_comparison.csv", "_dsr_sensitivity.csv")] + \
             [OUTPUTS / "equity_both_strategies_llm_calibrated.png"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Protected:
    """Back up official files, then restore and verify them on exit."""
    def __init__(self, files):
        self.files = [f for f in files if f.exists()]
        self.saved = {f: (f.with_suffix(f.suffix + ".official_bak"), sha(f)) for f in self.files}

    def __enter__(self):
        for f, (bak, _) in self.saved.items():
            shutil.copy2(f, bak)
        return self

    def __exit__(self, *exc):
        for f, (bak, h) in self.saved.items():
            shutil.move(bak, f)
            assert sha(f) == h, f"official file NOT restored: {f}"
        print(f"  restored and verified {len(self.saved)} official file(s)")


def log_test(rung: str, what: str, output: str) -> None:
    pd.DataFrame([{"timestamp": datetime.now().isoformat(timespec="seconds"),
                   "script": f"src/run_rung.py --rung {rung}", "scorers": rung,
                   "period": "2024-04-30 .. 2026-06-01", "what": what, "output": output}]).to_csv(
        OUTPUTS / "test_period_runs.csv", mode="a", index=False, header=False)


def event_studies(rung: str, train_file: str, full_file: str) -> None:
    px, nw, cfg = load_training()
    es.event_study(px, nw, cfg, [(rung, PrecomputedScorer(train_file), None)],
                   es.load_ndx(DATA_START, TRAIN_END), DATA_START,
                   f"event_study_train_{rung}_{STAMP}", f"training, rung {rung}")
    px, nw, first = es.load_test()
    out = es.event_study(px, nw, Config(), [(rung, PrecomputedScorer(full_file), None)],
                         es.load_ndx(TRAIN_END - es.PRE_TEST_PRICE_DAYS, es.DATA_END), first,
                         f"event_study_test_{rung}_{STAMP}", f"TEST, rung {rung}")
    log_test(rung, "frozen event study (ladder)", out.name)


def run(cmd: list, log: Path) -> None:
    print("  $ " + " ".join(cmd))
    with log.open("w") as f:
        rc = subprocess.run([sys.executable, *cmd], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    assert rc == 0, f"failed ({rc}); see {log}"


def strategies(rung: str, train_file: str, full_file: str) -> None:
    cal_out = OUTPUTS / f"risk_calibration_{rung}.csv"
    with Protected([CAL]):
        run(["src/calibrate_risk.py", "--llm-scores", train_file], LOG / f"calibrate_risk_{rung}_{STAMP}.log")
        shutil.move(CAL, cal_out)
    with Protected(RUNNER_OUT):
        run(["src/run_both_strategies.py", "--llm-scores", full_file, "--risk-scales", str(cal_out),
             "--dd-governor", "designed", "--n-trials", str(N_TRIALS)],
            LOG / f"test_run_strategies_{rung}_{STAMP}.log")
        for f in RUNNER_OUT:
            if f.exists():
                shutil.move(f, f.with_name(f.name.replace("_llm_calibrated", f"_{rung}_calibrated")))
    log_test(rung, f"strategies A/B/C vs momentum, N = {N_TRIALS}, risk scales from training",
             f"results_both_strategies_{rung}_calibrated.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rung", required=True)
    ap.add_argument("--train-file", required=True)
    ap.add_argument("--full-file", required=True)
    a = ap.parse_args()
    event_studies(a.rung, a.train_file, a.full_file)
    strategies(a.rung, a.train_file, a.full_file)


if __name__ == "__main__":
    main()
