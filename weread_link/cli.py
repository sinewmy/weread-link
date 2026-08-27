"""Command-line entry point for the WeRead -> inbox sync agent.

Examples:
    python -m weread_link --full --dry-run      # initial: see what a full sync writes
    python -m weread_link --full                # initial full sync (all existing highlights)
    python -m weread_link                       # incremental daily sync
"""

from __future__ import annotations

import argparse
import os

from .client import WeReadClient
from .gitops import commit_and_push
from .sync import SyncEngine


def _api_key() -> str:
    key = os.environ.get("WEREAD_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "WEREAD_API_KEY is not set. "
            "Get your key at https://weread.qq.com/r/weread-skills and export WEREAD_API_KEY=wrk-... "
            "(or set it in a .env file)."
        )
    return key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="weread-link")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full sync (ignore existing state and write every book). Use once initially.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and diff but do not write inbox notes or state.",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Skip the git commit+push that normally follows a successful sync.",
    )
    parser.add_argument(
        "--inbox",
        default=os.environ.get("WEREAD_INBOX_DIR", ""),
        help="Inbox dir (default: $WEREAD_INBOX_DIR or ~/knowledge-base/0-Inbox).",
    )
    parser.add_argument(
        "--state",
        default=os.environ.get("WEREAD_STATE_FILE", ""),
        help="State JSON path (default: $WEREAD_STATE_FILE or ./weread_state.json).",
    )
    args = parser.parse_args(argv)

    inbox = args.inbox or os.path.expanduser("~/knowledge-base/0-Inbox")
    state_path = args.state or "weread_state.json"

    client = WeReadClient(_api_key())
    engine = SyncEngine(client=client, inbox_dir=inbox, state_path=state_path)
    result = engine.run(full=args.full, dry_run=args.dry_run)

    if args.dry_run:
        print(f"[dry-run] books_seen={result.books_seen} new_notes={result.new_notes} "
              f"new_highlights={result.new_highlights} new_reviews={result.new_reviews} "
              f"(nothing written)")
    else:
        print(f"[sync] books_seen={result.books_seen} notes_written={result.new_notes} "
              f"highlights={result.new_highlights} reviews={result.new_reviews}")
        if not args.no_commit:
            commit_and_push(
                inbox,
                message=f"Import WeRead highlights into inbox ({result.new_notes} books)",
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
