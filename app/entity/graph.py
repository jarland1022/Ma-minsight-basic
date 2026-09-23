"""Entity graph BFS traversal for investigation Skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.db.enums import EntityType
from app.models.entity import EntityProfile, EntityRelation
from app.models.investigation import Event

ENTITY_TYPE_MAP = {
    "ip": EntityType.IP,
    "host": EntityType.HOST,
    "user": EntityType.USER,
    "domain": EntityType.DOMAIN,
}


def _node_id(entity_type: EntityType, entity_key: str) -> str:
    return f"{entity_type.value}:{entity_key}"


@dataclass
class GraphNode:
    entity_type: str
    entity_key: str
    display_name: str | None = None
    owner_team: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    from_type: str
    from_key: str
    to_type: str
    to_key: str
    relation_type: str
    confidence: float


@dataclass
class EntityGraphResult:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    summary: str = ""


async def traverse_entity_graph(
    session: AsyncSession,
    *,
    seed_entity_type: str,
    seed_entity_key: str,
    max_hops: int = 2,
    max_nodes: int = 30,
    relation_types: list[str] | None = None,
) -> EntityGraphResult:
    type_str = seed_entity_type.lower()
    if type_str not in ENTITY_TYPE_MAP or not seed_entity_key.strip():
        return EntityGraphResult(summary="Invalid seed entity.")

    seed_type = ENTITY_TYPE_MAP[type_str]
    seed_key = seed_entity_key.strip()
    now = utc_now()

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    visited: set[str] = set()
    frontier: list[tuple[EntityType, str, int]] = [(seed_type, seed_key, 0)]

    while frontier and len(nodes) < max_nodes:
        entity_type, entity_key, depth = frontier.pop(0)
        nid = _node_id(entity_type, entity_key)
        if nid in visited:
            continue
        visited.add(nid)

        profile_row = await session.execute(
            select(EntityProfile).where(
                EntityProfile.entity_type == entity_type,
                EntityProfile.entity_key == entity_key,
            )
        )
        profile = profile_row.scalar_one_or_none()
        meta = dict(profile.metadata_) if profile else {}
        nodes[nid] = GraphNode(
            entity_type=entity_type.value,
            entity_key=entity_key,
            display_name=profile.display_name if profile else None,
            owner_team=profile.owner_team if profile else None,
            metadata=meta,
        )

        if depth >= max_hops:
            continue

        rel_query = select(EntityRelation).where(
            or_(
                (EntityRelation.from_entity_type == entity_type)
                & (EntityRelation.from_entity_key == entity_key),
                (EntityRelation.to_entity_type == entity_type)
                & (EntityRelation.to_entity_key == entity_key),
            )
        )
        if relation_types:
            rel_query = rel_query.where(EntityRelation.relation_type.in_(relation_types))

        rel_result = await session.execute(rel_query)
        for rel in rel_result.scalars():
            if rel.valid_from and rel.valid_from > now:
                continue
            if rel.valid_until and rel.valid_until < now:
                continue

            if rel.from_entity_type == entity_type and rel.from_entity_key == entity_key:
                n_type, n_key = rel.to_entity_type, rel.to_entity_key
                edges.append(
                    GraphEdge(
                        from_type=entity_type.value,
                        from_key=entity_key,
                        to_type=n_type.value,
                        to_key=n_key,
                        relation_type=rel.relation_type,
                        confidence=rel.confidence,
                    )
                )
            else:
                n_type, n_key = rel.from_entity_type, rel.from_entity_key
                edges.append(
                    GraphEdge(
                        from_type=n_type.value,
                        from_key=n_key,
                        to_type=entity_type.value,
                        to_key=entity_key,
                        relation_type=rel.relation_type,
                        confidence=rel.confidence,
                    )
                )
            neighbor_id = _node_id(n_type, n_key)
            if neighbor_id not in visited and len(nodes) + len(frontier) < max_nodes:
                frontier.append((n_type, n_key, depth + 1))

    result = EntityGraphResult(
        nodes=list(nodes.values()),
        edges=edges,
        summary=build_graph_summary(list(nodes.values()), edges, seed_type.value, seed_key),
    )
    return result


async def one_hop_neighbors(
    session: AsyncSession,
    entity_type: EntityType,
    entity_key: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return 1-hop neighbor summaries for query_asset enrichment."""
    partial = await traverse_entity_graph(
        session,
        seed_entity_type=entity_type.value,
        seed_entity_key=entity_key,
        max_hops=1,
        max_nodes=limit + 1,
    )
    return [
        {
            "entity_type": edge.to_type if edge.from_key == entity_key else edge.from_type,
            "entity_key": edge.to_key if edge.from_key == entity_key else edge.from_key,
            "relation_type": edge.relation_type,
            "confidence": edge.confidence,
        }
        for edge in partial.edges
    ][:limit]


