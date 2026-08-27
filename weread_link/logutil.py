"""Tiny structured log writer for run summaries.

Writes timestamped, human-readable lines to a log file (and echoes them to
stdout) so every run leaves a checkable record: start/end, success or failure,
and a short summary. Append-only so history is preserved.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write(log_path: str | None, line: str) -> None:
    if log_path:
        try:
            os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            print(f"[log] could not write {log_path}: {exc}")


class RunLogger:
    """Convenience wrapper: log lines with a shared run-id prefix."""

    def __init__(self, log_path: Optional[str] = None) -> None:
        self.log_path = log_path

    def info(self, msg: str) -> None:
        line = f"[{_ts()}] {msg}"
        print(line)
        _write(self.log_path, line)

    def warn(self, msg: str) -> None:
        line = f"[{_ts()}] WARN {msg}"
        print(line)
        _write(self.log_path, line)

    def error(self, msg: str) -> None:
        line = f"[{_ts()}] ERROR {msg}"
        print(line)
        _write(self.log_path, line)
