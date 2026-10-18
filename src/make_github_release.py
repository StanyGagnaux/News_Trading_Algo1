"""
make_github_release.py -- build github_release/: the folder to upload to GitHub
for the supervisor. ALLOW-LIST only: code, tests, procedures, documentation,
frozen configuration and AGGREGATED results. Never keys, news, prices, holdout
data, minute bars, LLM score files, caches or the archive.

Safety checks (the build fails if any is violated):
  * no value from .env or ALPACA_KEY.py appears in any copied file (values are
    read for the check only, never printed or copied);
  * no copied CSV has raw-data columns (headline, bid, ask, mktcap, vwap);
  * no file larger than 10 MB.

USAGE (from the project root):
  python3 src/make_github_release.py --dry-run   # list what would be copied
  python3 src/make_github_release.py             # (re)build github_release/
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from paths import ROOT

OUT = ROOT / "github_release"
MARKER = ".built_by_make_github_release"
MAX_BYTES = 10 * 1024 * 1024
RAW_COLUMNS = {"headline", "bid", "ask", "mktcap", "vwap"}
SECRET_FILES = [ROOT / ".env", ROOT / "ALPACA_KEY.py"]

# (source glob relative to ROOT, destination folder relative to OUT)
ALLOW = [
    ("src/*.py", "src"), ("src/*.sh", "src"), ("src/newsdrift/*.py", "src/newsdrift"),
    ("tests/*.py", "tests"),
    ("skills/*.md", "skills"),
    ("context/thesis.md", "context"), ("context/methodology.md", "context"),
    ("context/systems.md", "context"), ("context/results.md", "context"),
    ("context/bugs.md", "context"), ("context/changelog.md", "context"),
    ("CLAUDE.md", "."),
    ("data_sources/nasdaq100.txt", "data_sources"),          # public ticker list
    ("data_sources/company_names.csv", "data_sources"),      # public names, for anonymisation
    ("outputs/FROZEN_CONFIG_*.md", "results/frozen"), ("outputs/FROZEN_CONFIG_hashes*.txt", "results/frozen"),
    ("outputs/results_both_strategies_*_calibrated.csv", "results/strategies_test"),
    ("outputs/results_both_strategies_*_calibrated_comparison.csv", "results/strategies_test"),
    ("outputs/results_both_strategies_*_calibrated_dsr_sensitivity.csv", "results/strategies_test"),
    ("outputs/equity_both_strategies_*_calibrated.png", "results/strategies_test"),
    ("outputs/logs/test_run_strategies_*.log", "results/strategies_test"),
    ("outputs/h2b_kelly_vs_fixed_holm_*.csv", "results/strategies_test"),
    ("outputs/order_robustness_*.csv", "results"), ("outputs/logs/order_robustness_*.log", "results"),
    ("outputs/h3_power_*.csv", "results/holdout_unused"),
    ("outputs/holdout_power_*.csv", "results/holdout_unused"),
    ("outputs/test_period_runs.csv", "results"), ("outputs/holdout_runs.csv", "results/holdout_unused"),
    ("outputs/experiments_log.csv", "results"),
    ("outputs/event_study_train_*bug11fix.*", "results/event_study"),
    ("outputs/event_study_test_*.csv", "results/event_study"),
    ("outputs/event_study_test_*.png", "results/event_study"),
    ("outputs/intraday_description_*.csv", "results"),
    ("outputs/source_consistency_*.csv", "results"),
    ("outputs/frozen_risk_scales_2026-10-13_*", "results/risk_scales"),
    ("outputs/sweep_*.csv", "results/sweeps"),
    ("outputs/logs/atr_fix_before_after_2026-10-13.csv", "results"),
    ("outputs/logs/event_study_train_*.log", "results/event_study"),   # current runs only
    ("outputs/logs/event_study_test_*.log", "results/event_study"),
    ("outputs/logs/intraday_description_*.log", "results"),
    ("outputs/logs/source_consistency_*.log", "results"),
    ("github_README.md", "."),                                # written for the supervisor
]

STATIC = {
    "requirements.txt": """# Python 3.13. Core:
