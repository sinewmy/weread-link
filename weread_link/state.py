"""Persistent sync state so runs are incremental and idempotent.

For each book we remember which highlight/review IDs we have already written
to the inbox, so a daily run only emits new content. The state file is plain
JSON and lives outside the vault (in this repo) by default.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class BookState:
    book_id: str
    written_highlights: set[str]
    written_reviews: set[str]
    # Cheap change-detection fingerprint from /user/notebooks: total note count
    # (reviewCount+noteCount+bookmarkCount) and the recent-note timestamp.
    # If these are unchanged, the book is skipped without any detail calls.
    total_count: int = 0
    sort: int = 0


def _load(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_books(path: str) -> dict[str, BookState]:
    raw = _load(path)
    books = raw.get("books", {})
    out: dict[str, BookState] = {}
    for book_id, st in books.items():
        out[book_id] = BookState(
            book_id=book_id,
            written_highlights=set(st.get("highlights", [])),
            written_reviews=set(st.get("reviews", [])),
            total_count=int(st.get("total_count", 0) or 0),
            sort=int(st.get("sort", 0) or 0),
        )
    return out


def save_books(path: str, states: dict[str, BookState]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = {
        "books": {
            bid: {
                "highlights": sorted(st.written_highlights),
                "reviews": sorted(st.written_reviews),
                "total_count": st.total_count,
                "sort": st.sort,
            }
            for bid, st in sorted(states.items())
        }
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
