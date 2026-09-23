"""Rank Wazuh rules by human-confirmed false positives.

Disposition confirm/reject stays on disposition_records. This module reads those
decisions together with the latest investigation verdict and the alerts' rule id.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.db.enums import DispositionStatus, InvestigationVerdict
from app.models.defense_assets import DispositionRecord
from app.models.ingestion import Alert
from app.models.investigation import Event, EventAlert, Investigation, InvestigationConclusion

FP = InvestigationVerdict.LIKELY_FALSE_POSITIVE.value
ATTACK = InvestigationVerdict.ATTACK_CONFIRMED.value


def aggregate_rule_noise(samples: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]:
    """Roll event-level samples into ranked rules.

    A sample is one event attributed to one rule:
    rule_id, rule_name, event_id, verdict, alert_count, human_confirmed, human_rejected.
    """
    grouped: dict[str, dict[str, Any]] = {}
    for sample in samples:
        rule_id = (sample.get("rule_id") or "").strip() or None
        rule_name = (sample.get("rule_name") or "").strip() or None
        rule_key = rule_id or rule_name
        if not rule_key:
            continue
        bucket = grouped.get(rule_key)
        if bucket is None:
            bucket = {
                "rule_id": rule_id,
                "rule_name": rule_name,
                "alert_count": 0,
                "event_ids": set(),
                "fp_events": 0,
                "attack_events": 0,
                "human_confirmed_fp": 0,
                "human_rejected_fp": 0,
                "human_confirmed_attack": 0,
                "human_rejected_attack": 0,
            }
            grouped[rule_key] = bucket
        if rule_name and not bucket["rule_name"]:
            bucket["rule_name"] = rule_name
        event_id = str(sample["event_id"])
        if event_id in bucket["event_ids"]:
            bucket["alert_count"] += int(sample.get("alert_count") or 0)
            continue
        bucket["event_ids"].add(event_id)
        bucket["alert_count"] += int(sample.get("alert_count") or 0)
        verdict = str(sample.get("verdict") or "")
        confirmed = bool(sample.get("human_confirmed"))
        rejected = bool(sample.get("human_rejected")) and not confirmed
        if verdict == FP:
            bucket["fp_events"] += 1
            if confirmed:
                bucket["human_confirmed_fp"] += 1
            elif rejected:
                bucket["human_rejected_fp"] += 1
        elif verdict == ATTACK:
            bucket["attack_events"] += 1
            if confirmed:
                bucket["human_confirmed_attack"] += 1
            elif rejected:
                bucket["human_rejected_attack"] += 1

    ranked: list[dict[str, Any]] = []
    for bucket in grouped.values():
        event_count = len(bucket["event_ids"])
        if event_count == 0:
            continue
        suggestion = _suggestion(bucket, event_count)
        if not suggestion:
            continue
        fp_ratio = bucket["fp_events"] / event_count
        ranked.append(
            {
                "rule_id": bucket["rule_id"],
                "rule_name": bucket["rule_name"] or bucket["rule_id"],
                "alert_count": bucket["alert_count"],
                "event_count": event_count,
                "fp_events": bucket["fp_events"],
                "attack_events": bucket["attack_events"],
                "human_confirmed_fp": bucket["human_confirmed_fp"],
                "human_rejected_fp": bucket["human_rejected_fp"],
                "human_confirmed_attack": bucket["human_confirmed_attack"],
                "human_rejected_attack": bucket["human_rejected_attack"],
                "fp_ratio": round(fp_ratio, 2),
                "suggestion": suggestion,
            }
        )
    ranked.sort(
        key=lambda row: (
            row["human_confirmed_fp"],
            row["fp_events"],
            row["alert_count"],
        ),
        reverse=True,
    )
    return ranked[:limit]


def _suggestion(bucket: dict[str, Any], event_count: int) -> str | None:
    name = bucket["rule_name"] or bucket["rule_id"] or "该规则"
    if bucket["human_confirmed_fp"] >= 1 and bucket["human_confirmed_fp"] >= bucket["human_confirmed_attack"]:
        return (
            f"人工已确认 {bucket['human_confirmed_fp']} 起按误报处置，"
            f"建议在 Wazuh 收紧规则「{name}」或为已知业务增加例外。"
        )
    if (
        bucket["human_confirmed_fp"] == 0
        and bucket["fp_events"] >= 2
        and bucket["fp_events"] > bucket["attack_events"]
        and bucket["fp_events"] / event_count >= 0.5
    ):
        return "AI 多次判为误报，尚无人工确认。建议抽查事件后再决定是否修改 Wazuh 规则。"
    return None


async def list_noisy_rules(
    session: AsyncSession,
    *,
    days: int = 30,
    limit: int = 20,
) -> dict[str, Any]:
    since = utc_now() - timedelta(days=days)
    latest = (
        select(Investigation.event_id, Investigation.id.label("investigation_id"))
        .where(Investigation.finished_at.is_not(None), Investigation.finished_at >= since)
        .distinct(Investigation.event_id)
        .order_by(Investigation.event_id, Investigation.started_at.desc())
        .subquery()
    )
    stmt = (
        select(
            Alert.id,
            Alert.rule_id,
            Alert.rule_name,
            Event.id,
            InvestigationConclusion.verdict,
            DispositionRecord.status,
        )
        .join(EventAlert, EventAlert.alert_id == Alert.id)
        .join(Event, Event.id == EventAlert.event_id)
        .join(latest, latest.c.event_id == Event.id)
        .join(
            InvestigationConclusion,
            InvestigationConclusion.investigation_id == latest.c.investigation_id,
        )
        .outerjoin(
            DispositionRecord,
            DispositionRecord.investigation_id == latest.c.investigation_id,
        )
    )
    rows = (await session.execute(stmt)).all()

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for alert_id, rule_id, rule_name, event_id, verdict, disp_status in rows:
        key_rule = (rule_id or "").strip() or (rule_name or "").strip()
        if not key_rule:
            continue
        key = (key_rule, str(event_id))
        item = merged.get(key)
        if item is None:
            item = {
                "rule_id": (rule_id or "").strip() or None,
                "rule_name": (rule_name or "").strip() or None,
                "event_id": str(event_id),
                "verdict": verdict.value if hasattr(verdict, "value") else str(verdict),
                "alert_ids": set(),
                "human_confirmed": False,
                "human_rejected": False,
            }
            merged[key] = item
        item["alert_ids"].add(str(alert_id))
        if disp_status == DispositionStatus.CONFIRMED:
            item["human_confirmed"] = True
        elif disp_status == DispositionStatus.REJECTED:
            item["human_rejected"] = True

    samples = [
        {
            "rule_id": item["rule_id"],
            "rule_name": item["rule_name"],
            "event_id": item["event_id"],
            "verdict": item["verdict"],
            "alert_count": len(item["alert_ids"]),
            "human_confirmed": item["human_confirmed"],
            "human_rejected": item["human_rejected"],
        }
        for item in merged.values()
    ]
    items = aggregate_rule_noise(samples, limit=limit)
    return {
        "days": days,
        "items": items,
        "note": "统计来自最近调查结论，以及处置建议的人工确认/驳回。不会修改 Wazuh 规则。",
    }
