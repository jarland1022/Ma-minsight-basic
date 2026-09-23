"""Detect Community vs Professional packaging."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def read_edition() -> str:
    """Return ``community`` or ``professional``.

    Resolution order:
    1. ``MA_MINSIGHT_EDITION`` env
    2. repo-root ``EDITION`` file
    3. default ``community`` for this repository
    """
    env = os.environ.get("MA_MINSIGHT_EDITION", "").strip().lower()
    if env in {"community", "professional", "pro"}:
        return "community" if env == "community" else "professional"

    edition_file = _repo_root() / "EDITION"
    try:
        raw = edition_file.read_text(encoding="utf-8").strip().lower()
    except OSError:
        raw = ""
    if raw in {"community", "professional", "pro"}:
        return "community" if raw == "community" else "professional"
    return "community"


def is_community_edition() -> bool:
    return read_edition() == "community"
