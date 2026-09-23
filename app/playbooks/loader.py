"""Curated defensive investigation playbooks (not executable Runtime Skills)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).with_name("catalog.json")


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    with _CATALOG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def list_playbooks(*, category: str | None = None, domain: str | None = None) -> list[dict[str, Any]]:
    items = list(load_catalog().get("playbooks") or [])
    if domain:
        items = [p for p in items if p.get("domain") == domain]
    if category:
        matched = match_playbooks(category)
        ids = {p["id"] for p in matched}
        # Keep category-specific first, then still allow filtering list view by category
        items = [p for p in items if p["id"] in ids or category in (p.get("alert_categories") or [])]
    return [_public_playbook(p) for p in items]


def get_playbook(playbook_id: str) -> dict[str, Any] | None:
    for item in load_catalog().get("playbooks") or []:
        if item.get("id") == playbook_id:
            return _public_playbook(item)
    return None


def match_playbooks(category: str | None, *, limit: int = 3) -> list[dict[str, Any]]:
    """Return playbooks for an alert/event category (specific first, generic last)."""
    items = list(load_catalog().get("playbooks") or [])
    if not category:
        generic = [p for p in items if "*" in (p.get("alert_categories") or [])]
        return [_public_playbook(p) for p in generic[:limit]]

    specific: list[dict[str, Any]] = []
    generic: list[dict[str, Any]] = []
    for item in items:
        cats = item.get("alert_categories") or []
        if category in cats:
            specific.append(item)
        elif "*" in cats:
            generic.append(item)
    ordered = specific + generic
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
    return {
        "version": raw.get("version"),
        "source": raw.get("source"),
        "note": raw.get("note"),
        "total": len(playbooks),
        "domains": domains,
        "alert_categories": categories,
    }


def render_playbook_prompt_section(playbooks: list[dict[str, Any]]) -> list[str]:
    if not playbooks:
        return []
    lines = ["\n## 防御调查剧本（精选知识，非可执行漏洞利用）"]
    for pb in playbooks:
        lines.append(f"### {pb.get('name')} ({pb.get('id')})")
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
    )
    return lines


def _public_playbook(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "domain": item.get("domain"),
        "alert_categories": list(item.get("alert_categories") or []),
        "mitre_attack": list(item.get("mitre_attack") or []),
        "nist_csf": list(item.get("nist_csf") or []),
        "summary": item.get("summary") or "",
        "investigation_steps": list(item.get("investigation_steps") or []),
        "runtime_skills": list(item.get("runtime_skills") or []),
        "human_questions": list(item.get("human_questions") or []),
        "disposition_hints": list(item.get("disposition_hints") or []),
    }
