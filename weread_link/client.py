"""Read-only client for the official WeRead Agent API gateway.

No dependency on third-party packages; uses the standard library ``urllib``.

Reference: the official "WeRead Skill" API contract published by Tencent:
  - POST https://i.weread.qq.com/api/agent/gateway
  - Header: ``Authorization: Bearer $WEREAD_API_KEY``
  - Body: JSON with ``api_name``, ``skill_version``, and flat business params.

See the sibling ``notes.md`` contract for pagination and field rules. This
module intentionally knows nothing about the knowledge base -- it only talks
to WeRead.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

GATEWAY_URL = "https://i.weread.qq.com/api/agent/gateway"
DEFAULT_SKILL_VERSION = "1.0.4"


class WeReadError(RuntimeError):
    """Raised when the gateway reports a non-zero errcode (or transport fails)."""


class WeReadClient:
    """Thin typed wrapper over the WeRead Agent gateway.

    Public methods map 1:1 to gateway endpoints and keep pagination helpers
    flat. Callers should treat responses as opaque ``dict``s.
    """

    def __init__(
        self,
        api_key: str,
        *,
        skill_version: str = DEFAULT_SKILL_VERSION,
        timeout: float = 30.0,
        max_retries: int = 5,
        retry_delay: float = 5.0,
    ) -> None:
        self.api_key = api_key
        self.skill_version = skill_version
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def request(self, api_name: str, **params: Any) -> dict[str, Any]:
        """POST to the gateway with ``api_name`` and flat ``params``."""
        for attempt in range(self.max_retries):
            try:
                return self._request_once(api_name, params)
            except WeReadError as exc:
                if "频率超限" in str(exc) or "轮换" in str(exc):
                    wait = self.retry_delay * (2**attempt)
                    print(f"[rate-limit] {api_name} retry in {wait:.0f}s ({attempt+1}/{self.max_retries})")
                    time.sleep(wait)
                    continue
                raise
        raise WeReadError(f"{api_name} exhausted retries")

    def _request_once(self, api_name: str, params: dict[str, Any]) -> dict[str, Any]:
        body = {"api_name": api_name, "skill_version": self.skill_version, **params}
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            GATEWAY_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "weread-link/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            # The gateway returns HTTP 499 for business errors (e.g. rate limit).
            raise WeReadError(f"{api_name} HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
        except urllib.error.URLError as exc:
            raise WeReadError(f"gateway request failed: {exc}") from exc

        data = json.loads(raw)
        if data.get("errcode"):
            raise WeReadError(
                f"{api_name} errcode={data['errcode']}: {data.get('errmsg', data.get('message', ''))}"
            )
        return data

    # -- paginated helpers ------------------------------------------------
    def all_notebooks(self) -> list[dict[str, Any]]:
        """Fetch every notebook entry (books with notes) across all pages."""
        books: list[dict[str, Any]] = []
        last_sort = None
        while True:
            params: dict[str, Any] = {"count": 100}
            if last_sort is not None:
                params["lastSort"] = last_sort
            data = self.request("/user/notebooks", **params)
            page_books = data.get("books") or []
            books.extend(page_books)
            if not data.get("hasMore") or not page_books:
                break
            last_sort = page_books[-1].get("sort")
        return books

    def bookmarklist(self, book_id: str) -> dict[str, Any]:
        """All highlights (``updated``) plus chapter metadata for one book."""
        return self.request("/book/bookmarklist", bookId=book_id)

    def my_reviews(self, book_id: str) -> list[dict[str, Any]]:
        """All personal thoughts/reviews (paginated) for one book."""
        reviews: list[dict[str, Any]] = []
        synckey = 0
        while True:
            data = self.request("/review/list/mine", bookid=book_id, synckey=synckey, count=20)
            page = data.get("reviews") or []
            reviews.extend(page)
            if not data.get("hasMore") or not page:
                break
            synckey = int(data.get("synckey") or 0)
        return reviews
