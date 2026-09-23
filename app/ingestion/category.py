"""Alert category mapping from source-specific rule metadata."""

from __future__ import annotations

import re

WAZUH_GROUP_TO_CATEGORY: dict[str, str] = {
    "authentication_failed": "brute_force",
    "authentication_success": "login_anomaly",
    "authentication": "authentication",
    "syscheck": "file_integrity",
    "web": "web_attack",
    "ids": "network_intrusion",
    "firewall": "firewall",
    "syslog": "syslog",
    "windows": "windows_event",
    "ossec": "host_anomaly",
    "malware": "malware",
    "pci_dss": "compliance",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "uncategorized"


def map_wazuh_category(groups: list[str] | None) -> str:
    if not groups:
        return "uncategorized"
    for group in groups:
        mapped = WAZUH_GROUP_TO_CATEGORY.get(group)
        if mapped:
            return mapped
    return slugify(groups[0])
