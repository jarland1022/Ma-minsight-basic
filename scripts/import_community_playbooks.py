#!/usr/bin/env python3
"""Import a defensive subset from Anthropic-Cybersecurity-Skills into MinSight.

Generates app/playbooks/community_pack.json — knowledge only, never executable.
Offensive / dual-use skill directories are excluded by prefix and keyword deny lists.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Prefer these prefixes (defensive SOC / DFIR / IR / hardening).
ALLOW_PREFIXES: tuple[str, ...] = (
    "detecting-",
    "triaging-",
    "containing-",
    "correlating-",
    "automating-ioc-",
    "collecting-indicators-",
    "collecting-volatile-",
    "recovering-from-",
    "validating-backup-",
    "defending-",
    "securing-",
    "remediating-",
    "prioritizing-vulnerabilities-",
    "processing-stix-",
    "profiling-threat-",
    "tracking-threat-",
)

# Secondary allow: only if name also matches a safe token below.
CONDITIONAL_PREFIXES: tuple[str, ...] = (
    "analyzing-",
    "building-",
    "conducting-",
    "performing-",
    "configuring-",
    "deploying-",
    "auditing-",
)

SAFE_TOKENS: tuple[str, ...] = (
    "log",
    "forensic",
    "incident",
    "playbook",
    "detection",
    "threat-hunt",
    "threat-hunting",
    "ransomware-response",
    "alert-triage",
    "malware-triage",
    "ioc",
    "phishing-incident",
    "malware-incident",
    "cloud-incident",
    "post-incident",
    "soc-",
    "sigma",
    "yara",
    "siem",
    "splunk",
    "zeek",
    "suricata",
    "snort",
    "osquery",
    "honeytoken",
    "canary",
    "decoy",
    "hardening",
    "cis-benchmark",
    "compliance",
    "false-positive",
    "user-behavior",
    "lateral-movement-detection",
    "dns-tunneling-detection",
    "container-escape-detection",
    "memory-forensic",
    "disk-forensic",
    "network-forensic",
    "endpoint-forensic",
    "windows-event",
    "audit-log",
    "threat-intel",
    "threat-intelligence",
    "indicator",
    "timeline",
    "ir-playbook",
    "cisa-framework",
    "guardrail",
    "prompt-injection",  # detecting/defending only via other filters
)

DENY_PREFIXES: tuple[str, ...] = (
    "abusing-",
    "attacking-",
    "bypassing-",
    "coercing-",
    "relaying-",
    "post-exploiting-",
    "red-teaming-",
)

DENY_TOKENS: tuple[str, ...] = (
    "-attack",
    "attack-simulation",
    "attack-test",
    "penetration-test",
    "penetration-testing",
    "red-team",
    "c2-infrastructure",
    "c2-redirector",
    "phishing-simulation",
    "spearphishing",
    "social-engineering",
    "pass-the-ticket",
    "pass-the-hash",
    "kerberoasting",
    "dcsync",
    "evilginx",
    "hashcat",
    "hash-cracking",
    "wifi-password-cracking",
    "packet-injection",
    "ssl-stripping",
    "arp-spoofing",
    "vlan-hopping",
    "force-browsing",
    "forced-browsing",
    "jwt-none",
    "ssrf-vulnerability-exploitation",
    "blind-ssrf",
    "sql-injection",
    "xss-vulnerabilit",
    "xxe-injection",
    "csrf-attack",
    "clickjacking",
    "web-cache-poison",
    "web-cache-deception",
    "waf-bypass",
    "rate-limiting-bypass",
    "certificate-pinning-bypass",
    "privilege-escalation-on-",
    "lateral-movement-with-",
    "credential-access-with-",
    "initial-access-with-",
    "building-c2",
    "building-red-team",
    "building-adversary",
    "conducting-full-scope-red",
    "conducting-internal-network-penetration",
    "conducting-external-reconnaissance",
    "conducting-network-penetration",
    "conducting-cloud-penetration",
    "conducting-mobile-app-penetration",
    "conducting-wireless",
    "conducting-man-in-the-middle",
    "conducting-domain-persistence",
    "conducting-pass-the",
    "performing-web-application-penetration",
    "performing-external-network-penetration",
    "performing-cloud-penetration",
    "performing-kubernetes-penetration",
    "performing-api-fuzzing",
    "performing-fuzzing-with",
    "performing-binary-exploitation",
    "performing-graphql-depth",
    "performing-graphql-introspection",
    "performing-directory-traversal",
    "performing-http-parameter-pollution",
    "performing-content-security-policy-bypass",
    "performing-mobile-app-certificate",
    "performing-supply-chain-attack-simulation",
    "performing-threat-emulation",
    "performing-purple-team",
    "performing-red-team",
    "performing-arp-spoofing",
    "performing-bandwidth-throttling-attack",
    "performing-packet-injection",
    "performing-ssl-stripping",
    "performing-vlan-hopping",
    "performing-wifi-password",
    "performing-hash-cracking",
    "performing-kerberoasting",
    "performing-initial-access",
    "performing-credential-access",
    "performing-lateral-movement-with",
    "performing-privilege-escalation-on",
    "performing-dns-enumeration",
    "performing-subdomain-enumeration",
    "performing-open-source-intelligence-gathering",
    "performing-osint-with",
    "performing-dark-web",
    "performing-paste-site",
    "analyzing-heap-spray",
    "analyzing-ethereum-smart-contract-vulnerabilities",
    "testing-for-",
    "testing-api-",
    "testing-cors-",
    "testing-jwt-",
    "testing-oauth",
    "testing-prompt-injection",  # offensive testing style
    "testing-android-",
    "testing-mobile-",
    "testing-websocket-",
    "continuous-llm-red-teaming",
)

# Map skill name / tags → MinSight alert categories (best-effort).
CATEGORY_RULES: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"brute|password.?spray|credential.?stuff|auth(enticat)?", re.I), ["brute_force", "authentication"]),
    (re.compile(r"login.?anomal|anomalous.?auth|impossible.?travel", re.I), ["login_anomaly"]),
    (re.compile(r"web.?attack|waf|xss|sqli|web.?server.?log|api.?gateway", re.I), ["web_attack"]),
    (re.compile(r"network.?intrusion|ids|ips|suricata|snort|zeek|beaconing|c2|command.?and.?control", re.I), ["network_intrusion", "ids"]),
    (re.compile(r"firewall|pf.?sense", re.I), ["firewall"]),
    (re.compile(r"malware|ransomware|cobalt.?strike|empire|rootkit|bootkit|packed.?malware|yara", re.I), ["malware", "ransomware"]),
    (re.compile(r"file.?integrit|syscheck|autoruns|persistence", re.I), ["file_integrity", "syscheck"]),
    (re.compile(r"host.?anomal|ossec|endpoint|osquery|edr|amcache|prefetch", re.I), ["host_anomaly", "ossec"]),
    (re.compile(r"windows.?event|powershell.?script.?block|sysmon|registry.?for", re.I), ["windows_event"]),
    (re.compile(r"privilege.?escalat|kerberoast|dcsync|token", re.I), ["privilege_escalation"]),
    (re.compile(r"exfiltrat|data.?theft|dns.?tunnel|covert.?channel", re.I), ["data_exfiltration", "dns"]),
    (re.compile(r"lateral.?movement|smb|wmi|rdp", re.I), ["lateral_movement"]),
    (re.compile(r"phish|bec|business.?email|email.?header|spear", re.I), ["phishing", "bec"]),
    (re.compile(r"cloud|aws|azure|gcp|kubernetes|container|docker|guardduty", re.I), ["cloud_access", "cloud"]),
    (re.compile(r"\bdns\b|typosquat|certificate.?transparency", re.I), ["dns", "c2"]),
    (re.compile(r"ransomware", re.I), ["ransomware"]),
    (re.compile(r"supply.?chain|sbom|dependency", re.I), ["supply_chain"]),
    (re.compile(r"insider|ueba|user.?behavior", re.I), ["insider", "ueba"]),
    (re.compile(r"compliance|pci|gdpr|cmmc|nist.?csf", re.I), ["compliance"]),
    (re.compile(r"syslog|siem|splunk|qradar|elastic", re.I), ["syslog"]),
]

DOMAIN_MAP: dict[str, str] = {
    "threat-detection": "detection",
    "incident-response": "incident_response",
    "digital-forensics": "forensics",
    "malware-analysis": "malware",
    "threat-intelligence": "threat_intel",
    "cloud-security": "cloud",
    "identity-security": "identity",
    "network-security": "network",
    "vulnerability-management": "vulnerability",
    "compliance": "compliance",
    "ai-security": "ai_security",
    "application-security": "appsec",
    "ot-ics-security": "ot",
}

DEFAULT_RUNTIME = [
    "query_behavior_timeline",
    "query_sample_enrichment",
    "query_entity_graph",
    "query_asset",
    "query_history_alerts",
    "query_threat_intel",
]

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
STEPS_RE = re.compile(r"##\s+Steps\s*\n+(.*?)(?:\n##\s+|\Z)", re.S | re.I)
OVERVIEW_RE = re.compile(r"##\s+Overview\s*\n+(.*?)(?:\n##\s+|\Z)", re.S | re.I)
WHEN_RE = re.compile(r"##\s+When to Use\s*\n+(.*?)(?:\n##\s+|\Z)", re.S | re.I)
WORKFLOW_STEP_RE = re.compile(r"###\s+Step\s+\d+:\s*(.+)", re.I)


def _parse_simple_yaml_list(block: str, key: str) -> list[str]:
    """Minimal list extractor for flat YAML frontmatter keys (no nested objects)."""
    # Inline: key: [a, b]
    m = re.search(rf"(?m)^{re.escape(key)}:\s*\[([^\]]*)\]\s*$", block)
    if m:
        return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()]

    # Multiline: key:\n- item  (with or without indentation; stop at next top-level key)
    m = re.search(rf"(?m)^{re.escape(key)}:\s*\n((?:[ \t]*-[ \t].+\n?)*)", block)
    if not m:
        return []
    items: list[str] = []
    for line in m.group(1).splitlines():
        s = line.strip()
        if not s.startswith("-"):
            break
        # Skip nested mappings like "- id: T1555"
        rest = s[1:].strip()
        if re.match(r"^[A-Za-z_][\w-]*:", rest) and not rest.startswith("T"):
            continue
        items.append(rest.strip("\"'"))
    return items


def _parse_scalar(block: str, key: str) -> str | None:
    m = re.search(rf"(?m)^{re.escape(key)}:\s*(.+)$", block)
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def _is_allowed(name: str) -> bool:
    if any(name.startswith(p) for p in DENY_PREFIXES):
        return False
    if any(tok in name for tok in DENY_TOKENS):
        return False
    if any(name.startswith(p) for p in ALLOW_PREFIXES):
        return True
    if any(name.startswith(p) for p in CONDITIONAL_PREFIXES):
        return any(tok in name for tok in SAFE_TOKENS)
    return False


def _title_from_slug(slug: str) -> str:
    return slug.replace("-", " ").strip().title()


def _bullet_lines(section: str) -> list[str]:
    lines: list[str] = []
    for raw in section.splitlines():
        s = raw.strip()
        if not s:
            continue
        s = re.sub(r"^[-*]\s+", "", s)
        s = re.sub(r"^\d+\.\s+", "", s)
        if s.startswith("#") or s.startswith("```"):
            continue
        if re.match(r"(?i)^\*\*do not use\*\*", s) or s.lower().startswith("do not use"):
            continue
        if len(s) > 220:
            s = s[:217] + "..."
        lines.append(s)
    return lines


def _extract_steps(body: str) -> list[str]:
    steps_m = STEPS_RE.search(body)
    if steps_m:
        steps = _bullet_lines(steps_m.group(1))
        if steps:
            return steps[:8]
    workflow_titles = [m.group(1).strip() for m in WORKFLOW_STEP_RE.finditer(body)]
    if workflow_titles:
        return workflow_titles[:8]
    when_m = WHEN_RE.search(body)
    if when_m:
        return _bullet_lines(when_m.group(1))[:8]
    return []


def _map_categories(name: str, tags: list[str], description: str) -> list[str]:
    blob = " ".join([name, " ".join(tags), description])
    found: list[str] = []
    seen: set[str] = set()
    for pat, cats in CATEGORY_RULES:
        if pat.search(blob):
            for c in cats:
                if c not in seen:
                    seen.add(c)
                    found.append(c)
    if not found:
        found = ["uncategorized"]
    return found[:4]


def _map_domain(subdomain: str | None, name: str) -> str:
    if subdomain and subdomain in DOMAIN_MAP:
        return DOMAIN_MAP[subdomain]
    for key, dom in DOMAIN_MAP.items():
        if key.replace("-", "_") in name.replace("-", "_"):
            return dom
    if name.startswith("detecting-") or name.startswith("triaging-"):
        return "detection"
    if "forensic" in name:
        return "forensics"
    if "incident" in name or name.startswith("containing-"):
        return "incident_response"
    if "cloud" in name or "aws" in name or "azure" in name or "kubernetes" in name:
        return "cloud"
    return "community"


def _priority(name: str) -> int:
    """Lower = more preferred when capping the pack."""
    if name.startswith("detecting-"):
        return 0
    if name.startswith("triaging-"):
        return 1
    if name.startswith("containing-") or "incident-response" in name or "ransomware-response" in name:
        return 2
    if "forensic" in name or name.startswith("analyzing-") and "log" in name:
        return 3
    if name.startswith("building-") and ("playbook" in name or "detection" in name or "soc" in name):
        return 4
    if name.startswith("performing-") and ("detection" in name or "forensic" in name or "threat-hunt" in name):
        return 5
    return 10


def convert_skill(skill_dir: Path) -> dict | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None
    name = skill_dir.name
    if not _is_allowed(name):
        return None

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm_m = FRONTMATTER_RE.match(text)
    fm = fm_m.group(1) if fm_m else ""
    body = text[fm_m.end() :] if fm_m else text

    description = _parse_scalar(fm, "description") or ""
    subdomain = _parse_scalar(fm, "subdomain")
    tags = _parse_simple_yaml_list(fm, "tags")
    mitre = [t for t in _parse_simple_yaml_list(fm, "mitre_attack") if t.startswith("T")]
    nist = _parse_simple_yaml_list(fm, "nist_csf")
    # Normalize NIST to function.category style used in curated pack when possible
    nist_short = sorted({re.split(r"[-_]", n, maxsplit=1)[0] if "." not in n else n.split("-")[0] for n in nist})
    # Prefer DE.CM style from frontmatter (already like DE.CM-01)
    nist_norm: list[str] = []
    for n in nist:
        base = n.split("-")[0] if re.match(r"^[A-Z]{2}\.", n) else n
        if base not in nist_norm:
            nist_norm.append(base)
        if len(nist_norm) >= 4:
            break

    overview_m = OVERVIEW_RE.search(body)
    summary = ""
    if overview_m:
        para = overview_m.group(1).strip().split("\n\n")[0]
        summary = re.sub(r"\s+", " ", para).strip()
    if not summary and description:
        summary = description
    if len(summary) > 280:
        summary = summary[:277] + "..."

    steps = _extract_steps(body)
    if not steps:
        steps = [
            "核对告警实体、时间窗与资产角色",
            "沿关联图扩展相关主机/账号/网络实体",
            "检索历史告警与威胁情报后再下结论",
        ]

    display = _parse_scalar(fm, "name") or name
    # Prefer human title from H1
    h1 = re.search(r"^#\s+(.+)$", body, re.M)
    title = h1.group(1).strip() if h1 else _title_from_slug(display)

    return {
        "id": f"acs-{name}",
        "name": title,
        "domain": _map_domain(subdomain, name),
        "alert_categories": _map_categories(name, tags, description),
        "mitre_attack": mitre[:8],
        "nist_csf": nist_norm or nist_short[:4],
        "summary": summary,
        "investigation_steps": steps,
        "runtime_skills": list(DEFAULT_RUNTIME),
        "human_questions": [
            "该活动是否属于已知变更、扫描或授权测试？",
            "相关资产/账号归属与业务影响如何？",
        ],
        "disposition_hints": [
            "仅输出处置建议，不在设备上自动执行阻断",
            "证据不足时发起人工协查后再确认结论",
        ],
        "source_skill": name,
        "source": "anthropic-cybersecurity-skills-community",
        "license": "Apache-2.0",
    }


def import_pack(
    skills_root: Path,
    *,
    limit: int = 120,
) -> dict:
    candidates: list[tuple[int, str, dict]] = []
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        pb = convert_skill(skill_dir)
        if not pb:
            continue
        candidates.append((_priority(skill_dir.name), skill_dir.name, pb))

    candidates.sort(key=lambda x: (x[0], x[1]))
    selected = [c[2] for c in candidates[:limit]]

    return {
        "version": 1,
        "source": "Anthropic-Cybersecurity-Skills (community, defensive subset)",
        "upstream": "https://github.com/mukul975/Anthropic-Cybersecurity-Skills",
        "license": "Apache-2.0",
        "note": (
            "Defensive investigation knowledge imported from the community cybersecurity "
            "skills library. Offensive/dual-use skills are excluded. Not affiliated with "
            "Anthropic PBC. Guidance only — not executable Runtime Skills."
        ),
        "imported_count": len(selected),
        "scanned_allowed": len(candidates),
        "playbooks": selected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=Path(r"D:\AI\Anthropic-Cybersecurity-Skills-main\skills"),
        help="Path to upstream skills/ directory",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "app" / "playbooks" / "community_pack.json",
    )
    parser.add_argument("--limit", type=int, default=180)
    args = parser.parse_args()

    if not args.skills_root.is_dir():
        raise SystemExit(f"skills root not found: {args.skills_root}")

    pack = import_pack(args.skills_root, limit=args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {pack['imported_count']} playbooks (from {pack['scanned_allowed']} allowed) -> {args.out}")


if __name__ == "__main__":
    main()
