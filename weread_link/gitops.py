"""Minimal git commit/push helper for the sync flow.

After a successful (non-dry-run) sync we commit the newly written inbox notes
and push them to the remote so highlights are saved externally. All run via the
system ``git`` binary against whatever repo the inbox lives in.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional


def _find_repo_root(path: str) -> Optional[str]:
    """Walk up from ``path`` until we find a directory containing ``.git``."""
    p = os.path.abspath(path)
    while True:
        if os.path.isdir(os.path.join(p, ".git")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def _current_branch(repo: str) -> str:
    out = subprocess.run(
        ["git", "-C", repo, "branch", "--show-current"],
        capture_output=True,
        text=True,
    )
    return out.stdout.strip() or "main"


def commit_and_push(
    inbox_dir: str,
    *,
    message: str,
    remote: str = "origin",
    push: bool = True,
) -> bool:
    """Stage the inbox subdir, commit if there are changes, and optionally push.

    Returns True if anything was committed; False if there was nothing to
    commit, no repo was found, or a step failed (errors are printed, not
    raised, so a git hiccup never loses the sync itself).
    """
    repo = _find_repo_root(inbox_dir)
    if repo is None:
        print(f"[git] no git repo found for {inbox_dir} - skipping auto commit")
        return False
    rel_inbox = os.path.relpath(inbox_dir, repo)

    stage = subprocess.run(
        ["git", "-C", repo, "add", "--", rel_inbox],
        capture_output=True,
        text=True,
    )
    if stage.returncode != 0:
        print(f"[git] add failed: {stage.stderr.strip() or stage.stdout.strip()}")
        return False

    quiet = subprocess.run(["git", "-C", repo, "diff", "--cached", "--quiet"])
    if quiet.returncode == 0:
        print("[git] no changes to commit")
        return False

    commit = subprocess.run(
        ["git", "-C", repo, "commit", "-m", message],
        capture_output=True,
        text=True,
    )
    if commit.returncode != 0:
        print(f"[git] commit failed: {commit.stderr.strip() or commit.stdout.strip()}")
        return False
    print(f"[git] committed: {commit.stdout.strip().splitlines()[-1]}")

    if push:
        branch = _current_branch(repo)
        push_run = subprocess.run(
            ["git", "-C", repo, "push", remote, branch],
            capture_output=True,
            text=True,
        )
        if push_run.returncode != 0:
            # Likely "! [rejected] ... (fetch first)": the remote has commits
            # we do not have locally (e.g. the KB-loop agent pushed first).
            # Merge the remote in, then push once more rather than leaving the
            # commit stranded locally. A merge never overwrites local work; a
            # conflict aborts the pull and we fall through to report failure.
            pull = subprocess.run(
                ["git", "-C", repo, "pull", "--no-rebase", remote, branch],
                capture_output=True,
                text=True,
            )
            if pull.returncode == 0:
                push_run = subprocess.run(
                    ["git", "-C", repo, "push", remote, branch],
                    capture_output=True,
                    text=True,
                )
            if push_run.returncode != 0:
                print(
                    f"[git] push failed: {push_run.stderr.strip() or push_run.stdout.strip()} "
                    "(commit is saved locally)"
                )
                return False
        print(f"[git] pushed to {remote}/{branch}")
    return True
