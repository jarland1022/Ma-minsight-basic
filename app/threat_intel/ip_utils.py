"""IP helpers for threat intel sync."""

from __future__ import annotations

import ipaddress


def normalize_ip(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return None


def is_public_ip(value: str) -> bool:
    normalized = normalize_ip(value)
    if normalized is None:
        return False
    addr = ipaddress.ip_address(normalized)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
    )
