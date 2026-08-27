"""Small data models for a book's highlights and personal notes.

These are plain immutable dataclasses -- the outputs of the sync become plain
Markdown notes, so stay away from heavier abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Highlight:
    """A single highlight (underline) with its chapter and timestamps."""

    bookmark_id: str
    chapter_uid: int
    text: str
    create_time: int
    range: str = ""
    chapter_title: str = ""


@dataclass
class Review:
    """A personal note/review, optionally tied to an underlying highlight."""

    review_id: str
    content: str
    abstract: str = ""
    range: str = ""
    chapter_uid: str = ""
    chapter_title: str = ""
    create_time: int = 0
    star: int = -1


@dataclass
class BookIndex:
    """Summary of one book from /user/notebooks used for change detection."""

    book_id: str
    title: str
    author: str = ""
    total_count: int = 0
    sort: int = 0


@dataclass
class BookContents:
    """Everything extracted for one book in a single sync pass."""

    index: BookIndex
    highlights: list[Highlight] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    bookmark_count: int = 0

    @property
    def latest_ts(self) -> int:
        """Most recent activity in this book (highlights or reviews), else 0."""
        ts = [h.create_time for h in self.highlights] + [r.create_time for r in self.reviews]
        return max(ts, default=0)
