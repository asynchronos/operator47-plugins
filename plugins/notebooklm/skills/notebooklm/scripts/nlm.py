#!/usr/bin/env python3
"""nlm.py - portable NotebookLM CLI: turn local text/Markdown into an AI report + infographic.

Project-agnostic wrapper around the UNOFFICIAL ``notebooklm-py`` library (PyPI
``notebooklm-py``, import ``notebooklm``, CLI ``notebooklm``), which drives Google
NotebookLM's internal API. Point it at any files / directories / text; it finds
(or creates) a notebook, adds your content as sources, then generates and
downloads a report (Markdown) and/or an infographic (PNG). It can also ask one
grounded question first.

Nothing here is specific to any project: sources are plain text/Markdown, so the
same script works for a docs set, a research dump, a CSV exported to a Markdown
table (see data_adapter.py), meeting notes, etc.

Subcommands
    check       verify auth + list notebooks
    add         add sources (--file / --dir+--glob / --text / --stdin) to a notebook
    generate    from an EXISTING notebook: report and/or infographic (+ optional --question)
    run         end-to-end: add sources, then generate
    chat        ask one grounded question against a notebook

One-time setup (see references/setup.md):
    py -m pip install -r requirements.txt        # installs notebooklm-py[browser]
    notebooklm login                             # sign in with a THROWAWAY Google account
    notebooklm auth check --test --json           # expect {"status": "ok"}

WARNING: notebooklm-py talks to NotebookLM's PRIVATE internal API. It is
unofficial and against Google's ToS. Use a spare Google account, keep usage
light, and treat it as best-effort tooling. See references/legal.md.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import pathlib
import sys
from datetime import datetime

# --- import notebooklm-py defensively -------------------------------------
# Enums live at the top level in 0.5.x and under notebooklm.rpc in 0.6.x; we
# accept either so the plugin works across versions.
_IMPORT_OK = True
_IMPORT_ERR: Exception | None = None
try:
    from notebooklm import NotebookLMClient  # type: ignore

    try:
        from notebooklm import (  # type: ignore
            ReportFormat,
            InfographicOrientation,
            InfographicDetail,
            InfographicStyle,
        )
    except ImportError:  # 0.6.x moved the enums under notebooklm.rpc
        from notebooklm.rpc import (  # type: ignore
            ReportFormat,
            InfographicOrientation,
            InfographicDetail,
            InfographicStyle,
        )
except ImportError as exc:  # notebooklm-py not installed at all
    _IMPORT_OK = False
    _IMPORT_ERR = exc


# --- enum maps (built only when the import succeeded) ----------------------
def _safe_map(enum, pairs):
    """Build {cli_name: enum_member} including ONLY members present in this version.

    Enum membership varies across notebooklm-py releases, so we never reference a
    member unconditionally (that would AttributeError on a version that lacks it).
    """
    out = {}
    for cli, member in pairs:
        if hasattr(enum, member):
            out[cli] = getattr(enum, member)
    return out


def _enum_maps():
    report = _safe_map(ReportFormat, [
        ("briefing", "BRIEFING_DOC"), ("study", "STUDY_GUIDE"),
        ("blog", "BLOG_POST"), ("custom", "CUSTOM"),
    ])
    orientation = _safe_map(InfographicOrientation, [
        ("landscape", "LANDSCAPE"), ("portrait", "PORTRAIT"), ("square", "SQUARE"),
    ])
    detail = _safe_map(InfographicDetail, [
        ("concise", "CONCISE"), ("standard", "STANDARD"), ("detailed", "DETAILED"),
    ])
    style = _safe_map(InfographicStyle, [
        ("auto", "AUTO_SELECT"), ("sketch", "SKETCH_NOTE"), ("professional", "PROFESSIONAL"),
        ("bento", "BENTO_GRID"), ("editorial", "EDITORIAL"), ("instructional", "INSTRUCTIONAL"),
        ("bricks", "BRICKS"), ("clay", "CLAY"), ("anime", "ANIME"),
        ("kawaii", "KAWAII"), ("scientific", "SCIENTIFIC"),
    ])
    return report, orientation, detail, style


def _filter_kwargs(fn, kwargs):
    """Drop kwargs the installed function signature doesn't accept (version tolerance).

    generate_* signatures differ across notebooklm-py versions; passing an
    unsupported keyword would raise TypeError and silently kill that artifact.
    If the function takes **kwargs we pass everything through.
    """
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs
    return {k: v for k, v in kwargs.items() if k in params}


REPORT_CHOICES = ["briefing", "study", "blog", "custom"]
STYLE_CHOICES = ["auto", "sketch", "professional", "bento", "editorial",
                 "instructional", "bricks", "clay", "anime", "kawaii", "scientific"]
ORIENTATION_CHOICES = ["landscape", "portrait", "square"]
DETAIL_CHOICES = ["concise", "standard", "detailed"]


# --- client open (version-tolerant) ----------------------------------------
async def _open_client(storage: str | None, profile: str | None):
    """Return an entered-ready NotebookLM client context manager.

    ``from_storage`` is a sync classmethod in notebooklm-py 0.5.x (returns the
    client directly) but an ``async def`` in 0.6.x (must be awaited). We detect
    which at runtime and await only when needed, so the same code works on both.
    The object we hand back is the client, which is itself an async context
    manager -- callers do ``async with (await _open_client(...)) as client:``.
    """
    cm = NotebookLMClient.from_storage(path=storage, profile=profile)
    if inspect.isawaitable(cm):
        cm = await cm
    return cm


# --- shared helpers ---------------------------------------------------------
async def _find_or_create(client, title: str, *, reuse: bool, create: bool):
    """Resolve a notebook by exact title. Returns (notebook, created_bool|None).

    reuse=True  -> return the first notebook matching ``title`` if present.
    create=True -> create it when not found (otherwise return (None, None)).
    """
    nb = None
    if reuse or not create:
        for cand in await client.notebooks.list():
            if cand.title == title:
                nb = cand
                break
    if nb is None and create:
        nb = await client.notebooks.create(title)
        return nb, True
    return nb, (False if nb is not None else None)


async def _existing_source_titles(client, nb):
    """Best-effort set of source titles already in the notebook + could_list flag.

    notebooklm-py's source-listing surface is not guaranteed across versions, so
    we probe a couple of likely shapes and fall back to "cannot enumerate".
    """
    candidates = []
    sources_svc = getattr(client, "sources", None)
    if sources_svc is not None and hasattr(sources_svc, "list"):
        candidates.append(lambda: sources_svc.list(nb.id))
    if hasattr(nb, "sources"):
        candidates.append(lambda: nb.sources)
    for get in candidates:
        try:
            res = get()
            if asyncio.iscoroutine(res):
                res = await res
            titles = {t for s in (res or []) if (t := getattr(s, "title", None))}
            return titles, True
        except Exception:
            continue
    return set(), False


async def _add_text_source(client, nb_id: str, title: str, content: str) -> bool:
    try:
        src = await client.sources.add_text(nb_id, title, content, wait=True)
        print(f"  + added: {title}  (id={getattr(src, 'id', '?')}, "
              f"ready={getattr(src, 'is_ready', '?')})")
        return True
    except Exception as e:
        print(f"  ! failed: {title}  -> {type(e).__name__}: {e}")
        return False


async def _finish_artifact(client, nb_id, status, download_fn, out_path, label, timeout):
    """Wait for a non-blocking generation to complete, then download it.

    generate_* returns immediately with a GenerationStatus; rate-limit / quota
    rejections come back as status.is_failed (and often is_rate_limited /
    is_removed) WITHOUT raising. wait_for_completion only raises on timeout, so
    a non-complete terminal status ("failed"/"removed") is checked explicitly.
    task_id == artifact_id.
    """
    if getattr(status, "is_failed", False) or getattr(status, "is_removed", False):
        why = ("rate-limit / quota (USER_DISPLAYABLE_ERROR)"
               if getattr(status, "is_rate_limited", False)
               else (getattr(status, "error_code", None) or getattr(status, "error", None) or "unknown"))
        print(f"  [{label}] generation rejected: {why}")
        return None

    # task_id should always be present on a non-failed status; guard so a
    # malformed response gives a clear message instead of an AttributeError that
    # the catch-all in main() would mislabel as an auth/session problem.
    task_id = getattr(status, "task_id", None)
    if task_id is None:
        print(f"  [{label}] unexpected generation response (no task_id)")
        return None

    print(f"  [{label}] generating (task {task_id}) ...")
    try:
        final = await client.artifacts.wait_for_completion(nb_id, task_id, timeout=timeout)
    except Exception as e:  # TimeoutError (and similar)
        print(f"  [{label}] timed out / error while waiting: {type(e).__name__}: {e}")
        return None

    if not final.is_complete:
        print(f"  [{label}] did not complete: status={final.status} error={getattr(final, 'error', None)}")
        return None

    out_path.parent.mkdir(parents=True, exist_ok=True)
    saved = await download_fn(nb_id, str(out_path), artifact_id=task_id)
    print(f"  [{label}] saved -> {saved}")
    return saved


# --- source collection (for add / run) -------------------------------------
def _collect_sources(args) -> list[tuple[str, str]]:
    """Build a work-list of (source_title, content) from --file/--dir/--text/--stdin."""
    work: list[tuple[str, str]] = []
    # utf-8-sig strips a leading BOM if present (harmless otherwise).
    for f in (args.file or []):
        p = pathlib.Path(f)
        work.append((p.name, p.read_text(encoding="utf-8-sig")))
    for d in (args.dir or []):
        for p in sorted(pathlib.Path(d).glob(args.glob)):
            if p.is_file():
                work.append((p.name, p.read_text(encoding="utf-8-sig")))
    if args.text:
        work.append((args.title or "text source", args.text))
    if args.stdin:
        data = sys.stdin.read()
        if data.strip():
            work.append((args.title or "stdin source", data))
    return work


# --- generation core (shared by generate / run) ----------------------------
async def _generate(client, nb_id, args, out_dir, stamp):
    report_map, orient_map, detail_map, style_map = _enum_maps()
    topic = getattr(args, "topic", None) or None

    if getattr(args, "question", None):
        print(f"\nQ: {args.question}")
        res = await client.chat.ask(nb_id, args.question)
        print(f"A: {res.answer}")
        if getattr(res, "references", None):
            print(f"   ({len(res.references)} citation(s))")

    if not args.no_report:
        print("\nGenerating report ...")
        fmt = report_map.get(args.report_format)
        if fmt is None:
            # The requested format isn't available in this notebooklm-py build;
            # say so before silently downgrading to briefing.
            print(f"  ! report-format {args.report_format!r} unavailable in installed "
                  "notebooklm-py; using briefing")
            fmt = report_map.get("briefing")
        kwargs = dict(report_format=fmt, language=args.language)
        if args.report_format == "custom" and topic:
            kwargs["custom_prompt"] = topic          # CUSTOM uses custom_prompt
        elif topic:
            kwargs["extra_instructions"] = topic      # otherwise steer with extra_instructions
        rep = await client.artifacts.generate_report(
            nb_id, **_filter_kwargs(client.artifacts.generate_report, kwargs))
        await _finish_artifact(client, nb_id, rep, client.artifacts.download_report,
                               out_dir / f"report_{stamp}.md", "report", args.timeout)

    if not args.no_infographic:
        print("\nGenerating infographic ...")
        ig_kwargs = dict(
            orientation=orient_map.get(args.orientation),
            detail_level=detail_map.get(args.detail),
            language=args.language,
            instructions=topic,
        )
        style_enum = style_map.get(args.style)   # may be absent on some versions
        if style_enum is not None:
            ig_kwargs["style"] = style_enum
        ig = await client.artifacts.generate_infographic(
            nb_id, **_filter_kwargs(client.artifacts.generate_infographic, ig_kwargs))
        await _finish_artifact(client, nb_id, ig, client.artifacts.download_infographic,
                               out_dir / f"infographic_{stamp}.png", "infographic", args.timeout)


# --- subcommand implementations --------------------------------------------
async def cmd_check(args) -> int:
    async with await _open_client(args.storage, args.profile) as client:
        nbs = await client.notebooks.list()
        print(f"Auth OK. {len(nbs)} notebook(s):")
        for nb in nbs:
            print(f"  - {nb.title!r}  ({nb.id})")
    return 0


async def cmd_add(args) -> int:
    work = _collect_sources(args)
    if not work:
        print("No sources given. Use --file / --dir (+--glob) / --text / --stdin.")
        return 1

    print(f"Notebook: {args.notebook_title!r}")
    print(f"Sources to consider: {len(work)}")
    for title, content in work:
        print(f"  - {title}  ({len(content)} chars)")
    if args.dry_run:
        print("\n[dry-run] nothing was added.")
        return 0

    async with await _open_client(args.storage, args.profile) as client:
        nb, created = await _find_or_create(client, args.notebook_title, reuse=True, create=True)
        print(f"\nNotebook {'created' if created else 'reused'}: {nb.title!r} ({nb.id})")

        existing, could_list = await _existing_source_titles(client, nb)
        if could_list:
            print(f"Existing sources: {len(existing)} (already-added titles will be skipped)")
        else:
            print("Could not enumerate existing sources - adding all (re-running may duplicate).")

        added = skipped = failed = 0
        for title, content in work:
            if could_list and title in existing:
                print(f"  = skip (already present): {title}")
                skipped += 1
                continue
            ok = await _add_text_source(client, nb.id, title, content)
            added += int(ok)
            failed += int(not ok)
        print(f"\nDone. added={added} skipped={skipped} failed={failed}")
    # Every attempted source failed (and none were merely skipped-as-present):
    # surface that as a non-zero exit instead of a misleading success.
    if added == 0 and failed > 0:
        return 1
    return 0


async def _resolve_notebook_id(client, args):
    if args.notebook_id:
        return args.notebook_id, args.notebook_id
    nb, _ = await _find_or_create(client, args.notebook_title, reuse=True, create=False)
    if nb is None:
        return None, None
    return nb.id, nb.title


async def cmd_generate(args) -> int:
    out_dir = pathlib.Path(args.out_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    async with await _open_client(args.storage, args.profile) as client:
        nb_id, nb_title = await _resolve_notebook_id(client, args)
        if not nb_id:
            print(f"Notebook not found by title: {args.notebook_title!r}. "
                  "Pass --notebook-id, or add sources first with `add`.")
            return 1
        print(f"Notebook: {nb_title!r} ({nb_id})")
        await _generate(client, nb_id, args, out_dir, stamp)
        print(f"\nDone. Outputs in {out_dir}{chr(92) if sys.platform == 'win32' else '/'}")
    return 0


async def cmd_run(args) -> int:
    work = _collect_sources(args)
    out_dir = pathlib.Path(args.out_dir)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if args.dry_run:
        print(f"Notebook: {args.notebook_title!r}")
        if work:
            print(f"Sources that WOULD be uploaded: {len(work)}")
            for title, content in work:
                print(f"  - {title}  ({len(content)} chars)")
        else:
            print("(no new sources; generation would run on the notebook's existing sources)")
        gen = []
        if not args.no_report:
            gen.append(f"report (format={args.report_format})")
        if not args.no_infographic:
            gen.append(f"infographic (style={args.style})")
        if getattr(args, "question", None):
            gen.append("a grounded question")
        print(f"Would generate: {', '.join(gen) if gen else 'nothing'}")
        print("\n[dry-run] nothing was uploaded or generated.")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    async with await _open_client(args.storage, args.profile) as client:
        nb, created = await _find_or_create(
            client, args.notebook_title, reuse=args.reuse, create=True)
        print(f"Notebook: {nb.title!r} ({nb.id}) [{'created' if created else 'reused'}]")

        if work:
            existing, could_list = await _existing_source_titles(client, nb)
            added = skipped = failed = 0
            for title, content in work:
                if could_list and title in existing:
                    print(f"  = skip (already present): {title}")
                    skipped += 1
                    continue
                ok = await _add_text_source(client, nb.id, title, content)
                added += int(ok)
                failed += int(not ok)
            # If we tried to add sources and every one failed (none added, none
            # already present), don't burn quota generating from an empty/unchanged
            # notebook -- bail with a clear error.
            if added == 0 and skipped == 0 and failed > 0:
                print("\nNo sources were added (all uploads failed); not generating.")
                return 1
        else:
            print("(no new sources passed; generating from whatever the notebook already has)")

        await _generate(client, nb.id, args, out_dir, stamp)
        print(f"\nDone. Outputs in {out_dir}{chr(92) if sys.platform == 'win32' else '/'}")
    return 0


async def cmd_chat(args) -> int:
    async with await _open_client(args.storage, args.profile) as client:
        nb_id, nb_title = await _resolve_notebook_id(client, args)
        if not nb_id:
            print(f"Notebook not found by title: {args.notebook_title!r}. Pass --notebook-id.")
            return 1
        print(f"Notebook: {nb_title!r} ({nb_id})")
        print(f"\nQ: {args.question}")
        res = await client.chat.ask(nb_id, args.question)
        print(f"A: {res.answer}")
        for r in (getattr(res, "references", None) or []):
            cited = getattr(r, "cited_text", "") or ""
            print(f"   [{getattr(r, 'citation_number', '?')}] {cited[:120]}")
    return 0


# --- argument parsing -------------------------------------------------------
def _add_auth_args(p):
    p.add_argument("--storage", help="path to a storage_state.json (overrides default/profile)")
    p.add_argument("--profile", help="named auth profile (notebooklm --profile <name> login)")


def _add_source_args(p):
    p.add_argument("--file", action="append", help="a file to add as a source (repeatable)")
    p.add_argument("--dir", action="append", help="a directory to add files from (repeatable)")
    p.add_argument("--glob", default="*.md", help="which files in each --dir to add (default *.md)")
    p.add_argument("--text", help="inline text to add as a source")
    p.add_argument("--stdin", action="store_true", help="read a source from STDIN")
    p.add_argument("--title", help="title for --text / --stdin source")


def _add_generate_args(p):
    p.add_argument("--out-dir", default="notebooklm-output",
                   help="where to write the report + infographic (default ./notebooklm-output)")
    p.add_argument("--language", default="en", help="artifact language, e.g. 'en' or 'th'")
    p.add_argument("--question", default="", help="optional grounded question to ask first ('' = skip)")
    p.add_argument("--report-format", choices=REPORT_CHOICES, default="briefing")
    p.add_argument("--no-report", action="store_true", help="skip the report")
    p.add_argument("--no-infographic", action="store_true", help="skip the infographic")
    p.add_argument("--style", choices=STYLE_CHOICES, default="professional")
    p.add_argument("--orientation", choices=ORIENTATION_CHOICES, default="portrait")
    p.add_argument("--detail", choices=DETAIL_CHOICES, default="detailed")
    p.add_argument("--topic", default="",
                   help="steering text: report extra_instructions / infographic instructions "
                        "(or custom_prompt when --report-format custom)")
    p.add_argument("--timeout", type=float, default=600.0, help="seconds to wait per artifact")


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="nlm", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="verify auth + list notebooks")
    _add_auth_args(pc)
    pc.set_defaults(func=cmd_check)

    pa = sub.add_parser("add", help="add sources to a notebook (find-or-create by title)")
    pa.add_argument("--notebook-title", default="NotebookLM sources")
    pa.add_argument("--dry-run", action="store_true", help="list what would be added; add nothing")
    _add_source_args(pa)
    _add_auth_args(pa)
    pa.set_defaults(func=cmd_add)

    pg = sub.add_parser("generate", help="report + infographic from an EXISTING notebook")
    pg.add_argument("--notebook-title", default="NotebookLM sources",
                    help="notebook to target (matched by title)")
    pg.add_argument("--notebook-id", help="notebook id (takes precedence over --notebook-title)")
    _add_generate_args(pg)
    _add_auth_args(pg)
    pg.set_defaults(func=cmd_generate)

    pr = sub.add_parser("run", help="end-to-end: add sources then generate")
    pr.add_argument("--notebook-title", default="NotebookLM sources")
    pr.add_argument("--reuse", action="store_true",
                    help="reuse an existing notebook with the same title instead of always creating")
    pr.add_argument("--dry-run", action="store_true",
                    help="list what would be uploaded + generated; upload and generate nothing")
    _add_source_args(pr)
    _add_generate_args(pr)
    _add_auth_args(pr)
    pr.set_defaults(func=cmd_run)

    pq = sub.add_parser("chat", help="ask one grounded question against a notebook")
    pq.add_argument("question", help="the question to ask")
    pq.add_argument("--notebook-title", default="NotebookLM sources")
    pq.add_argument("--notebook-id", help="notebook id (takes precedence over --notebook-title)")
    _add_auth_args(pq)
    pq.set_defaults(func=cmd_chat)

    return ap.parse_args(argv)


# --- Windows-safe asyncio runner -------------------------------------------
def _run_async(coro):
    """Run an async entry point with a Windows-safe event loop.

    On Windows notebooklm-py needs the SelectorEventLoop (the default
    ProactorEventLoop can hang under httpx). On 3.12+ we pass loop_factory to
    avoid the deprecated set_event_loop_policy (removed in 3.16); older Pythons
    fall back to it.
    """
    if sys.platform != "win32":
        return asyncio.run(coro)
    if sys.version_info >= (3, 12):
        return asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(coro)


def main(argv=None) -> int:
    # Parse args FIRST so -h/--help (which exits 0 inside parse_args) works even
    # without notebooklm-py installed. Only gate on the dependency once we're
    # actually about to run a handler that needs it.
    args = parse_args(argv)

    if not _IMPORT_OK:
        print("notebooklm-py is not installed.")
        print("  py -m pip install -r requirements.txt    (installs notebooklm-py[browser])")
        print("Then sign in once with a THROWAWAY Google account:")
        print("  notebooklm login")
        print("  notebooklm auth check --test --json")
        print(f"\n(import error: {_IMPORT_ERR})")
        return 2

    try:
        return _run_async(args.func(args))
    except Exception as e:
        print(f"\nNotebookLM error: {type(e).__name__}: {e}")
        print("If this looks like an auth/session problem, run:")
        print("  notebooklm login                    # throwaway Google account")
        print("  notebooklm auth check --test --json")
        return 1


if __name__ == "__main__":
    # Windows: avoid UnicodeEncodeError when printing Thai/emoji on cp874/cp932.
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    raise SystemExit(main())
