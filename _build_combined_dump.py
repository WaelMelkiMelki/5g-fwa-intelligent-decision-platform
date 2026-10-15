"""Build FWA_project_COMBINED_DUMP.txt per user request.

User spec (2026-08-31):
- 1.c: recursive, but don't include .venv
- 2: extensions = .py + .txt + .md + .json + .tex + .bib + .yaml + .toml + .sql + .log
     (+ .csv truncated, + .yml as yaml alias)
- 3: create new file FWA_project_COMBINED_DUMP.txt
- 4: order alphabetically by path, truncate csv's

Interpretation & safety:
- .venv excluded as requested; also exclude .git / __pycache__ / .pytest_cache
  (not project sources, would bloat dump with binaries/git metadata).
- Exclude self + previous dumps (FWA_project_all_sources.txt, etc.) to avoid duplication.
- Exclude app/.streamlit/secrets.toml (contains live credentials), include .example.
- CSVs truncated to first 30 lines (user request).
- Huge files (>200 lines for .sql/.log, >500KB) also truncated to first 100-200 lines
  to prevent 95 MB sql from making dump unopenable in Notepad.
"""
from pathlib import Path
from datetime import date
import re

ROOT = Path(r"C:\Users\w50057230\Downloads\FWA project")
OUT = ROOT / "FWA_project_COMBINED_DUMP.txt"

TEXT_EXTS = {".py", ".txt", ".md", ".json", ".tex", ".bib", ".yaml", ".yml", ".toml", ".sql", ".log", ".csv"}

EXCLUDED_FILES = {
    "FWA_project_all_sources.txt",
    "FWA_project_python_code.txt",
    "FWA_project_COMBINED_DUMP.txt",
    "_build_combined_dump.py",
    "_build_code_dump.py",
    "_build_full_dump.py",
    # duplicate merged reports
    "report_v4/all_sources.txt",
    "report_v4/all_sources_backup.txt",
    "report_v4/all_sources_backup_v1.txt",
    "report_v4/combined_report.txt",
    "report_v4/merged_output.txt",
    "report_v4/main.txt",
    # credentials
    "app/.streamlit/secrets.toml",
    # huge raw sql not useful for LLM / would be 95 MB
    # we keep it truncated instead of fully excluded, but flag here if you want full exclude
}

# redact credentials only in dump, not source
REDACTION_PATTERNS = [
    (re.compile(r"postgres:admin@"), "postgres:[REDACTED]@"),
    (re.compile(r"(['\"]?\bpassword['\"]?\s*[:=]\s*['\"])(admin)(['\")])"), r"\1[REDACTED]\3"),
]

def redact(text: str) -> str:
    for pat, repl in REDACTION_PATTERNS:
        text = pat.sub(repl, text)
    return text

def read_file(p: Path):
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = p.read_text(encoding="latin-1", errors="replace")
    return text

def is_excluded_dir(parts):
    # user said only .venv, but we also skip git/cache for practicality
    blocked = {".venv", ".git", "__pycache__", ".pytest_cache"}
    return any(part in blocked for part in parts[:-1])

# CSV truncation
CSV_MAX_LINES = 30
LARGE_MAX_LINES = 100  # for .sql/.log huge files

def maybe_truncate(rel: str, ext: str, text: str):
    lines = text.splitlines()
    n = len(lines)
    truncated = False
    limit = None
    note = ""
    if ext == ".csv":
        if n > CSV_MAX_LINES:
            truncated = True
            limit = CSV_MAX_LINES
            note = f"[TRUNCATED] CSV showing first {limit} of {n} lines (user requested truncation). Full file: {rel} ({len(text.encode('utf-8')):,} bytes)"
    elif ext in {".sql", ".log"}:
        if n > 200:  # huge sql/log
            truncated = True
            limit = LARGE_MAX_LINES
            note = f"[TRUNCATED] {ext} showing first {limit} of {n} lines to keep dump openable. Full file: {rel} ({len(text.encode('utf-8')):,} bytes, 95 MB sql truncated)"
    elif ext == ".txt" and n > 1000:
        # e.g. report_v4/all_sources_backup_v1.txt 197k but >1000 lines
        if n > 1000:
            truncated = True
            limit = 200
            note = f"[TRUNCATED] .txt showing first {limit} of {n} lines (file too large for Notepad). Full file: {rel}"
    if truncated:
        truncated_text = "\n".join(lines[:limit])
        if text.endswith("\n"):
            truncated_text += "\n"
        truncated_text += f"\n... {note} ...\n"
        return truncated_text, limit, note, n
    return text, n, "", n

def collect():
    candidates = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if is_excluded_dir(p.parts):
            continue
        # handle .toml.example
        ext = p.suffix.lower()
        if p.name.lower().endswith(".toml.example"):
            ext = ".toml"
        if ext not in TEXT_EXTS:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in EXCLUDED_FILES:
            continue
        if p.name.startswith("_build_"):
            continue
        if p.name.endswith(".pre_edit_backup"):
            continue
        candidates.append(p)
    candidates = sorted(candidates, key=lambda p: p.relative_to(ROOT).as_posix().lower())
    return candidates

