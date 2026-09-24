"""Playbook catalog loader tests."""

from __future__ import annotations

from app.playbooks.loader import (
    attack_coverage,
    catalog_meta,
    clear_catalog_cache,
    get_playbook,
    list_playbooks,
    match_playbooks,
    render_playbook_prompt_section,
)


def setup_function() -> None:
    clear_catalog_cache()


def test_catalog_has_curated_and_community_playbooks() -> None:
    meta = catalog_meta()
    assert meta["curated_count"] >= 15
    assert meta["community_count"] >= 150
    assert meta["total"] == meta["curated_count"] + meta["community_count"]
    assert meta["mitre_attack_coverage"] >= 80
    assert "brute_force" in meta["alert_categories"]
    items = list_playbooks()
    assert all("investigation_steps" in p for p in items)
    assert any(p.get("pack") == "community" for p in items)
    # No obvious offensive community ids
    offensive_markers = ("acs-attacking-", "acs-building-c2", "acs-performing-kerberoasting")
    ids = {p["id"] for p in items}
    for marker in offensive_markers:
        assert not any(i.startswith(marker) or i == marker for i in ids)


def test_match_brute_force_prefers_curated_playbook() -> None:
    matched = match_playbooks("brute_force", limit=3)
    assert matched
    assert matched[0]["id"] == "inv-brute-force-auth"
    assert matched[0]["pack"] == "curated"
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


def test_list_by_pack_filter() -> None:
    community = list_playbooks(pack="community")
    curated = list_playbooks(pack="curated")
    assert community
    assert curated
    assert all(p["pack"] == "community" for p in community)
    assert all(p["pack"] == "curated" for p in curated)
    assert all(str(p["id"]).startswith("acs-") for p in community)


def test_community_pack_has_attack_mappings() -> None:
    community = list_playbooks(pack="community")
    with_attack = [p for p in community if p.get("mitre_attack")]
    assert len(with_attack) >= int(len(community) * 0.7)
    for p in community[:30]:
        assert p["investigation_steps"]
        assert not any("do not use" in s.lower() for s in p["investigation_steps"])


def test_attack_coverage_board() -> None:
    cov = attack_coverage()
    assert cov["total_playbooks"] >= 150
    assert cov["covered_techniques"] >= 50
    assert cov["max_playbook_count"] >= 1
    assert len(cov["tactics"]) >= 10
    keys = {t["key"] for t in cov["tactics"]}
    assert "credential-access" in keys
    assert "initial-access" in keys
    # At least one tactic has techniques with playbook refs
    assert any(t["technique_count"] > 0 for t in cov["tactics"])
    curated_only = attack_coverage(pack="curated")
    assert curated_only["total_playbooks"] == catalog_meta()["curated_count"]
    assert curated_only["covered_techniques"] >= 5
