# weread-link

Sync highlights from your 微信读书 (WeRead) account into your knowledge-base
inbox (`~/knowledge-base/0-Inbox`) as one Markdown note per book — so your
existing vault ingestion flow can pick them up.

- 100% deterministic: plain Python stdlib, no LLM, no third-party runtime deps.
- Uses the **official WeRead Skill Agent API** (`i.weread.qq.com`, `wrk-...` key).
- Writes **one note per book**, grouped into 划线 (highlights) and 个人想法
  (personal notes / reviews), with vault-style YAML frontmatter.
- Writes to **`~/knowledge-base/0-Inbox/` only**. It never touches PARA
  folders, `Wiki/`, or the vault's own `.codex/` state.
- Incremental and idempotent: sync progress is tracked in a local
  `weread_state.json` so day-to-day runs only emit new/changed highlights.
- After each successful non-dry-run sync it auto-commits and pushes the inbox
  notes to the vault's git remote, so highlights are saved as you go. Pass
  `--no-commit` to skip this.

## How the sync & state work

**State** lives in `weread_state.json` (in this repo, git-ignored). For each
book it records the highlight/review *IDs* already written to the inbox, plus a
cheap change-detection fingerprint from the notebooks overview (the total note
count and the recent-note timestamp).

- **Incremental sync (default, `python3 -m weread_link`)** — first fetches the
  lightweight *overview* (one paginated list of books with their counts and
  timestamps). For each book whose fingerprint changed (new/edited/deleted
  notes), it pulls the full details and writes any genuinely-new highlights/
  reviews. **Unchanged books are skipped entirely, with no per-book API
  calls** — so a run where nothing changed costs only the overview request,
  not ~2 calls per book.
- **Full sync (`--full`)** — starts from **empty state** (it does *not* reuse
  the saved file), so it re-writes the full note for every book with
  highlights. Because the notes are overwritten from scratch (not appended),
  running `--full` is safe and simply reproduces the complete current content.

> `--full` ignores prior state on purpose: it's for backfills / starting over.
> Once you're set up, run without `--full` for fast daily increments. The CLI
> reports how many books were `skipped` each run.

## Step 1 — Get your WeRead API key
1. Open the WeRead app (微信读书) on your phone.
2. Go to **我的 → 设置 → 微信读书 Skill** (功能/API) and scan the QR code to
   get a key that looks like `wrk-xxxxxxxx`.
   - Alternative: open `https://weread.qq.com/r/weread-skills` in the app.
3. Copy the key somewhere safe. It is tied to your account.

## Step 2 — Configure the repo

The project lives at `/home/stephen/codex-projects/weread-link`.

```bash
cd /home/stephen/codex-projects/weread-link
cp .env.example .env
```

Edit `.env` and set your key:

```bash
WEREAD_API_KEY=wrk-xxxxxxxx
```

Leave the other lines as-is (they point to the right places on this machine):
- `WEREAD_INBOX_DIR=/home/stephen/knowledge-base/0-Inbox`
- `WEREAD_STATE_FILE=/home/stephen/codex-projects/weread-link/weread_state.json`

> `.env` is git-ignored, so your key is never committed.

## Step 3 — Sanity-check it runs

```bash
python3 -m tests.test_sync        # offline tests, no key/network needed
python3 -m weread_link --help     # confirm CLI options
```

## Step 4 — Preview the initial backfill

Shows what the first full sync would write, without touching your inbox:

```bash
python3 -m weread_link --full --dry-run
```

Review the printed `books_seen` / `new_highlights` / `new_reviews` counts.
Check a couple of the generated notes (they appear under
`~/knowledge-base/0-Inbox/`) to make sure the format looks right.

## Step 5 — Run the full backfill (one time)

Writes a note for every book that has highlights/notes in your WeRead account:

```bash
python3 -m weread_link --full
```

If you have a lot of books this may take a while (one API round-trip per book).
Re-run if interrupted — it picks up where it left off.

## Step 6 — The periodic (incremental) job

Each run fetches only books that gained new highlights/notes since the last
run, then auto-commits + pushes any new inbox notes to the vault's git remote.

**Installed cron schedule:**

```cron
45 6 1-31/2 * * /home/stephen/codex-projects/weread-link/bin/sync.sh >> /home/stephen/codex-projects/weread-link/logs/cron.log 2>&1
```

This runs at **06:45 on odd days** (every 2nd day) — intentionally **earlier
than the KB-loop daily inbox pass** (Mon–Fri 07:09) so fresh highlights land in
`0-Inbox/` before the vault processes them. `bin/sync.sh` loads `.env` and runs
the incremental sync.

> The `1-31/2` day-of-month step means every other calendar day; at month
> boundaries you can get a 1-day gap (day 31 → next month's 1st) or a 3-day gap
> (Feb 27 → Mar 1). If you want a strict 48-hour cadence independent of the
> calendar, replace this entry with a fixed-interval scheduler.

**Manual / on-demand run:**

```bash
cd /home/stephen/codex-projects/weread-link
source .env
python3 -m weread_link
```

**Logging:** every run appends a timestamped entry to `logs/sync.log` — a
`started` line, then a `done ...` summary (`books_seen`, `notes_written`,
`highlights`, `reviews`, `skipped`) or an `ERROR ... FAILED` line. The cron
wrapper also captures stdio to `logs/cron.log`. Use the log to verify past runs.

> ⚠️ If nothing happens when the cron fires, grant Full Disk Access (macOS) to
> allow reading files under `~/knowledge-base`.

## Step 7 — Let it ride

Each successful run drops new, one-per-book notes into
`~/knowledge-base/0-Inbox/`. Your normal vault ingestion skill (`ingest-inbox`)
processes the inbox as usual. This agent is independent — it never invokes or
blocks the knowledge-base's own orchestrator processes.

## What a note looks like

`~/knowledge-base/0-Inbox/weread-<slug>.md`

```markdown
---
title: <book title>
type: resource
status: inbox
source: weread
author: <author>
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [weread, reading]
---

# <book title>

## 划线
### <chapter>
> <highlighted text>

## 个人想法
- <your thought / review>
```

## Notes & limits

- **Bookmarks** (阅读位置书签) are not exported as content (only counted) —
  that's an upstream WeRead API limitation, not a bug.
- The API can be rate-limited; if a run errors partway, it is safe to re-run and
  it will continue incrementally.
- If the API contract changes (new `skill_version`), the gateway returns
  `upgrade_info` — update `DEFAULT_SKILL_VERSION` in `weread_link/client.py`.

## Troubleshooting

- **`WEREAD_API_KEY is not set.`** — `.env` isn't loaded or the var is empty.
  Double-check you ran via `bin/sync.sh` or `source .env`.
- **Non-zero `errcode` in output** — the API failed (e.g. auth or a changed
  request). Use `--dry-run` to debug without writing anything.
