"""Default entity profiles and on-duty knowledge for production seeding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.db.enums import AssetCriticality


@dataclass(frozen=True)
class AssetRow:
    public_ip: str
    private_ip: str
    host: str
    display_name: str
    owner_team: str = "业务"
    criticality: AssetCriticality = AssetCriticality.HIGH
    is_jump_host: bool = False
    extra_metadata: dict[str, Any] = field(default_factory=dict)


DEFAULT_ASSETS: tuple[AssetRow, ...] = (
    AssetRow("39.108.213.241", "172.18.241.79", "web-server-01", "优悦商城"),
    AssetRow("47.112.170.136", "172.18.241.78", "web-server-02", "权益商城"),
    AssetRow("120.77.67.235", "172.18.241.75", "web-server-03", "官网"),
    AssetRow("120.25.226.229", "172.18.241.74", "web-server-04", "建行运营端"),
    AssetRow(
        "120.79.165.121",
        "172.18.131.89",
        "firewall",
        "防火墙和IPS",
        owner_team="安全",
        criticality=AssetCriticality.CRITICAL,
        extra_metadata={"role": "firewall_ips"},
    ),
    AssetRow(
        "47.119.118.34",
        "172.18.131.88",
        "waf",
        "WAF/堡垒机/SIEM",
        owner_team="安全",
        criticality=AssetCriticality.CRITICAL,
        is_jump_host=True,
        extra_metadata={"role": "waf_bastion_siem"},
    ),
)

SCANNER_IP = "183.6.90.91"
SCANNER_NOTE = "该 IP 为等保测评漏洞扫描器，非攻击 IP"
