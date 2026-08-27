# weread-link — WeRead → knowledge-base inbox sync

Pipeline: import highlights from WeRead (official Agent gateway) and write ONE
note per book into the vault inbox (`~/knowledge-base/0-Inbox`).

- Plain Python stdlib only (no third-party runtime deps). Tests use a fake
  client; no network or credentials needed.
- The vault at `~/knowledge-base` is treated as **write-only** here: the sink
  is `0-Inbox/`. Do not touch PARA folders, `Wiki/`, or the vault's own
  `.codex/` state. Those are handled by the vault's independent processes.
- Sync state lives in `weread_state.json` (git-ignored) so runs are
  incremental and idempotent.
- `--full` syncs all existing highlights (used for the initial backfill).
- After a successful non-dry-run sync, the CLI auto-commits and pushes the
  inbox notes to the vault's git remote (`--no-commit` to skip).
- Cron runs the incremental sync at 06:45 on odd days (`1-31/2`), earlier than
  the KB-loop daily pass (Mon–Fri 07:09), so highlights land before processing.
  Every run appends a timestamped entry to `logs/sync.log` (start/done/failed +
  summary); cron captures output too. Check `logs/` to verify runs.

## Running

```bash
python3 -m weread_link --help            # see options
python3 -m weread_link --full --dry-run  # preview initial backfill
python3 -m weread_link --full            # one-time backfill of all book notes
python3 -m weread_link                   # incremental (used by cron)
bash bin/sync.sh                         # same, with .env loading + logging
```

Secrets come from `~/.env` or the process env — never committed.

## Tests

```bash
python3 -m tests.test_sync        # offline, no credentials
```
