"""MITRE ATT&CK tactic/technique helpers for playbook coverage boards."""

from __future__ import annotations

# Enterprise ATT&CK tactic order (v14+). ICS techniques (T08xx) map to "ics".
ENTERPRISE_TACTICS: list[dict[str, str]] = [
    {"id": "TA0043", "key": "reconnaissance", "name": "Reconnaissance", "name_zh": "侦察"},
    {"id": "TA0042", "key": "resource-development", "name": "Resource Development", "name_zh": "资源开发"},
    {"id": "TA0001", "key": "initial-access", "name": "Initial Access", "name_zh": "初始访问"},
    {"id": "TA0002", "key": "execution", "name": "Execution", "name_zh": "执行"},
    {"id": "TA0003", "key": "persistence", "name": "Persistence", "name_zh": "持久化"},
    {"id": "TA0004", "key": "privilege-escalation", "name": "Privilege Escalation", "name_zh": "权限提升"},
    {"id": "TA0005", "key": "defense-evasion", "name": "Defense Evasion", "name_zh": "防御绕过"},
    {"id": "TA0006", "key": "credential-access", "name": "Credential Access", "name_zh": "凭证访问"},
    {"id": "TA0007", "key": "discovery", "name": "Discovery", "name_zh": "发现"},
    {"id": "TA0008", "key": "lateral-movement", "name": "Lateral Movement", "name_zh": "横向移动"},
    {"id": "TA0009", "key": "collection", "name": "Collection", "name_zh": "收集"},
    {"id": "TA0011", "key": "command-and-control", "name": "Command and Control", "name_zh": "命令与控制"},
    {"id": "TA0010", "key": "exfiltration", "name": "Exfiltration", "name_zh": "数据渗出"},
    {"id": "TA0040", "key": "impact", "name": "Impact", "name_zh": "影响"},
]

ICS_TACTIC = {
    "id": "ICS",
    "key": "ics",
    "name": "ICS / OT",
    "name_zh": "工控 / OT",
}

UNMAPPED_TACTIC = {
    "id": "UNMAPPED",
    "key": "unmapped",
    "name": "Unmapped",
    "name_zh": "未映射",
}

