"""P0-08 audit log serialization / filter field presence (unit-level)."""

from types import SimpleNamespace
from uuid import uuid4

from app.db.enums import ActorType


def _serialize(r) -> dict:
    """Mirror audit_logs / system list shape."""
    return {
        "id": str(r.id),
        "action": r.action,
        "actor_type": r.actor_type.value if r.actor_type else None,
        "actor_id": r.actor_id,
        "resource_type": r.resource_type,
        "resource_id": r.resource_id,
        "detail": r.detail,
        "result": r.result,
        "correlation_id": r.correlation_id,
        "client_ip": r.client_ip,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def test_audit_row_exposes_result_and_correlation() -> None:
    from datetime import UTC, datetime

    row = SimpleNamespace(
        id=uuid4(),
        action="config.update",
        actor_type=ActorType.USER,
        actor_id="admin-id",
        resource_type="system_config",
        resource_id="triage",
        detail={"before": {"value": {"x": 1}}, "after": {"value": {"x": 2}}},
        result="success",
        correlation_id="abc123",
        client_ip="10.0.0.1",
        created_at=datetime.now(UTC),
    )
    payload = _serialize(row)
    assert payload["result"] == "success"
    assert payload["correlation_id"] == "abc123"
    assert payload["client_ip"] == "10.0.0.1"
    assert payload["detail"]["before"]["value"]["x"] == 1


def test_success_vs_failure_distinguishable() -> None:
    ok = _serialize(
        SimpleNamespace(
            id=uuid4(),
            action="disposition.confirm",
            actor_type=ActorType.USER,
            actor_id="u1",
            resource_type="disposition",
            resource_id="r1",
            detail={},
            result="success",
            correlation_id="c1",
            client_ip=None,
            created_at=None,
        )
    )
    bad = _serialize(
        SimpleNamespace(
            id=uuid4(),
            action="disposition.confirm",
            actor_type=ActorType.USER,
            actor_id="u1",
            resource_type="disposition",
            resource_id="r1",
            detail={"error": "denied"},
            result="denied",
            correlation_id="c2",
            client_ip=None,
            created_at=None,
        )
    )
    assert ok["result"] != bad["result"]