def build_graph_summary(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    seed_type: str,
    seed_key: str,
) -> str:
    if not edges:
        return f"No entity relations found for {seed_type}:{seed_key}."
    parts = [f"Graph from {seed_type}:{seed_key}: {len(nodes)} nodes, {len(edges)} edges."]
    for edge in edges[:8]:
        parts.append(
            f"{edge.from_type}:{edge.from_key} -[{edge.relation_type}]-> "
            f"{edge.to_type}:{edge.to_key}"
        )
    if len(edges) > 8:
        parts.append(f"... and {len(edges) - 8} more edges.")
    return " ".join(parts)[:800]


def graph_result_to_snapshot(result: EntityGraphResult, *, seed_type: str, seed_key: str) -> dict[str, Any]:
    """Serialize graph traversal for event.entity_context_snapshot."""
    return {
        "seed_entity_type": seed_type,
        "seed_entity_key": seed_key,
        "captured_at": utc_now().isoformat(),
        "summary": result.summary,
        "node_count": len(result.nodes),
        "edge_count": len(result.edges),
        "nodes": [
            {
                "entity_type": n.entity_type,
                "entity_key": n.entity_key,
                "display_name": n.display_name,
                "owner_team": n.owner_team,
            }
            for n in result.nodes
        ],
        "edges": [
            {
                "from_type": e.from_type,
                "from_key": e.from_key,
                "to_type": e.to_type,
                "to_key": e.to_key,
                "relation_type": e.relation_type,
                "confidence": e.confidence,
            }
            for e in result.edges
        ],
    }


async def build_event_entity_context_snapshot(
    session: AsyncSession,
    event: Event,
    *,
    max_hops: int = 1,
    max_nodes: int = 20,
) -> dict[str, Any] | None:
    """Freeze a lightweight entity subgraph when investigation starts."""
    from sqlalchemy.orm import selectinload

    from app.models.investigation import EventAlert

    # Always eager-load links; accessing event.alert_links without selectinload
    # triggers lazy IO and fails under AsyncSession (greenlet_spawn error).
    row = await session.execute(
        select(Event)
        .options(selectinload(Event.alert_links).selectinload(EventAlert.alert))
        .where(Event.id == event.id)
    )
    loaded = row.scalar_one_or_none()
    if loaded is None:
        return None
    event = loaded

    seed_type, seed_key = _pick_event_seed_entity(event)
    if not seed_type or not seed_key:
        return None

    graph = await traverse_entity_graph(
        session,
        seed_entity_type=seed_type,
        seed_entity_key=seed_key,
        max_hops=max_hops,
        max_nodes=max_nodes,
    )
    return graph_result_to_snapshot(graph, seed_type=seed_type, seed_key=seed_key)


def _pick_event_seed_entity(event: Event) -> tuple[str | None, str | None]:
    for link in event.alert_links:
        alert = link.alert
        if alert.src_ip:
            return "ip", str(alert.src_ip)
    if event.aggregate_host_name:
        return "host", event.aggregate_host_name
    if event.aggregate_user_name:
        return "user", event.aggregate_user_name
    return None, None
