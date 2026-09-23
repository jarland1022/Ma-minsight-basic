"""Rule noise ranking from human disposition outcomes."""

from app.console.rule_noise import aggregate_rule_noise
from app.db.enums import InvestigationVerdict


def _sample(**overrides: object) -> dict:
    base = {
        "rule_id": "5710",
        "rule_name": "sshd: authentication failed",
        "event_id": "e1",
        "verdict": InvestigationVerdict.LIKELY_FALSE_POSITIVE.value,
        "alert_count": 3,
        "human_confirmed": True,
        "human_rejected": False,
    }
    base.update(overrides)
    return base


def test_human_confirmed_false_positive_ranks_first() -> None:
    rows = aggregate_rule_noise(
        [
            _sample(event_id="e1", alert_count=4),
            _sample(event_id="e2", alert_count=2),
            _sample(
                rule_id="1002",
                rule_name="syslog",
                event_id="e3",
                verdict=InvestigationVerdict.ATTACK_CONFIRMED.value,
                human_confirmed=True,
                alert_count=10,
            ),
        ]
    )
    assert rows[0]["rule_id"] == "5710"
    assert rows[0]["human_confirmed_fp"] == 2
    assert rows[0]["alert_count"] == 6
    assert "收紧" in rows[0]["suggestion"]
    assert all(row["rule_id"] != "1002" for row in rows)


def test_rejected_false_positive_is_not_treated_as_noise() -> None:
    rows = aggregate_rule_noise(
        [
            _sample(human_confirmed=False, human_rejected=True),
        ]
    )
    assert rows == []


def test_repeated_ai_false_positive_is_listed_without_human_confirm() -> None:
    rows = aggregate_rule_noise(
        [
            _sample(event_id="e1", human_confirmed=False),
            _sample(event_id="e2", human_confirmed=False),
        ]
    )
    assert len(rows) == 1
    assert rows[0]["human_confirmed_fp"] == 0
    assert "尚无人工确认" in rows[0]["suggestion"]


def test_same_event_is_counted_once() -> None:
    rows = aggregate_rule_noise(
        [
            _sample(event_id="e1", alert_count=2),
            _sample(event_id="e1", alert_count=5),
        ]
    )
    assert rows[0]["event_count"] == 1
    assert rows[0]["human_confirmed_fp"] == 1
    assert rows[0]["alert_count"] == 7