# Primary tactic for parent technique IDs (sub-techniques inherit parent).
# Coverage-oriented: one primary tactic per technique for heatmap columns.
_TECHNIQUE_PRIMARY_TACTIC: dict[str, str] = {
    # Reconnaissance
    "T1595": "reconnaissance",
    "T1592": "reconnaissance",
    "T1589": "reconnaissance",
    "T1590": "reconnaissance",
    "T1591": "reconnaissance",
    "T1598": "reconnaissance",
    "T1596": "reconnaissance",
    "T1593": "reconnaissance",
    "T1594": "reconnaissance",
    "T1597": "reconnaissance",
    # Resource Development
    "T1583": "resource-development",
    "T1584": "resource-development",
    "T1585": "resource-development",
    "T1586": "resource-development",
    "T1587": "resource-development",
    "T1588": "resource-development",
    "T1608": "resource-development",
    # Initial Access
    "T1133": "initial-access",
    "T1189": "initial-access",
    "T1190": "initial-access",
    "T1195": "initial-access",
    "T1199": "initial-access",
    "T1200": "initial-access",
    "T1566": "initial-access",
    "T1078": "initial-access",
    "T1091": "initial-access",
    "T1199": "initial-access",
    "T1665": "initial-access",
    # Execution
    "T1059": "execution",
    "T1203": "execution",
    "T1204": "execution",
    "T1047": "execution",
    "T1053": "execution",
    "T1106": "execution",
    "T1129": "execution",
    "T1559": "execution",
    "T1569": "execution",
    "T1072": "execution",
    "T1609": "execution",
    "T1610": "execution",
    "T1651": "execution",
    # Persistence
    "T1098": "persistence",
    "T1136": "persistence",
    "T1543": "persistence",
    "T1546": "persistence",
    "T1547": "persistence",
    "T1037": "persistence",
    "T1137": "persistence",
    "T1505": "persistence",
    "T1525": "persistence",
    "T1554": "persistence",
    "T1574": "persistence",
    "T1197": "persistence",
    "T1176": "persistence",
    "T1556": "persistence",
    "T1133": "persistence",
    # Privilege Escalation
    "T1548": "privilege-escalation",
    "T1134": "privilege-escalation",
    "T1484": "privilege-escalation",
    "T1611": "privilege-escalation",
    "T1068": "privilege-escalation",
    "T1055": "privilege-escalation",
    "T1078": "privilege-escalation",
    # Defense Evasion
    "T1140": "defense-evasion",
    "T1070": "defense-evasion",
    "T1036": "defense-evasion",
    "T1027": "defense-evasion",
    "T1562": "defense-evasion",
    "T1564": "defense-evasion",
    "T1112": "defense-evasion",
    "T1218": "defense-evasion",
    "T1222": "defense-evasion",
    "T1553": "defense-evasion",
    "T1578": "defense-evasion",
    "T1497": "defense-evasion",
    "T1622": "defense-evasion",
    "T1480": "defense-evasion",
    "T1202": "defense-evasion",
    "T1205": "defense-evasion",
    "T1207": "defense-evasion",
    "T1211": "defense-evasion",
    "T1216": "defense-evasion",
    "T1220": "defense-evasion",
    "T1221": "defense-evasion",
    "T1562": "defense-evasion",
    "T1612": "defense-evasion",
    "T1620": "defense-evasion",
    "T1647": "defense-evasion",
    "T1656": "defense-evasion",
    # Credential Access
    "T1003": "credential-access",
    "T1110": "credential-access",
    "T1555": "credential-access",
    "T1552": "credential-access",
    "T1558": "credential-access",
    "T1557": "credential-access",
    "T1539": "credential-access",
    "T1528": "credential-access",
    "T1111": "credential-access",
    "T1040": "credential-access",
    "T1056": "credential-access",
    "T1187": "credential-access",
    "T1606": "credential-access",
    "T1621": "credential-access",
    "T1649": "credential-access",
    # Discovery
    "T1082": "discovery",
    "T1083": "discovery",
    "T1087": "discovery",
    "T1016": "discovery",
    "T1018": "discovery",
    "T1046": "discovery",
    "T1049": "discovery",
    "T1057": "discovery",
    "T1069": "discovery",
    "T1033": "discovery",
    "T1007": "discovery",
    "T1120": "discovery",
    "T1124": "discovery",
    "T1135": "discovery",
    "T1201": "discovery",
    "T1217": "discovery",
    "T1482": "discovery",
    "T1518": "discovery",
    "T1526": "discovery",
    "T1580": "discovery",
    "T1613": "discovery",
    "T1614": "discovery",
    "T1619": "discovery",
    "T1622": "discovery",
    "T1652": "discovery",
    "T1654": "discovery",
    "T1010": "discovery",
    "T1497": "discovery",
    # Lateral Movement
    "T1021": "lateral-movement",
    "T1091": "lateral-movement",
    "T1210": "lateral-movement",
    "T1534": "lateral-movement",
    "T1550": "lateral-movement",
    "T1563": "lateral-movement",
    "T1570": "lateral-movement",
    "T1080": "lateral-movement",
    "T1428": "lateral-movement",
    # Collection
    "T1005": "collection",
    "T1025": "collection",
    "T1039": "collection",
    "T1074": "collection",
    "T1113": "collection",
    "T1114": "collection",
    "T1115": "collection",
    "T1119": "collection",
    "T1123": "collection",
    "T1125": "collection",
    "T1213": "collection",
    "T1530": "collection",
    "T1560": "collection",
    "T1602": "collection",
    "T1056": "collection",
    "T1185": "collection",
    "T1557": "collection",
    # Command and Control
    "T1071": "command-and-control",
    "T1090": "command-and-control",
    "T1095": "command-and-control",
    "T1102": "command-and-control",
    "T1104": "command-and-control",
    "T1105": "command-and-control",
    "T1132": "command-and-control",
    "T1219": "command-and-control",
    "T1568": "command-and-control",
    "T1571": "command-and-control",
    "T1572": "command-and-control",
    "T1573": "command-and-control",
    "T1001": "command-and-control",
    "T1008": "command-and-control",
    "T1659": "command-and-control",
    "T1665": "command-and-control",
    # Exfiltration
    "T1020": "exfiltration",
    "T1029": "exfiltration",
    "T1030": "exfiltration",
    "T1041": "exfiltration",
    "T1048": "exfiltration",
    "T1052": "exfiltration",
    "T1567": "exfiltration",
    "T1011": "exfiltration",
    "T1537": "exfiltration",
    # Impact
    "T1485": "impact",
    "T1486": "impact",
    "T1489": "impact",
    "T1490": "impact",
    "T1491": "impact",
    "T1496": "impact",
    "T1498": "impact",
    "T1499": "impact",
    "T1529": "impact",
    "T1531": "impact",
    "T1561": "impact",
    "T1565": "impact",
    "T1657": "impact",
}


def parent_technique_id(tech_id: str) -> str:
    tid = tech_id.strip().upper()
    if "." in tid:
        return tid.split(".", 1)[0]
    return tid


def tactic_key_for_technique(tech_id: str) -> str:
    tid = tech_id.strip().upper()
    parent = parent_technique_id(tid)
    # ICS / OT technique range (rough): T08xx
    if parent.startswith("T08"):
        return "ics"
    key = _TECHNIQUE_PRIMARY_TACTIC.get(parent)
    if key:
        return key
    # Sub-technique may be listed without parent — try exact
    key = _TECHNIQUE_PRIMARY_TACTIC.get(tid)
    if key:
        return key
    return "unmapped"


def all_tactics() -> list[dict[str, str]]:
    return [*ENTERPRISE_TACTICS, ICS_TACTIC, UNMAPPED_TACTIC]
