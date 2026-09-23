"""Tests for entity graph traversal."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.entity.graph import GraphEdge, GraphNode, build_graph_summary, traverse_entity_graph


@pytest.mark.asyncio
async def test_traverse_empty_graph() -> None:
    session = AsyncMock()
    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = None
    rel_result = MagicMock()
    rel_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[profile_result, rel_result])

    result = await traverse_entity_graph(
        session,
        seed_entity_type="ip",
        seed_entity_key="1.2.3.4",
        max_hops=1,
    )
    assert "1.2.3.4" in result.summary
    assert len(result.edges) == 0


def test_build_graph_summary_with_edges() -> None:
    summary = build_graph_summary(
        [GraphNode(entity_type="ip", entity_key="1.2.3.4")],
        [
            GraphEdge(
                from_type="ip",
                from_key="1.2.3.4",
                to_type="host",
                to_key="web-01",
                relation_type="has_host",
                confidence=1.0,
            )
        ],
        "ip",
        "1.2.3.4",
    )
    assert "has_host" in summary
