"""Offline test of the sync engine using a fake gateway client.

Runs without credentials or network.
"""

from __future__ import annotations

from pathlib import Path

from weread_link.gitops import _find_repo_root
from weread_link.sync import SyncEngine


class FakeClient:
    """Stand-in for WeReadClient driven by in-memory fixtures."""

    def __init__(self, notebook: dict, bookmark: dict, reviews: list[dict]) -> None:
        self._notebook = notebook
        self._bookmark = bookmark
        self._reviews = reviews

    def all_notebooks(self):
        return [self._notebook]

    def bookmarklist(self, book_id):
        return self._bookmark

    def my_reviews(self, book_id):
        return self._reviews


def _note_path(inbox: Path, title: str) -> Path:
    return inbox / f"weread-{title}.md"


def test_full_then_incremental(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    state_path = str(tmp_path / "state.json")

    fixture = {
        "bookId": "B1",
        "book": {"title": "连 接", "author": "张三"},
        "reviewCount": 1,
        "noteCount": 2,
        "bookmarkCount": 1,
        "sort": 100,
    }
    bookmark = {
        "chapters": [{"chapterUid": 11, "title": "第一章"}],
        "updated": [
            {
                "bookmarkId": "H1",
                "chapterUid": 11,
                "markText": "Hello highlight one.",
                "createTime": 1700000000,
                "range": "1-2",
            },
            {
                "bookmarkId": "H2",
                "chapterUid": 11,
                "markText": "Second highlight.",
                "createTime": 1700000100,
                "range": "3-4",
            },
        ],
    }
    reviews = [
        {"review": {"reviewId": "R1", "content": "My thought here.", "abstract": "Hello highlight one."}}
    ]

    box = FakeClient(fixture, bookmark, reviews)
    engine = SyncEngine(box, str(inbox), state_path=state_path)

    # Full sync writes the note
    res = engine.run(full=True)
    assert res.books_seen == 1
    assert res.new_notes == 1
    assert res.new_highlights == 2
    assert res.new_reviews == 1
    assert (inbox / "weread-连-接.md").exists()

    # Incremental with no change: nothing new
    engine2 = SyncEngine(box, str(inbox), state_path=state_path)
    res2 = engine2.run()
    assert res2.new_notes == 0

    # A new highlight arrives -> incremental pick it up, only that one
    bookmark2 = {"updated": bookmark["updated"], "chapters": bookmark["chapters"]}
    bookmark2["updated"].append(
        {"bookmarkId": "H3", "chapterUid": 11, "markText": "Third highlight.", "createTime": 1700000200, "range": "5"}
    )
    box2 = FakeClient(fixture, bookmark2, reviews)
    res3 = SyncEngine(box2, str(inbox), state_path=state_path).run()
    assert res3.new_highlights == 1
    assert res3.new_reviews == 0

    note_txt = (inbox / "weread-连-接.md").read_text(encoding="utf-8")
    assert "Third highlight." in note_txt


def test_notes_render_frontmatter(tmp_path: Path) -> None:
    from weread_link.models import BookContents, BookIndex, Highlight
    from weread_link.notes import render_note

    contents = BookContents(
        index=BookIndex(book_id="B9", title="测试书", author="作者"),
        highlights=[Highlight(bookmark_id="H1", chapter_uid=11, text="划线", create_time=1)],
    )
    text = render_note(contents)
    assert "title: 测试书" in text
    assert "type: resource" in text
    assert "> 划线" in text


def test_git_repo_root_detection(tmp_path: Path) -> None:
    repo = tmp_path / "vault"
    (repo / ".git").mkdir(parents=True)
    sub = repo / "0-Inbox"
    sub.mkdir()
    assert _find_repo_root(str(sub)) == str(repo)
    # nearest repo is found even if an ancestor is also a repo
    nested = repo / "0-Inbox" / "sub" / "deeper"
    nested.mkdir(parents=True)
    assert _find_repo_root(str(nested)) == str(repo)


def test_commit_and_push_integration(tmp_path: Path) -> None:
    """commit_and_push stages and commits a new note in a real git repo."""
    import subprocess

    repo = tmp_path / "vault"
    repo.mkdir(exist_ok=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)

    inbox = repo / "0-Inbox"
    inbox.mkdir(exist_ok=True)
    (inbox / "note.md").write_text("hi", encoding="utf-8")

    from weread_link.gitops import commit_and_push

    ok = commit_and_push(str(inbox), message="test commit", push=False)
    assert ok is True
    assert (repo / ".git").exists()
    log = subprocess.run(["git", "-C", str(repo), "log", "--oneline"], capture_output=True, text=True)
    assert "test commit" in log.stdout

    # Second call: no changes -> False
    assert commit_and_push(str(inbox), message="again", push=False) is False


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    td = Path(tempfile.mkdtemp())
    test_full_then_incremental(td)
    test_notes_render_frontmatter(td)
    test_git_repo_root_detection(td)
    test_commit_and_push_integration(td)
    print("OK")
