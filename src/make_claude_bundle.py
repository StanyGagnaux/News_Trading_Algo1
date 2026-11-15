"""
make_claude_bundle.py -- turn for_claude/ into files that can be attached to a
Claude chat message: one Markdown file with every text file (README first,
each file in its own section) plus the charts as separate PNGs, and a zip of
the whole folder as an alternative.

USAGE (from the project root; rerun whenever for_claude/ changes):
  python3 src/make_claude_bundle.py
Outputs: for_claude_bundle.md, for_claude.zip (project root).
"""
from __future__ import annotations

import zipfile
from datetime import datetime

from paths import ROOT

SRC = ROOT / "for_claude"
BUNDLE = ROOT / "for_claude_bundle.md"
ZIP = ROOT / "for_claude.zip"
FIRST = ["README.md", "current_state.md", "FROZEN_CONFIG_2026-10-18.md",
         "FROZEN_CONFIG_2026-10-18_note_2026-10-18.md", "FROZEN_CONFIG_hashes.txt",
         "results.md", "bugs.md", "changelog.md"]
TEXT_SUFFIXES = {".md", ".txt", ".csv", ".log"}
FENCE = {".csv": "csv", ".log": "text", ".txt": "text"}


def ordered_text_files() -> list:
    files = [p for p in SRC.iterdir() if p.suffix in TEXT_SUFFIXES]
    rank = {name: i for i, name in enumerate(FIRST)}
    return sorted(files, key=lambda p: (rank.get(p.name, len(FIRST)), p.name))


def build_bundle() -> list:
    files = ordered_text_files()
    images = sorted(p.name for p in SRC.iterdir() if p.suffix == ".png")
    parts = [f"# for_claude bundle — built {datetime.now():%Y-%m-%d %H:%M}\n",
             "All text files of the for_claude/ folder, one section each (README "
             "first). Charts are attached separately: " + ", ".join(images) + ".\n",
             "## Contents\n" + "\n".join(f"- {p.name}" for p in files) + "\n"]
    for p in files:
        body = p.read_text(encoding="utf-8")
        if p.suffix == ".md":
            parts.append(f"\n---\n\n## FILE: {p.name}\n\n{body}\n")
        else:
            parts.append(f"\n---\n\n## FILE: {p.name}\n\n```{FENCE[p.suffix]}\n{body.rstrip()}\n```\n")
    BUNDLE.write_text("".join(parts), encoding="utf-8")
    return images


def build_zip() -> None:
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(SRC.iterdir()):
            if p.is_file():
                z.write(p, f"for_claude/{p.name}")


def main():
    images = build_bundle()
    build_zip()
    print(f"{BUNDLE.name}: {BUNDLE.stat().st_size / 1024:.0f} KB | {ZIP.name}: "
          f"{ZIP.stat().st_size / 1024:.0f} KB")
    print("attach: for_claude_bundle.md + " + " + ".join(f"for_claude/{i}" for i in images))


if __name__ == "__main__":
    main()
