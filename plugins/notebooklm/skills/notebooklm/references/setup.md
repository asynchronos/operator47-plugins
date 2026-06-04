# Setup & authentication

One-time per machine / per Google account. Everything here uses the **CLI** that
ships with `notebooklm-py`; `nlm.py` then reuses the saved session.

## 1. Install

```bash
# from the skill's scripts/ dir, or pass the full path to requirements.txt
pip install -r requirements.txt          # macOS/Linux
py -m pip install -r requirements.txt     # Windows
```

This installs `notebooklm-py[browser]`. The `[browser]` extra pulls in Playwright,
which `notebooklm login` uses to open a sign-in window. If `login` later complains
about a missing browser, run `python -m playwright install chromium`.

## 2. Log in with a THROWAWAY Google account

> Use a spare account, never your primary Google identity. This is unofficial
> tooling against NotebookLM's internal API — see [legal.md](legal.md).

```bash
notebooklm login
```

Opens a browser; sign in and the session is saved to
`~/.notebooklm/profiles/default/storage_state.json`.

Useful flags:
- `--browser chromium|msedge|chrome` — which browser to drive.
- `--browser-cookies auto|chrome|edge|firefox|safari|brave|arc` — import cookies
  from an already-signed-in browser **without** launching Playwright (handy on
  locked-down machines).
- `--account EMAIL`, `--all-accounts`, `--fresh` (ignore cached profile).
- `--profile-name NAME` (or global `-p/--profile NAME`) — keep multiple identities.

## 3. Verify

```bash
notebooklm auth check --test --json
```

Expect `{"status": "ok", ...}`. `--test` does a live token-fetch (not just a file
check). The JSON reports `storage_exists`, `json_valid`, `cookies_present`,
`sid_cookie`, `token_fetch`, plus the storage path and cookie domains.

Then confirm the library path end-to-end:

```bash
python nlm.py check          # lists your notebooks
```

## Profiles & non-default storage

- Multiple accounts: `notebooklm --profile work login`, then
  `python nlm.py run --profile work ...`.
- Custom storage file: `python nlm.py run --storage /path/to/storage_state.json ...`
  (or set `NOTEBOOKLM_AUTH_JSON`). Resolution order: `--storage` > env > profile default.
- Log out / reset: `notebooklm auth logout` clears the storage and cached profile.

## Windows notes

- Use `py` instead of `python` and `py -m pip` instead of `pip`.
- `nlm.py` already selects the Windows-safe asyncio loop and forces UTF-8 stdout
  (Thai/emoji safe). If you call the library yourself, replicate that — see
  [api.md](api.md#windows-gotcha).
- If Thai still mojibakes in a parent shell, set `$env:PYTHONUTF8=1`.

## When it fails

Almost every runtime error is auth/session expiry. Re-seed:

```bash
notebooklm login
notebooklm auth check --test --json
```

Rate-limit/quota shows up as a rejected generation (`is_rate_limited` /
`USER_DISPLAYABLE_ERROR`), not a crash — wait and retry, or lighten usage. The
free tier is roughly ~50 queries/day; keep batches small.
