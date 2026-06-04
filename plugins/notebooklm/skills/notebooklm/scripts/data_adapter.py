#!/usr/bin/env python3
"""data_adapter.py - turn tabular data into a Markdown table source for NotebookLM.

NotebookLM does NOT accept raw CSV as a source, so structured data must be fed
as a Markdown table (added via `nlm.py add --file table.md`). This module is the
generic, project-agnostic version of that bridge: give it rows (or a CSV file)
and it emits a titled Markdown document with a table -- plus an optional
"what changed" table when you pass a previous snapshot.

Use it as a library:
    from data_adapter import rows_to_markdown, csv_to_markdown, diff_markdown

or as a CLI:
    python data_adapter.py prices.csv --title "Daily prices" --out prices.md
    python data_adapter.py new.csv --prev old.csv --key item,source --value price --out changes.md

The food-price project's original markdown_export.py pulled rows from SQLite and
hard-coded price columns; this keeps the exact same Markdown shape but takes the
rows from anywhere, so any project can reuse it: query your DB / API / CSV into a
list of dicts, then call rows_to_markdown(). Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from typing import Iterable, Mapping, Sequence


def _esc(text) -> str:
    """Escape pipe chars so cell values don't break the Markdown table."""
    s = str("" if text is None else text)
    # Collapse all line/cell-breaking whitespace (CR, LF, TAB) to spaces before
    # escaping pipes, otherwise a bare \r or \t leaks into the cell and splits
    # the row across lines / columns in some Markdown renderers.
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return s.replace("|", "\\|").strip()


def _num_str(x: float) -> str:
    """Format a numeric value losslessly (no scientific notation).

    f"{x:g}" renders large magnitudes in lossy scientific form (1000000 ->
    '1e+06'), which collapses distinct values to one string. Render integers
    plainly and floats with trailing zeros trimmed instead.
    """
    if x != x or x in (float("inf"), float("-inf")):
        return repr(x)  # NaN / inf have no plain decimal form
    if x == int(x):
        return str(int(x))
    return ("%f" % x).rstrip("0").rstrip(".")


def _signed_num_str(x: float) -> str:
    """Like _num_str but with an explicit leading sign (for deltas)."""
    s = _num_str(abs(x))
    return ("-" if x < 0 else "+") + s


def rows_to_markdown(
    headers: Sequence[str],
    rows: Iterable[Sequence],
    *,
    title: str | None = None,
    intro: Sequence[str] | None = None,
    right_align: Sequence[str] | None = None,
) -> str:
    """Render rows as a Markdown document with a single table.

    headers      column names (table header row)
    rows         iterable of row sequences (same width as headers)
    title        optional H1 above the table
    intro        optional bullet lines between the title and the table
    right_align  header names to right-align (numbers); others left-align
    """
    headers = list(headers)
    right = set(right_align or ())
    seps = ["---:" if h in right else "---" for h in headers]

    out: list[str] = []
    if title:
        out += [f"# {title}", ""]
    for line in (intro or []):
        out.append(f"- {line}")
    if intro:
        out.append("")
    # Empty headers would emit a malformed '|  |' / '||' table; emit the same
    # placeholder csv_to_markdown uses for an empty input instead.
    if not headers:
        out.append("_No rows._")
        return "\n".join(out) + "\n"
    ncols = len(headers)
    out.append("| " + " | ".join(_esc(h) for h in headers) + " |")
    out.append("|" + "|".join(seps) + "|")
    for row in rows:
        # Normalize every data row to exactly ncols cells. GFM silently
        # truncates over-long rows (= data loss), so pad short rows with '' and
        # for over-long rows keep all cells (no silent drop) but warn.
        cells = [_esc(c) for c in row]
        if len(cells) < ncols:
            cells += [""] * (ncols - len(cells))
        elif len(cells) > ncols:
            print(
                f"data_adapter: row has {len(cells)} cells, header has {ncols}; "
                "keeping extra cells",
                file=sys.stderr,
            )
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def dicts_to_markdown(
    records: Sequence[Mapping],
    *,
    columns: Sequence[str] | None = None,
    **kw,
) -> str:
    """Convenience: render a list of dicts.

    Columns default to the UNION of keys across all records (insertion order
    preserved), not just the first record's keys -- otherwise a key present only
    on later records is silently dropped.
    """
    records = list(records)
    if not records:
        return rows_to_markdown(columns or [], [], **kw)
    if columns is not None:
        cols = list(columns)
    else:
        cols = list(dict.fromkeys(c for rec in records for c in rec.keys()))
    rows = [[rec.get(c, "") for c in cols] for rec in records]
    return rows_to_markdown(cols, rows, **kw)


def _read_csv(path: str | pathlib.Path) -> tuple[list[str], list[list[str]]]:
    # utf-8-sig strips a leading BOM (Excel / PowerShell Out-File write one),
    # which would otherwise corrupt the first column name -> broken --key matching.
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _looks_numeric(values: Iterable[str]) -> bool:
    seen = False
    for v in values:
        v = (v or "").strip().replace(",", "")
        if v == "":
            continue
        seen = True
        try:
            float(v)
        except ValueError:
            return False
    return seen


