"""Read-only disposition impact simulation (Mock / CMDB placeholder)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import EntityType
from app.entity.graph import traverse_entity_graph
from app.models.entity import EntityProfile


ACTION_PARAM_KEYS = {
    "block_ip": "ip",
    "isolate_host": "host_name",
    "disable_user": "user_name",
}


@dataclass
class SimulationResult:
    action_type: str
    action_params: dict[str, Any]
    simulated_impact: dict[str, Any]
    summary: str


class DispositionSimulator:
    """Estimate blast radius without executing any enforcement action."""

    async def simulate(
        self,
        session: AsyncSession,
        *,
        action_type: str,
        action_params: dict[str, Any],
        mock_mode: bool = True,
    ) -> SimulationResult:
        action_type = action_type.strip().lower()
        param_key = ACTION_PARAM_KEYS.get(action_type)
        if param_key is None:
            raise ValueError(f"Unsupported action_type: {action_type}")

        target = str(action_params.get(param_key) or "").strip()
        if not target:
            raise ValueError(f"action_params.{param_key} is required for {action_type}")

        seed_type = {"block_ip": "ip", "isolate_host": "host", "disable_user": "user"}[action_type]
        graph = await traverse_entity_graph(
            session,
            seed_entity_type=seed_type,
            seed_entity_key=target,
            max_hops=2,
            max_nodes=25,
        )

        hosts = {
            n.entity_key
            for n in graph.nodes
            if n.entity_type == EntityType.HOST.value
        }
        if action_type == "isolate_host":
            hosts.add(target)

        business_systems: set[str] = set()
        for node in graph.nodes:
            systems = node.metadata.get("business_systems") or []
            if isinstance(systems, list):
                business_systems.update(str(s) for s in systems)

        profile_row = await session.execute(
            select(EntityProfile).where(
                EntityProfile.entity_type == EntityType(seed_type),
                EntityProfile.entity_key == target,
            )
        )
        profile = profile_row.scalar_one_or_none()
        if profile and profile.metadata_:
            systems = profile.metadata_.get("business_systems") or []
            if isinstance(systems, list):
                business_systems.update(str(s) for s in systems)

        host_count = len(hosts)
        downtime = _estimate_downtime_minutes(action_type, host_count)
        risk_notes = _risk_notes(action_type, target, host_count, business_systems)

        impact: dict[str, Any] = {
            "mode": "mock" if mock_mode else "cmdb",
            "action_type": action_type,
            "target": target,
            "affected_hosts": sorted(hosts)[:20],
            "affected_host_count": host_count,
            "business_systems": sorted(business_systems)[:10],
            "estimated_downtime_minutes": downtime,
            "graph_node_count": len(graph.nodes),
            "graph_edge_count": len(graph.edges),
            "risk_notes": risk_notes,
        }

        summary = (
            f"[推演/Mock] {action_type} → {target}: "
            f"影响约 {host_count} 台主机"
            + (f"、业务系统 {', '.join(sorted(business_systems)[:3])}" if business_systems else "")
            + f"；预估中断 {downtime} 分钟。"
            + (" " + risk_notes[0] if risk_notes else "")
        )
        return SimulationResult(
            action_type=action_type,
            action_params={param_key: target, **{k: v for k, v in action_params.items() if k != param_key}},
            simulated_impact=impact,
            summary=summary[:900],
        )


def _estimate_downtime_minutes(action_type: str, host_count: int) -> int:
    base = {"block_ip": 5, "isolate_host": 30, "disable_user": 15}[action_type]
    return base + max(0, host_count - 1) * 10


def _risk_notes(
    action_type: str,
    target: str,
    host_count: int,
    business_systems: set[str],
) -> list[str]:
    notes: list[str] = []
    if action_type == "block_ip":
        notes.append("可能阻断合法供应商或 CDN 回源访问，需核对白名单与业务窗口。")
    if action_type == "isolate_host" and host_count > 3:
        notes.append("关联主机较多，隔离可能影响同网段业务互访。")
    if action_type == "disable_user":
        notes.append("账号禁用可能影响值班/运维跳板访问，需确认是否为共享账号。")
    if business_systems:
        notes.append(f"涉及业务系统: {', '.join(sorted(business_systems)[:5])}。")
    if not notes:
        notes.append(f"目标 {target} 关联面较小，但仍需人工确认后再执行真实处置。")
    return notes
