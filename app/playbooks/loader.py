"""Curated + community defensive investigation playbooks (not executable Runtime Skills)."""

from __future__ import annotations

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.playbooks.attack_tactics import (
    all_tactics,
    parent_technique_id,
    tactic_key_for_technique,
)

_DIR = Path(__file__).resolve().parent
_CATALOG_PATH = _DIR / "catalog.json"
_COMMUNITY_PATH = _DIR / "community_pack.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    """Merged catalog: curated core first, then community defensive pack."""
    with _CATALOG_PATH.open(encoding="utf-8") as fh:
        curated = json.load(fh)

    community_playbooks: list[dict[str, Any]] = []
    community_meta: dict[str, Any] = {}
    if _COMMUNITY_PATH.is_file():
        with _COMMUNITY_PATH.open(encoding="utf-8") as fh:
            community = json.load(fh)
        community_meta = {
            "community_source": community.get("source"),
            "community_upstream": community.get("upstream"),
            "community_license": community.get("license"),
            "community_note": community.get("note"),
            "community_count": len(community.get("playbooks") or []),
        }
        for item in community.get("playbooks") or []:
            enriched = dict(item)
            enriched.setdefault("pack", "community")
            community_playbooks.append(enriched)

    curated_items: list[dict[str, Any]] = []
    for item in curated.get("playbooks") or []:
        enriched = dict(item)
        enriched.setdefault("pack", "curated")
        curated_items.append(enriched)

    # Curated IDs win on collision.
    seen: set[str] = {str(p.get("id")) for p in curated_items if p.get("id")}
    merged = list(curated_items)
    for item in community_playbooks:
        pid = str(item.get("id") or "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        merged.append(item)

    note_parts = [curated.get("note") or ""]
    if community_meta.get("community_note"):
        note_parts.append(str(community_meta["community_note"]))

    return {
        "version": curated.get("version"),
        "source": curated.get("source"),
        "note": " ".join(p for p in note_parts if p).strip(),
        "playbooks": merged,
        "curated_count": len(curated_items),
        **community_meta,
    }


def list_playbooks(
    *,
    category: str | None = None,
    domain: str | None = None,
    pack: str | None = None,
) -> list[dict[str, Any]]:
    items = list(load_catalog().get("playbooks") or [])
    if pack:
        items = [p for p in items if p.get("pack") == pack]
    if domain:
        items = [p for p in items if p.get("domain") == domain]
    if category:
        matched = match_playbooks(category, limit=10_000)
        ids = {p["id"] for p in matched}
        items = [
            p
            for p in items
            if p["id"] in ids or category in (p.get("alert_categories") or [])
        ]
    return [_public_playbook(p) for p in items]


def get_playbook(playbook_id: str) -> dict[str, Any] | None:
    for item in load_catalog().get("playbooks") or []:
        if item.get("id") == playbook_id:
            return _public_playbook(item)
    return None


def match_playbooks(category: str | None, *, limit: int = 3) -> list[dict[str, Any]]:
    """Return playbooks for an alert/event category (curated specific → community → generic)."""
    items = list(load_catalog().get("playbooks") or [])
    if not category:
        generic = [p for p in items if "*" in (p.get("alert_categories") or [])]
        return [_public_playbook(p) for p in generic[:limit]]

    curated_specific: list[dict[str, Any]] = []
    community_specific: list[dict[str, Any]] = []
    generic: list[dict[str, Any]] = []
    for item in items:
        cats = item.get("alert_categories") or []
        pack = item.get("pack") or "curated"
        if category in cats:
            if pack == "community":
                community_specific.append(item)
            else:
                curated_specific.append(item)
        elif "*" in cats:
            generic.append(item)
    ordered = curated_specific + community_specific + generic
    return [_public_playbook(p) for p in ordered[:limit]]


def catalog_meta() -> dict[str, Any]:
    raw = load_catalog()
    playbooks = raw.get("playbooks") or []
    domains = sorted({p.get("domain") for p in playbooks if p.get("domain")})
    categories = sorted(
        {
            c
            for p in playbooks
            for c in (p.get("alert_categories") or [])
            if c != "*"
        }
    )
    attack_ids = sorted(
        {
            t
            for p in playbooks
            for t in (p.get("mitre_attack") or [])
            if isinstance(t, str) and t.startswith("T")
        }
    )
    return {
        "version": raw.get("version"),
        "source": raw.get("source"),
        "note": raw.get("note"),
        "total": len(playbooks),
        "curated_count": raw.get("curated_count") or 0,
        "community_count": raw.get("community_count") or 0,
        "community_source": raw.get("community_source"),
        "community_upstream": raw.get("community_upstream"),
        "community_license": raw.get("community_license"),
        "domains": domains,
        "alert_categories": categories,
        "mitre_attack_coverage": len(attack_ids),
        "packs": ["curated", "community"],
    }


def attack_coverage(*, pack: str | None = None) -> dict[str, Any]:
    """Build ATT&CK coverage board: tactics → techniques → playbook refs."""
    items = list(load_catalog().get("playbooks") or [])
    if pack:
        items = [p for p in items if p.get("pack") == pack]

    # technique_id -> {playbook_ids, packs, parents}
    tech_books: dict[str, set[str]] = defaultdict(set)
    tech_packs: dict[str, set[str]] = defaultdict(set)
    tech_names_hint: dict[str, str] = {}

    for pb in items:
        pid = str(pb.get("id") or "")
        if not pid:
            continue
        ppack = str(pb.get("pack") or "curated")
        for raw in pb.get("mitre_attack") or []:
            if not isinstance(raw, str) or not raw.startswith("T"):
                continue
            tid = raw.strip().upper()
            tech_books[tid].add(pid)
            tech_packs[tid].add(ppack)
            parent = parent_technique_id(tid)
            if parent != tid:
                tech_books[parent].add(pid)
                tech_packs[parent].add(ppack)

    tactics_meta = {t["key"]: t for t in all_tactics()}
    columns: dict[str, list[dict[str, Any]]] = {k: [] for k in tactics_meta}

    # Prefer parent techniques on the board; keep sub-techniques nested under parent.
    parents = sorted({parent_technique_id(t) for t in tech_books})
    max_count = 1
    for parent in parents:
        # Aggregate count = unique playbooks referencing parent or any sub-technique
        book_ids = set(tech_books.get(parent) or [])
        sub_ids = sorted(t for t in tech_books if parent_technique_id(t) == parent and t != parent)
        for sid in sub_ids:
            book_ids |= tech_books[sid]
        count = len(book_ids)
        max_count = max(max_count, count)
        tactic_key = tactic_key_for_technique(parent)
        if tactic_key not in columns:
            tactic_key = "unmapped"
        packs = set(tech_packs.get(parent) or [])
        for sid in sub_ids:
            packs |= tech_packs.get(sid) or set()
        columns[tactic_key].append(
            {
                "technique_id": parent,
                "playbook_count": count,
                "packs": sorted(packs),
                "sub_techniques": [
                    {
                        "technique_id": sid,
                        "playbook_count": len(tech_books[sid]),
                    }
                    for sid in sub_ids
                ],
                "playbook_ids": sorted(book_ids)[:40],
            }
        )

    for key in columns:
        columns[key].sort(key=lambda x: (-x["playbook_count"], x["technique_id"]))

    tactic_rows = []
    for tactic in all_tactics():
        cells = columns.get(tactic["key"]) or []
        if not cells and tactic["key"] in {"unmapped"}:
            continue
        tactic_rows.append(
            {
                **tactic,
                "technique_count": len(cells),
                "playbook_refs": sum(c["playbook_count"] for c in cells),
                "techniques": cells,
            }
        )

    covered_parents = sum(1 for row in tactic_rows for _ in row["techniques"])
    return {
        "total_playbooks": len(items),
        "covered_techniques": covered_parents,
        "max_playbook_count": max_count,
        "tactics": tactic_rows,
        "pack_filter": pack,
    }


def render_playbook_prompt_section(playbooks: list[dict[str, Any]]) -> list[str]:
    if not playbooks:
        return []
    lines = ["\n## 防御调查剧本（精选知识，非可执行漏洞利用）"]
    for pb in playbooks:
        pack = pb.get("pack") or "curated"
        label = "核心" if pack == "curated" else "社区防御子集"
        lines.append(f"### {pb.get('name')} ({pb.get('id')}) [{label}]")
        if pb.get("summary"):
            lines.append(pb["summary"])
        attack = pb.get("mitre_attack") or []
        if attack:
            lines.append(f"ATT&CK: {', '.join(attack)}")
        steps = pb.get("investigation_steps") or []
        if steps:
            lines.append("建议调查要点:")
            for step in steps:
                lines.append(f"- {step}")
        questions = pb.get("human_questions") or []
        if questions:
            lines.append("可向人工协查的问题示例:")
            for q in questions[:3]:
                lines.append(f"- {q}")
        skills = pb.get("runtime_skills") or []
        if skills:
            lines.append(f"优先调用 Runtime Skill: {', '.join(skills)}")
    lines.append(
        "以上剧本仅提供防御调查指引；仍须基于 Skill 返回证据下结论，不得臆测。"
        "优先用 query_behavior_timeline 做可回源时间线；情报以 sources[] 为准；"
        "单路孤证不得 attack_confirmed。"
    )
    return lines


def _public_playbook(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "domain": item.get("domain"),
        "pack": item.get("pack") or "curated",
        "alert_categories": list(item.get("alert_categories") or []),
        "mitre_attack": list(item.get("mitre_attack") or []),
        "nist_csf": list(item.get("nist_csf") or []),
        "summary": item.get("summary") or "",
        "investigation_steps": list(item.get("investigation_steps") or []),
        "runtime_skills": list(item.get("runtime_skills") or []),
        "human_questions": list(item.get("human_questions") or []),
        "disposition_hints": list(item.get("disposition_hints") or []),
        "source_skill": item.get("source_skill"),
        "license": item.get("license"),
    }


def clear_catalog_cache() -> None:
    load_catalog.cache_clear()
