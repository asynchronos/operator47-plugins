---
name: python-venv
description: Create a Python virtual environment (.venv) in the current project — set up a venv, install requirements.txt or pyproject.toml deps, gitignore the venv. Prefers uv, falls back to stdlib `python -m venv`.
---

# Python Virtual Environment Setup

Create a Python virtual environment in the current working directory, install any project dependencies that are present, ensure the venv is gitignored, and print activation instructions.

The skill is **read-mostly** on the project: it writes exactly two things — the `.venv/` directory and (if needed) a `.venv/` line in `.gitignore`. Nothing else is touched.

## When To Use

Invoke this skill when the user wants to:

- Spin up a fresh Python environment for a new or untouched project
- Install a project's `requirements.txt` or `pyproject.toml` dependencies in isolation
- Recover a broken `.venv/` (recreate from scratch)
- Add `.venv/` to a project's `.gitignore`

Do **not** invoke this skill for:

- Conda/mamba environments (different workflow)
- System-wide pip installs (this skill always isolates)
- Already-active venvs the user just wants to add packages to (use `pip install` directly)

## Procedure

Execute these six steps in order. Each step is gated — confirm with the user (via `AskUserQuestion`) at decision points marked **ask**.

### Step 1 — Detect existing venv

Look for `.venv/` and `venv/` in the current working directory:

```powershell
$existing = @()
if (Test-Path '.venv') { $existing += '.venv' }
if (Test-Path 'venv')  { $existing += 'venv' }
```

If `$existing` is empty, skip to Step 2.

If a venv exists, **ask** the user how to proceed:

- **Reuse** — keep the existing venv, skip Step 3, jump to Step 4 (install deps into it)
- **Recreate** — `Remove-Item -Recurse -Force <path>` on the existing venv, then continue to Step 3
- **Abort** — exit the skill with no changes

Never delete a venv without an explicit "Recreate" answer. If both `.venv/` and `venv/` exist, ask which to act on; do not assume.

### Step 2 — Choose toolchain

Probe for `uv` on PATH:

```powershell
$useUv = $null -ne (Get-Command uv -ErrorAction SilentlyContinue)
```

For bash environments:

```bash
if command -v uv >/dev/null 2>&1; then USE_UV=1; else USE_UV=0; fi
```

Announce the choice to the user in one short line: "Using uv (fast path)." or "uv not found — falling back to stdlib `python -m venv`."

If `uv` is missing AND `python` is also missing from PATH, abort with a clear diagnostic: "No Python interpreter found on PATH. Install Python 3.10+ from python.org or via winget (`winget install Python.Python.3.12`)."

### Step 3 — Create the venv

With uv:

```powershell
uv venv .venv
```

With stdlib:

```powershell
python -m venv .venv
```

Always create the venv at `.venv/` (dot-prefixed, PEP 405 convention). Do not name it `venv/`, `env/`, `.env/`, or anything else.

Verify creation by checking that `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python` (POSIX) exists. If not, surface the underlying command's stderr — do not silently continue.

### Step 4 — Install dependencies

Detect dependency manifests in the project root:

```powershell
$hasRequirements = Test-Path 'requirements.txt'
$hasPyproject    = Test-Path 'pyproject.toml'
```

If both are absent, skip to Step 5 with a one-line note: "No dependency manifests found — venv is empty."

If `requirements.txt` is present, install from it first:

