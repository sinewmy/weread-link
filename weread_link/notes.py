"""Render a ``BookContents`` into a vault-ready Markdown note.

One note per book, grouped by chapter, with vault-style YAML frontmatter so the
inbox ingestion flow can pick it up unchanged.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .models import BookContents, Review


def _safe_name(text: str) -> str:
    """Lowercase, keep letters/digits/Asian chars, collapse spaces."""
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text, flags=re.UNICODE).strip()
    text = re.sub(r"\s+", "-", text)
    return text[:80] or "untitled"


def _fmt_ts(ts: int) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _frontmatter(contents: BookContents, source: str) -> str:
    idx = contents.index
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        "---\n"
        f"title: {idx.title}\n"
        "type: resource\n"
        "status: inbox\n"
        f"source: {source}\n"
        f"author: {idx.author!r}\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        'tags: [weread, reading]\n'
        "---\n"
    )


def render_note(contents: BookContents, *, source: str = "weread") -> str:
    """Return the full Markdown text for one book."""
    idx = contents.index
    lines: list[str] = []
    lines.append(_frontmatter(contents, source))
    lines.append(f"# {idx.title}")
    if idx.author:
        lines.append(f"**{idx.author}**\n")
    if contents.latest_ts:
        lines.append(f"> 最近笔记：{_fmt_ts(contents.latest_ts)}")
    lines.append("")
    lines.append("## 划线")
    if not contents.highlights:
        lines.append("_无划线_")
    else:
        # group highlights by chapter for readability
        by_chapter: dict[str, list] = {}
        for h in contents.highlights:
            by_chapter.setdefault(h.chapter_title or "(无章节)", []).append(h)
        for chapter, items in by_chapter.items():
            lines.append(f"### {chapter}")
            lines.append("")
            for h in items:
                lines.append(f"> {h.text}")
                lines.append("")
    lines.append("## 个人想法")
    if not contents.reviews:
        lines.append("_无_")
    else:
        for r in contents.reviews:
            if r.abstract:
                lines.append(f"> {r.abstract}")
            lines.append(f"- {r.content}")
            lines.append("")
    lines.append("")
    return "\n".join(lines)


def filename_for(contents: BookContents) -> str:
    """Sanitized filename, one note per book."""
    return f"weread-{_safe_name(contents.index.title)}.md"
