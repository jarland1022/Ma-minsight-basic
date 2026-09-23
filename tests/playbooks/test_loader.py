"""Playbook catalog loader tests."""

from __future__ import annotations

from app.playbooks.loader import (
    catalog_meta,
    get_playbook,
    list_playbooks,
    match_playbooks,
    render_playbook_prompt_section,
)


def test_catalog_has_curated_defensive_playbooks() -> None:
    meta = catalog_meta()
    assert meta["total"] >= 15
    assert "brute_force" in meta["alert_categories"]
    items = list_playbooks()
    assert all("investigation_steps" in p for p in items)


def test_match_brute_force_prefers_specific_playbook() -> None:
    matched = match_playbooks("brute_force", limit=2)
    assert matched
    assert matched[0]["id"] == "inv-brute-force-auth"
    assert "T1110" in matched[0]["mitre_attack"]


def test_match_unknown_falls_back_to_generic() -> None:
    matched = match_playbooks("totally_new_category", limit=1)
    assert matched[0]["id"] == "inv-generic-deep-review"


def test_get_playbook_and_prompt_section() -> None:
    pb = get_playbook("inv-web-attack")
    assert pb is not None
    lines = render_playbook_prompt_section([pb])
    assert any("Web 攻击" in line for line in lines)
    assert any("防御调查剧本" in line for line in lines)