- With uv: `uv pip install -r requirements.txt`
- With stdlib: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` (Windows) or `./.venv/bin/python -m pip install -r requirements.txt` (POSIX)

If `pyproject.toml` is present, install the project itself in editable mode:

- With uv: `uv pip install -e .`
- With stdlib: `.\.venv\Scripts\python.exe -m pip install -e .` (Windows) or `./.venv/bin/python -m pip install -e .` (POSIX)

Always use the venv's interpreter explicitly (`.\.venv\Scripts\python.exe`) — never bare `pip` or `python` outside the venv. Activation is the user's job, not the skill's.

If installation fails (network, missing build deps, version conflict), stop and report the exact pip error. Do not silently continue to Step 5.

### Step 5 — Update `.gitignore`

Ensure `.venv/` is gitignored. The match should be idempotent — if any line in `.gitignore` already gitignores `.venv` (e.g. `.venv`, `.venv/`, `**/.venv/`), do nothing.

Pattern (PowerShell):

```powershell
$gitignorePath = '.gitignore'
$pattern = '^\s*\*?\*?/?\.venv/?\s*$'
$alreadyIgnored = $false
if (Test-Path $gitignorePath) {
    $alreadyIgnored = (Get-Content $gitignorePath) -match $pattern
}
if (-not $alreadyIgnored) {
    Add-Content -Path $gitignorePath -Value "`n.venv/" -Encoding UTF8
}
```

If `.gitignore` does not exist, create it containing a single line: `.venv/`.

Never rewrite the file; only append. Never remove existing lines. Never sort or reformat.

### Step 6 — Report

Print a compact final report with three sections:

**Status line:**

```
✓ venv created at .venv/  (Python 3.12.1, 14 packages, uv)
```

Include: Python version (`.\.venv\Scripts\python.exe --version`), package count (`pip list --format=freeze | Measure-Object -Line`), and the toolchain used (`uv` or `stdlib`).

**Activation hints — all three shells:**

```
PowerShell:    .\.venv\Scripts\Activate.ps1
cmd.exe:       .venv\Scripts\activate.bat
bash/zsh:      source .venv/bin/activate
```

Show all three even on Windows — the user may SSH into Linux/WSL where bash is the default.

**Next-step nudge** (one line):

- If `requirements.txt` was installed: "Run your project's tests to confirm dependencies resolved."
- If `pyproject.toml` was installed editable: "Edits to source files are picked up immediately — no reinstall needed."
- If venv is empty: "Add packages with `uv pip install <pkg>` (or `pip install` after activation)."

## Rules

These are non-negotiable. Violating them risks data loss or surprise.

1. **Never delete a venv without explicit confirmation.** A pre-existing `.venv/` may hold uncommitted edits (editable installs), expensive wheels, or cached builds. Always ask.
2. **Never commit the venv.** Step 5 is mandatory, not optional. A venv in version control is broken on every machine other than the one that built it.
3. **Never run `pip install` outside the venv.** Always use the venv interpreter explicitly: `.\.venv\Scripts\python.exe -m pip`. Bare `pip` invocations may pollute the system Python.
4. **Always use `.venv/` (dot-prefixed).** Do not create `venv/`, `env/`, or any other name. Consistency makes the skill predictable across projects.
5. **Do not chain into `git add` or `git commit`.** The skill scope ends after Step 6. Staging is the user's call.
6. **Do not modify `.gitignore` beyond appending `.venv/`.** Do not sort, dedupe, or reformat. Append only.

## Common Pitfalls

**"Python not found" on Windows.** The Microsoft Store stub (`python.exe` that opens the Store) is on PATH by default. If `python -m venv` opens the Store instead of running, the user has not installed real Python. Direct them to `winget install Python.Python.3.12` or python.org.

**uv installed but not on PATH.** uv installs to `%USERPROFILE%\.local\bin` by default — sometimes that's missing from PATH. Step 2's probe correctly handles this (treats it as "no uv" and falls back), but the user may benefit from a one-line nudge: "Tip: add `%USERPROFILE%\.local\bin` to PATH to enable uv."

**Already-activated venv in the parent shell.** If the user has another venv activated when invoking this skill, `python -m venv .venv` may inherit the active venv's site-packages. Always use the venv-local interpreter for Step 4 — never rely on the ambient `python`/`pip`.

**`.gitignore` with CRLF/LF mixed line endings.** When appending, use `Add-Content` with the file's existing newline convention. The pattern in Step 5 uses `\s*$` which tolerates both `\r\n` and `\n` line endings.

**pyproject.toml without a `[build-system]` table.** Older `pyproject.toml` files (config-only, not packaging) will fail `pip install -e .`. Detect by reading the file before install; if no `[build-system]` table is present, skip the editable install with a note: "pyproject.toml has no [build-system] — skipping editable install. Add `requirements.txt` for dependency management."

**Existing `.venv/` is corrupted (interpreter missing).** If Step 1 finds `.venv/` but `.venv\Scripts\python.exe` is absent, treat it as broken: report the issue, then ask Recreate / Abort (skip Reuse — it would fail anyway).

## Verification

After the skill completes, the user should be able to:

1. Activate the venv: `.\.venv\Scripts\Activate.ps1` (PowerShell)
2. Confirm isolation: `python -c "import sys; print(sys.prefix)"` returns a path inside `.venv/`
3. Confirm packages: `pip list` shows what was installed (if any)
4. Confirm gitignore: `git status` does not list `.venv/` as untracked

If any of these fail, re-read the skill's status output for the first error — never proceed past a failed step.
