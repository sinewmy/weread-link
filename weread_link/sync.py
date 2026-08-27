"""Orchestrate a single sync: fetch, diff against state, render, write.

This is the ingest pipe: it talks to WeRead, writes new notes into the vault
inbox, and updates local sync state. It is deliberately independent of the
vault's own orchestrator processes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .client import WeReadClient
from .models import BookContents, BookIndex, Highlight, Review
from .notes import filename_for, render_note
from .state import BookState, load_books, save_books


@dataclass
class SyncResult:
    """High-level summary of a sync pass."""

    books_seen: int = 0
    skipped: int = 0
    new_notes: int = 0
    new_highlights: int = 0
    new_reviews: int = 0


class SyncEngine:
    def __init__(
        self,
        client: WeReadClient,
        inbox_dir: str,
        state_path: str,
    ) -> None:
        self.client = client
        self.inbox_dir = inbox_dir
        self.state_path = state_path

    def _chapter_index(self, data: dict) -> dict[int, str]:
        out: dict[int, str] = {}
        for ch in data.get("chapters") or []:
            out[int(ch.get("chapterUid") or 0)] = ch.get("title") or ""
        return out

    def _extract(self, book: dict) -> BookContents:
        """Pull highlights + reviews for one book index entry."""
        book_id = book["bookId"]
        idx = BookIndex(
            book_id=book_id,
            title=(book.get("book") or {}).get("title") or book_id,
            author=(book.get("book") or {}).get("author") or "",
            total_count=sum(
                int(book.get(k) or 0)
                for k in ("reviewCount", "noteCount", "bookmarkCount")
            ),
            sort=int(book.get("sort") or 0),
        )
        bm = self.client.bookmarklist(book_id)
        chunks = self._chapter_index(bm)
        highlights: list[Highlight] = []
        for item in bm.get("updated") or []:
            cu = int(item.get("chapterUid") or 0)
            highlights.append(
                Highlight(
                    bookmark_id=str(item.get("bookmarkId") or ""),
                    chapter_uid=cu,
                    text=item.get("markText") or "",
                    create_time=int(item.get("createTime") or 0),
                    range=str(item.get("range") or ""),
                    chapter_title=chunks.get(cu, ""),
                )
            )
        reviews: list[Review] = []
        for item in self.client.my_reviews(book_id):
            rev = item.get("review") or {}
            cu = str(rev.get("chapterUid") or "")
            reviews.append(
                Review(
                    review_id=str(rev.get("reviewId") or ""),
                    content=rev.get("content") or "",
                    abstract=rev.get("abstract") or "",
                    range=str(rev.get("range") or ""),
                    chapter_uid=cu,
                    chapter_title=rev.get("chapterName") or chunks.get(int(cu) if cu.isdigit() else 0, ""),
                    create_time=int(rev.get("createTime") or 0),
                    star=int(rev.get("star") or -1),
                )
            )
        return BookContents(
            index=idx,
            highlights=highlights,
            reviews=reviews,
            bookmark_count=int(book.get("bookmarkCount") or 0),
        )

    @staticmethod
    def _fingerprint(book: dict) -> tuple[int, int]:
        """Cheap change-detection fingerprint from the notebooks overview.

        Returns (total_note_count, recent_sort_ts). If both are unchanged for a
        book we already synced, the per-book detail endpoints can be skipped.
        """
        total = sum(int(book.get(k) or 0) for k in ("reviewCount", "noteCount", "bookmarkCount"))
        return total, int(book.get("sort") or 0)

    def run(self, *, full: bool = False, dry_run: bool = False) -> SyncResult:
        os.makedirs(self.inbox_dir, exist_ok=True)
        states = {} if full else load_books(self.state_path)
        result = SyncResult()
        for book in self.client.all_notebooks():
            book_id = book.get("bookId")
            if not book_id:
                continue
            result.books_seen += 1
            total, sort = SyncEngine._fingerprint(book)

            # Cheap change detection: if a known book's counts/timestamp are
            # unchanged, skip it without any per-book detail API calls.
            if not full and book_id in states:
                st = states[book_id]
                if st.total_count == total and st.sort == sort:
                    result.skipped += 1
                    continue
            else:
                st = states.setdefault(
                    book_id,
                    BookState(book_id=book_id, written_highlights=set(), written_reviews=set()),
                )

            contents = self._extract(book)
            new_h = [h for h in contents.highlights if h.bookmark_id not in st.written_highlights]
            new_r = [r for r in contents.reviews if r.review_id not in st.written_reviews]
            # keep state cheap-indicators fresh even if detail diff found nothing
            st.total_count = contents.index.total_count
            st.sort = contents.index.sort
            if not new_h and not new_r:
                # counts moved (e.g. edit) but no genuinely-new IDs -> nothing to write
                continue
            result.new_highlights += len(new_h)
            result.new_reviews += len(new_r)
            contents = BookContents(
                index=contents.index,
                highlights=new_h,
                reviews=new_r,
                bookmark_count=contents.bookmark_count,
            )
            if not dry_run:
                os.makedirs(self.inbox_dir, exist_ok=True)
                fpath = os.path.join(self.inbox_dir, filename_for(contents))
                with open(fpath, "w", encoding="utf-8") as fh:
                    fh.write(render_note(contents))
                result.new_notes += 1
                st.written_highlights.update(h.bookmark_id for h in new_h)
                st.written_reviews.update(r.review_id for r in new_r)
        if not dry_run:
            save_books(self.state_path, states)
        return result
