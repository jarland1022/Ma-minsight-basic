"""Query entity relationship graph for cross-alert correlation."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import InvestigationContext
from app.entity.graph import traverse_entity_graph
from app.services.system_config import get_config_bool, get_config_int
from app.skills.base import Skill, SkillResult


class QueryEntityGraphSkill(Skill):
    name = "query_entity_graph"
    description = (
        "Traverse entity relations (IP/host/user) to build context graph and natural-language summary. "
        "Use early in investigation to connect isolated alerts."
    )

    @classmethod
    def parameters_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "seed_entity_type": {"type": "string", "enum": ["ip", "host", "user", "domain"]},
                "seed_entity_key": {"type": "string"},
                "max_hops": {"type": "integer", "default": 2},
                "relation_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional filter, e.g. has_public_ip, business_peer",
                },
            },
            "required": ["seed_entity_type", "seed_entity_key"],
        }

    async def execute(
        self,
        params: dict[str, Any],
        ctx: InvestigationContext,
        session: AsyncSession,
    ) -> SkillResult:
        enabled = await get_config_bool(session, "entity.graph_enabled", True)
        if not enabled:
            return SkillResult(
                success=False,
                summary="Entity graph is disabled in system_config.",
                error="disabled",
            )

        seed_type = str(params.get("seed_entity_type", "")).lower()
        seed_key = str(params.get("seed_entity_key", "")).strip()
        max_hops = int(params.get("max_hops") or await get_config_int(session, "entity.graph_max_hops", 2))
        max_nodes = await get_config_int(session, "entity.graph_max_nodes", 30)
        relation_types = params.get("relation_types")
        if relation_types is not None and not isinstance(relation_types, list):
            relation_types = None

        graph = await traverse_entity_graph(
            session,
            seed_entity_type=seed_type,
            seed_entity_key=seed_key,
            max_hops=max_hops,
            max_nodes=max_nodes,
            relation_types=relation_types,
        )

        data = {
            "nodes": [
                {
                    "entity_type": n.entity_type,
                    "entity_key": n.entity_key,
                    "display_name": n.display_name,
                    "owner_team": n.owner_team,
                    "metadata": n.metadata,
                }
                for n in graph.nodes
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
                for e in graph.edges
            ],
        }
        return SkillResult(
            success=True,
            summary=graph.summary,
            data=data,
            evidence_ref=f"graph:{seed_type}:{seed_key}",
        )
