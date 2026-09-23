"""Wazuh alert document → NormalizedAlert mapping."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.datetime_utils import as_naive_utc, utc_now
from app.ingestion.category import map_wazuh_category
from app.ingestion.fingerprint import compute_fingerprint
from app.ingestion.schemas.normalized_alert import NormalizedAlert
from app.ingestion.severity import map_wazuh_level


def _first_str(*values: Any) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def parse_occurred_at(raw: dict[str, Any]) -> datetime:
    value = raw.get("timestamp") or raw.get("@timestamp")
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        return as_naive_utc(value)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return utc_now()
    return as_naive_utc(parsed)


def extract_request_url(
    raw: dict[str, Any],
    *,
    normalized_fields: dict[str, Any] | None = None,
) -> str | None:
    """Extract HTTP request path/URL from Wazuh/nginx alert payloads."""
    if normalized_fields:
        cached = _first_str(normalized_fields.get("request_url"))
        if cached:
            return cached

    data = raw.get("data") or {}
    url = _first_str(
        data.get("url"),
        data.get("request_uri"),
        data.get("uri"),
        data.get("path"),
    )
    if url:
        return url

    full_log = raw.get("full_log")
    if isinstance(full_log, str):
        for token in full_log.split():
            if token.startswith("/") and " " not in token:
                return token.rstrip("?")
    return None


def extract_source_alert_id(raw: dict[str, Any]) -> str:
    alert_id = _first_str(raw.get("_id"), raw.get("id"))
    if alert_id:
        return alert_id
    ts = parse_occurred_at(raw).isoformat()
    rule_id = _nested(raw, "rule", "id") or "unknown"
    return f"{rule_id}:{ts}"


def map_wazuh_alert(
    raw: dict[str, Any],
    *,
    data_source_id: UUID,
    data_source_name: str,
) -> NormalizedAlert:
    rule = raw.get("rule") or {}
    agent = raw.get("agent") or {}
    data = raw.get("data") or {}
    syscheck = raw.get("syscheck") or {}
    process = data.get("process") if isinstance(data.get("process"), dict) else {}

    rule_id = _first_str(rule.get("id"))
    rule_name = _first_str(rule.get("description"))
    rule_level = rule.get("level")
    groups = rule.get("groups") if isinstance(rule.get("groups"), list) else []
    alert_category = map_wazuh_category(groups)

    src_ip = _first_str(data.get("srcip"), data.get("src_ip"), agent.get("ip"))
    dst_ip = _first_str(data.get("dstip"), data.get("dst_ip"))
    user_name = _first_str(data.get("dstuser"), data.get("uid"), data.get("srcuser"))
    host_name = _first_str(agent.get("name"))
    process_name = _first_str(process.get("name"), data.get("process_name"))
    process_cmdline = _first_str(process.get("cmd"), data.get("command"))
    file_hash = _first_str(syscheck.get("sha256_after"), data.get("hash"))

    src_port = data.get("srcport") or data.get("src_port")
    dst_port = data.get("dstport") or data.get("dst_port")

    request_url = extract_request_url(raw)

    normalized_fields: dict[str, Any] = {
        "rule_groups": groups,
        "agent_id": agent.get("id"),
        "agent_ip": agent.get("ip"),
        "decoder_name": raw.get("decoder", {}).get("name") if isinstance(raw.get("decoder"), dict) else None,
        "location": raw.get("location"),
        "geo_location": raw.get("GeoLocation") or raw.get("geoLocation"),
        "full_log_excerpt": (raw.get("full_log") or "")[:500] or None,
        "request_url": request_url,
        "data_source_id": str(data_source_id),
    }
    normalized_fields = {k: v for k, v in normalized_fields.items() if v is not None}

    fingerprint = compute_fingerprint(
        data_source_name=data_source_name,
        rule_id=rule_id,
        src_ip=src_ip,
        dst_ip=dst_ip,
        user_name=user_name,
        host_name=host_name,
        alert_category=alert_category,
    )

    return NormalizedAlert(
        source_alert_id=extract_source_alert_id(raw),
        fingerprint=fingerprint,
        rule_id=rule_id,
        rule_name=rule_name,
        severity=map_wazuh_level(rule_level),
        severity_raw=str(rule_level) if rule_level is not None else None,
        occurred_at=parse_occurred_at(raw),
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=int(src_port) if src_port is not None else None,
        dst_port=int(dst_port) if dst_port is not None else None,
        user_name=user_name,
        host_name=host_name,
        process_name=process_name,
        process_cmdline=process_cmdline,
        file_hash=file_hash,
        alert_category=alert_category,
        normalized_fields=normalized_fields,
        raw_data=raw,
    )