pandas==2.3.3
numpy==2.3.4
matplotlib==3.10.7
requests==2.32.5
python-dotenv==1.2.3
yfinance==0.2.66
# LLM scoring (Ollama via its OpenAI-compatible API) and optional providers:
openai==3.3.1
google-genai==2.20.0
# optional: live pusher / Bloomberg conversion
websocket-client==1.9.0
openpyxl==3.1.5
# anthropic        (optional provider, not used in the thesis runs)
""",
    ".env.example": """# Copy to .env and fill in. Never commit .env.
ALPACA_KEY=
ALPACA_SECRET=
OLLAMA_BASE_URL=http://<ollama-host>:11434/v1
GOOGLE_API_KEY=
GROQ_API_KEY=
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
""",
    ".gitignore": """.env
ALPACA_KEY.py
data_sources/*
!data_sources/nasdaq100.txt
!data_sources/company_names.csv
__pycache__/
.DS_Store
""",
}


def collect() -> list[tuple[Path, Path]]:
    pairs = []
    for pattern, dest in ALLOW:
        for src in sorted(ROOT.glob(pattern)):
            if src.is_file() and "__pycache__" not in src.parts and "DRAFT" not in src.name:
                pairs.append((src, OUT / dest / src.name))
    return pairs


def secret_values() -> list[str]:
    vals = []
    for f in SECRET_FILES:
        if f.exists():
            for line in f.read_text().splitlines():
                m = re.search(r"=\s*['\"]?([A-Za-z0-9_\-:/.]{12,})['\"]?\s*$", line)
                if m and not m.group(1).startswith("http"):
                    vals.append(m.group(1))
    return vals


def check(pairs: list[tuple[Path, Path]]) -> list[str]:
    problems, secrets = [], secret_values()
    for src, dst in pairs:
        if src.stat().st_size > MAX_BYTES:
            problems.append(f"too large: {src.relative_to(ROOT)}")
        text = src.read_text(errors="ignore") if src.suffix != ".png" else ""
        if any(v in text for v in secrets):
            problems.append(f"contains a secret value: {src.relative_to(ROOT)}")
        if src.suffix == ".csv":
            header = {c.strip().lower() for c in text.split("\n", 1)[0].split(",")}
            if header & RAW_COLUMNS and src.name != "company_names.csv":
                problems.append(f"raw-data columns {sorted(header & RAW_COLUMNS)}: {src.relative_to(ROOT)}")
    return problems


def build(pairs: list[tuple[Path, Path]]) -> None:
    if OUT.exists():
        if not (OUT / MARKER).exists():
            raise SystemExit(f"{OUT} exists but was not built by this script -- not touching it")
        shutil.rmtree(OUT)
    for src, dst in pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for name, body in STATIC.items():
        (OUT / name).write_text(body)
    readme = OUT / "github_README.md"
    if readme.exists():
        readme.rename(OUT / "README.md")
    (OUT / MARKER).write_text("rebuilt by src/make_github_release.py; safe to delete\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    pairs = collect()
    problems = check(pairs)
    for src, dst in pairs:
        print(f"  {str(dst.relative_to(OUT)):<70} {src.stat().st_size / 1024:8.1f} KB")
    print(f"\n{len(pairs)} files + {len(STATIC)} generated ({', '.join(STATIC)})"
          f" | total {sum(s.stat().st_size for s, _ in pairs) / 1024 / 1024:.1f} MB")
    if not (ROOT / "github_README.md").exists():
        print("NOTE: github_README.md not written yet -- the folder will have no README")
    if problems:
        raise SystemExit("BLOCKED:\n  " + "\n  ".join(problems))
    print("checks passed: no secret values, no raw-data CSVs, no file > 10 MB")
    if not args.dry_run:
        build(pairs)
        print(f"built {OUT}")


if __name__ == "__main__":
    main()
