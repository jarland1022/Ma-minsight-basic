"""Skill registry tests."""

import app.skills.bootstrap  # noqa: F401
from app.skills.registry import SkillRegistry
from app.skills.submit_conclusion import SUBMIT_CONCLUSION_NAME


def test_registry_has_mvp_skills() -> None:
    tools = SkillRegistry.tool_definitions(include_submit=True)
    names = {t["function"]["name"] for t in tools}
    assert {"query_asset", "query_history_alerts", "query_threat_intel", "query_entity_graph", SUBMIT_CONCLUSION_NAME} <= names
