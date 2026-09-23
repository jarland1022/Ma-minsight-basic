"""Parse inbound IM replies."""

from __future__ import annotations

import re

EVT_TAG_PATTERN = re.compile(r"#EVT-([0-9a-fA-F]{8})")


def extract_short_code(content: str) -> str | None:
    match = EVT_TAG_PATTERN.search(content)
    if match is None:
        return None
    return match.group(1).lower()


def parse_reply_content(raw_content: str) -> tuple[str | None, str]:
    """Return (short_code, content_without_tag_line). Structured parsing reserved for phase 6+."""
    short_code = extract_short_code(raw_content)
    cleaned = EVT_TAG_PATTERN.sub("", raw_content).strip()
    return short_code, cleaned or raw_content.strip()