def csv_to_markdown(path: str | pathlib.Path, *, title: str | None = None,
                    intro: Sequence[str] | None = None) -> str:
    """Read a CSV file and render it as a Markdown table (numeric columns right-aligned)."""
    headers, rows = _read_csv(path)
    title = title or pathlib.Path(path).stem
    if not headers:
        return f"# {title}\n\n_No rows._\n"
    right = [h for i, h in enumerate(headers) if _looks_numeric(r[i] if i < len(r) else "" for r in rows)]
    return rows_to_markdown(headers, rows, title=title, intro=intro, right_align=right)


def diff_markdown(
    new_rows: Sequence[Mapping],
    old_rows: Sequence[Mapping],
    *,
    key: Sequence[str],
    value: str,
    title: str = "Changes vs previous snapshot",
) -> str:
    """Render a 'what changed' table comparing a numeric `value` column keyed by `key`.

    Generalizes the food-price "price changes" table: NEW / GONE / +delta, sorted
    by absolute change. Rows are dicts; key is the tuple of columns identifying a
    record, value is the numeric column to diff.
    """
    def k(rec):
        return tuple(str(rec.get(c, "")) for c in key)

    def num(rec):
        try:
            return float(str(rec.get(value, "")).replace(",", ""))
        except (ValueError, TypeError):
            return None

    # Track key PRESENCE separately from the parsed numeric value: a key that
    # exists in old but whose value is blank/non-numeric (prev is None) must NOT
    # be confused with a genuinely new key.
    def _build_map(rows, label):
        # Duplicate key-tuples collapse last-wins; warn so the silent collapse
        # is at least visible rather than masking dropped records.
        m = {}
        for r in rows:
            kk = k(r)
            if kk in m:
                print(
                    f"data_adapter: duplicate key {kk} in {label} rows "
                    "(last value wins)",
                    file=sys.stderr,
                )
            m[kk] = num(r)
        return m

    old_map = _build_map(old_rows, "previous")
    new_map = _build_map(new_rows, "new")
    old_keys = set(old_map)
    new_keys = set(new_map)

    changes = []  # (key_tuple, prev, now, delta_or_None, kind)
    for kk in new_keys:
        now = new_map.get(kk)
        if kk not in old_keys:
            changes.append((kk, None, now, None, "NEW"))
            continue
        prev = old_map.get(kk)
        if prev is not None and now is not None and abs(now - prev) > 1e-9:
            changes.append((kk, prev, now, now - prev, "changed"))
        elif (prev is None) != (now is None):
            # one side unparseable while the other is a number -> still a change
            changes.append((kk, prev, now, None, "changed"))
        # else: equal numbers, or both unparseable -> unchanged, skip
    for kk in old_keys:
        if kk not in new_keys:
            changes.append((kk, old_map.get(kk), None, None, "GONE"))

    # Magnitude descending, then key tuple ascending. The secondary key makes
    # ordering deterministic: NEW/GONE/None-delta rows all tie at 0.0 magnitude
    # and would otherwise come out in hash-randomized set-iteration order.
    changes.sort(key=lambda c: (-(abs(c[3]) if c[3] is not None else 0.0), c[0]))

    headers = list(key) + ["Prev", "Now", "Change"]
    out_rows = []
    for kk, prev, now, delta, kind in changes:
        prev_s = "-" if prev is None else _num_str(prev)
        now_s = "-" if now is None else _num_str(now)
        if kind == "NEW":
            change_s = "NEW"
        elif kind == "GONE":
            change_s = "GONE"
        elif delta is not None:
            change_s = _signed_num_str(delta)
        else:
            change_s = "changed"
        out_rows.append(list(kk) + [prev_s, now_s, change_s])
    right = ["Prev", "Now", "Change"]
    return rows_to_markdown(headers, out_rows, title=title, right_align=right)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CSV -> Markdown table source for NotebookLM")
    ap.add_argument("csv", help="input CSV file")
    ap.add_argument("--title", help="document title (default: CSV file stem)")
    ap.add_argument("--out", help="write Markdown here (default: print to stdout)")
    ap.add_argument("--prev", help="a previous CSV snapshot -> emit a 'changes' table instead")
    ap.add_argument("--key", help="comma-separated key columns (with --prev)")
    ap.add_argument("--value", help="numeric column to diff (with --prev)")
    args = ap.parse_args(argv)

    if args.prev:
        if not (args.key and args.value):
            print("--prev requires --key and --value", file=sys.stderr)
            return 2
        new_headers, new_rows = _read_csv(args.csv)
        old_headers, old_rows = _read_csv(args.prev)

        def _to_dicts(headers, rows):
            # Pad ragged rows to header width before zipping: a short row would
            # otherwise drop its trailing keys entirely, so a blank-but-present
            # value masquerades as an absent key (looks 'changed' in the diff).
            out = []
            for r in rows:
                if len(r) < len(headers):
                    r = list(r) + [""] * (len(headers) - len(r))
                out.append(dict(zip(headers, r)))
            return out

        new_dicts = _to_dicts(new_headers, new_rows)
        old_dicts = _to_dicts(old_headers, old_rows)
        md = diff_markdown(new_dicts, old_dicts,
                           key=[c.strip() for c in args.key.split(",")], value=args.value)
    else:
        md = csv_to_markdown(args.csv, title=args.title)

    if args.out:
        pathlib.Path(args.out).write_text(md, encoding="utf-8")
        print(f"Wrote {args.out} ({len(md)} chars)")
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    raise SystemExit(main())