def main():
    candidates = collect()
    bar = "=" * 78
    # Prepare data
    data = []  # (rel, ext, full_lines, truncated_lines, size, text_to_write, note, was_truncated)
    total_full_lines = 0
    total_shown_lines = 0
    total_bytes = 0
    for p in candidates:
        rel = p.relative_to(ROOT).as_posix()
        ext = p.suffix.lower()
        if p.name.lower().endswith(".toml.example"):
            ext = ".toml"
        text = read_file(p)
        text = redact(text)
        full_n = len(text.splitlines())
        total_full_lines += full_n
        total_bytes += p.stat().st_size
        trunc_text, shown_n, note, _ = maybe_truncate(rel, ext, text)
        total_shown_lines += shown_n if trunc_text != text else full_n
        was_trunc = trunc_text != text
        data.append((rel, ext, full_n, shown_n, p.stat().st_size, trunc_text, note, was_trunc, p))

    # Build output
    out_lines = []
    out_lines.append(bar)
    out_lines.append("FWA PROJECT — COMBINED TEXT DUMP")
    out_lines.append(f"Generated: {date.today().isoformat()}")
    out_lines.append(f"Source root: {ROOT}")
    out_lines.append(f"Output file: {OUT.name}")
    out_lines.append(bar)
    out_lines.append("""
PURPOSE
-------
Single .txt file aggregating ALL text-readable project files,
each separated by its path relative to FWA project folder.
Openable in Notepad (all entries are plain text).

USER SPEC APPLIED
-----------------
- Scope: recursive (1.c) excluding .venv (user) + .git/__pycache__/.pytest_cache (sanity)
- Included extensions: .py + .txt + .md + .json + .tex + .bib + .yaml/.yml + .toml + .sql + .log
  (+ .csv truncated per user request)
- Excluded files: self (FWA_project_COMBINED_DUMP.txt), previous dumps
  (FWA_project_all_sources.txt, FWA_project_python_code.txt), merged report dupes,
  app/.streamlit/secrets.toml (credentials)
- Ordering: alphabetically by relative path (case-insensitive)
- Truncation: .csv -> first 30 lines; huge .sql/.log (>200 lines) -> first 100 lines;
  huge .txt (>1000 lines) -> first 200 lines. Truncated files are marked with [TRUNCATED].
""")
    out_lines.append(f"Included types: {', '.join(sorted(TEXT_EXTS))}")
    out_lines.append(f"Total files collected: {len(data)}")
    out_lines.append(f"Total full lines (if untruncated): {total_full_lines:,}")
    out_lines.append(f"Total shown lines (after truncation): {total_shown_lines:,}")
    out_lines.append(f"Total source bytes on disk: {total_bytes:,}")
    out_lines.append("")
    out_lines.append(bar)
    out_lines.append("TABLE OF CONTENTS (alphabetical by path)")
    out_lines.append(bar)
    for rel, ext, full_n, shown_n, sz, _, note, was_trunc, _ in data:
        flag = " [TRUNCATED]" if was_trunc else ""
        if was_trunc:
            out_lines.append(f"{rel}  ({shown_n}/{full_n} lines shown, {sz:,} bytes){flag}")
        else:
            out_lines.append(f"{rel}  ({full_n} lines, {sz:,} bytes)")
    out_lines.append("")
    out_lines.append(f"TOTAL: {len(data)} files, {total_shown_lines:,}/{total_full_lines:,} lines shown, {total_bytes:,} bytes source")
    out_lines.append("")
    # File entries
    for rel, ext, full_n, shown_n, sz, text_to_write, note, was_trunc, p in data:
        out_lines.append("")
        out_lines.append(bar)
        if was_trunc:
            out_lines.append(f"FILE: {rel}  |  {shown_n}/{full_n} lines shown (TRUNCATED)  |  {sz:,} bytes  |  {ext}")
            out_lines.append(f"PATH: {(ROOT / rel).as_posix()}")
            out_lines.append(f"NOTE: {note}")
        else:
            out_lines.append(f"FILE: {rel}  |  {full_n} lines  |  {sz:,} bytes  |  {ext}")
            out_lines.append(f"PATH: {(ROOT / rel).as_posix()}")
        out_lines.append(bar)
        if text_to_write.strip() == "":
            out_lines.append("(empty file)")
        else:
            out_lines.append(text_to_write)
        if not text_to_write.endswith("\n"):
            out_lines.append("")

    OUT.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Files: {len(data)}  FullLines: {total_full_lines:,}  ShownLines: {total_shown_lines:,}  SourceBytes: {total_bytes:,}  OutBytes: {OUT.stat().st_size:,}")
    truncated_count = sum(1 for d in data if d[7])
    print(f"Truncated: {truncated_count} files")
    # also print list of truncated
    for rel, ext, full_n, shown_n, sz, _, note, was_trunc, _ in data:
        if was_trunc:
            print(f"  TRUNC {rel} {shown_n}/{full_n} {sz:,} bytes")

if __name__ == "__main__":
    main()
