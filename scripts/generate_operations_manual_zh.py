#!/usr/bin/env python3
"""Generate docs/MA-MinSight-操作说明.docx (Chinese operations manual)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "MA-MinSight-操作说明.docx"


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def add_para(doc: Document, text: str, *, bold: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def add_numbered(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Number")


def build_document() -> Document:
    doc = Document()
    title = doc.add_heading("MA-MinSight 安全告警分诊与研判系统", 0)
    title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    sub = doc.add_paragraph("操作说明与运维手册")
    sub.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    meta = doc.add_paragraph(f"版本：0.2.0    文档日期：{date.today().isoformat()}")
    meta.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    add_heading(doc, "文档导读", 1)
    add_para(
        doc,
        "本手册面向两类读者：① 日常处理告警的业务/运维人员（无需深厚安全背景）；"
        "② 负责部署与排障的管理员。若您刚接触本系统，请先阅读第 2 章「业务人员快速上手」。",
    )

    add_heading(doc, "目录（摘要）", 2)
    add_numbered(
        doc,
        [
            "业务人员快速上手（必读）",
            "系统简介与核心概念",
            "数据处理流水线概览",
            "Web 控制台操作指南（含人工协查）",
            "防御资产与处置确认",
            "部署与初始化（管理员）",
            "数据库与配置参考（管理员）",
            "故障排查",
            "附录",
        ],
    )

    # Chapter 2 - Quick start for operators
    add_heading(doc, "1. 业务人员快速上手（必读）", 1)
    add_para(doc, "MA-MinSight 帮您做三件事：把 Wazuh 等设备的告警自动整理成「事件」、用 AI 查背景并给结论、在需要时向您提问补充业务信息。", bold=True)
    add_heading(doc, "1.1 您每天只需关注两个数字", 2)
    add_bullets(
        doc,
        [
            "仪表盘「协查中」> 0 → 打开左侧「人工协查」，用白话回复 AI 的问题。",
            "仪表盘「待处置建议」> 0 → 打开「防御资产」，阅读建议后点确认或拒绝。",
        ],
    )
    add_heading(doc, "1.2 四步处理流程", 2)
    add_numbered(
        doc,
        [
            "登录控制台，看仪表盘是否有「协查中」或「待处置建议」。",
            "有协查中：进入「人工协查」，阅读 AI 问题，用日常语言回复（见 1.3 示例），点击提交。",
            "等待 3–5 分钟（或请管理员手动运行「Agent 调查」），到「事件队列 → 已结论」查看 AI 最终判断。",
            "若 AI 给出处置建议：到「防御资产」确认或拒绝；真实封禁/隔离需在防火墙等设备上由运维执行。",
        ],
    )
    add_heading(doc, "1.3 协查回复示例（可直接改写使用）", 2)
    add_bullets(
        doc,
        [
            "确认误报：源 IP 10.1.2.3 是我司绿盟漏洞扫描器，当晚有例行扫描任务，已报备。",
            "确认业务行为：用户 zhangsan 是运维账号，该时段在执行批量补丁脚本，属正常变更窗口。",
            "补充信息：该主机为测试环境，无生产数据，可接受较高探测频率。",
            "暂无法确认：已联系业务负责人核实，预计 2 小时内回复。",
        ],
    )
    add_heading(doc, "1.4 常见误解（请务必了解）", 2)
    add_bullets(
        doc,
        [
            "没有「误报 / 真实攻击」人工直判按钮——您补充事实，AI 复跑后给出结论。",
            "「确认处置」不会在系统外自动封 IP 或隔离主机，仅作审批与审计记录。",
            "协查问题若出现 LLM 404 等系统报错，属于 AI 服务配置问题，请联系管理员修复 DEEPSEEK 配置。",
            "看不懂 verdict 英文时，可在 Web「使用指南」页查看中文对照表。",
        ],
    )

    add_heading(doc, "2. 系统简介与核心概念", 1)
    add_heading(doc, "2.1 一条告警如何变成您看到的事件", 2)
    add_para(doc, "Wazuh 告警 → 入库 → 机器初筛 → 合并为 Event → AI 调查 →（可选）人工协查 → 结论 → 防御资产沉淀")
    add_heading(doc, "2.2 关键名词（白话）", 2)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "术语"
    hdr[1].text = "白话解释"
    rows = [
        ("告警 Alert", "安全设备报出的一条原始记录"),
        ("事件 Event", "多条相似告警合并后的调查单"),
        ("初筛", "机器先过滤明显低风险告警，减少打扰"),
        ("Agent 调查", "AI 查资产、历史、情报后给出结构化结论"),
        ("协查", "AI 向您提问，您用业务语言补充"),
        ("verdict 结论", "AI 判断：确认攻击 / 大概率误报 / 信息不足 / 需人工复核"),
        ("防御资产", "白名单候选、处置建议等需您确认的记录"),
    ]
    for a, b in rows:
        cells = table.add_row().cells
        cells[0].text = a
        cells[1].text = b

    add_heading(doc, "3. 数据处理流水线概览", 1)
    add_para(doc, "系统每 2–5 分钟自动运行各阶段。管理员可在「设置 → 手动运行流水线」按顺序触发。")
    add_bullets(
        doc,
        [
            "告警入库：从 Wazuh Indexer 拉取新告警",
            "初筛分诊：打分并决定归档或进入深度调查",
            "事件聚合：合并为 Event",
            "Agent 调查：AI 深度分析",
            "协查派发：向 Web/企微下发待回复问题",
            "防御资产沉淀：生成判例、白名单候选、处置建议",
        ],
    )

    add_heading(doc, "4. Web 控制台操作指南", 1)
    add_heading(doc, "4.1 菜单说明", 2)
    menu = doc.add_table(rows=1, cols=3)
    menu.style = "Table Grid"
    menu.rows[0].cells[0].text = "菜单"
    menu.rows[0].cells[1].text = "谁常用"
    menu.rows[0].cells[2].text = "做什么"
    for m, who, what in [
        ("仪表盘", "所有人", "看待办数量、流水线是否运行"),
        ("事件队列", "所有人", "按状态浏览事件，进入详情"),
        ("人工协查", "业务/运维", "回复 AI 问题（核心操作）"),
        ("防御资产", "业务/运维", "确认白名单、处置、推演"),
        ("使用指南", "所有人", "在线帮助与 FAQ"),
        ("设置", "管理员", "手动跑流水线、改配置"),
        ("评测", "管理员", "回归测试与链路探针"),
    ]:
        r = menu.add_row().cells
        r[0].text = m
        r[1].text = who
        r[2].text = what

    add_heading(doc, "4.2 人工协查详细步骤", 2)
    add_numbered(
        doc,
        [
            "确认仪表盘「协查中」> 0；若人工协查页为空，请管理员执行「协查派发」。",
            "打开「人工协查」，阅读每条「AI 想了解的问题」。",
            "在回复框用白话描述您知道的情况（谁、什么系统、是否授权、是否例行）。",
            "点击「提交回复」。",
            "3–5 分钟后刷新「事件详情」或查看「已结论」列表中的 verdict。",
        ],
    )
    add_heading(doc, "4.3 AI 结论（verdict）中文对照", 2)
    vt = doc.add_table(rows=1, cols=3)
    vt.style = "Table Grid"
    vt.rows[0].cells[0].text = "verdict"
    vt.rows[0].cells[1].text = "中文"
    vt.rows[0].cells[2].text = "您该做什么"
    for code, zh, act in [
        ("attack_confirmed", "确认攻击", "阅读推理，在防御资产确认处置建议；高影响操作与运维/业务负责人沟通"),
        ("likely_false_positive", "大概率误报", "若同意，可确认白名单候选减少重复告警"),
        ("insufficient_information", "信息不足", "到人工协查补充事实"),
        ("needs_human_review", "需人工复核", "同上，补充业务背景"),
    ]:
        c = vt.add_row().cells
        c[0].text = code
        c[1].text = zh
        c[2].text = act

    add_heading(doc, "4.4 事件状态说明", 2)
    st = doc.add_table(rows=1, cols=2)
    st.style = "Table Grid"
    st.rows[0].cells[0].text = "状态"
    st.rows[0].cells[1].text = "含义"
    for s, d in [
        ("pending_review", "待调查，等 AI 自动分析"),
        ("investigating", "AI 正在调查"),
        ("human_pending", "等您协查回复"),
        ("concluded", "AI 已给结论"),
        ("closed", "流程结束"),
    ]:
        c = st.add_row().cells
        c[0].text = s
        c[1].text = d

    add_heading(doc, "5. 防御资产与处置确认", 1)
    add_bullets(
        doc,
        [
            "白名单候选：多次确认后自动生成白名单规则，减少误报重复出现。",
            "待确认处置：AI 的运维建议；确认=记录您同意，拒绝=不采纳；均不会自动执行。",
            "处置推演审批：AI 模拟封禁/隔离影响；批准仅表示认可评估，仍不自动执行。",
        ],
    )

    add_heading(doc, "6. 部署与初始化（管理员）", 1)
    add_numbered(
        doc,
        [
            "git clone 到 /opt/minsight && cp deploy/env/production.env.example .env",
            "配置 POSTGRES_PASSWORD、API_KEY、JWT_SECRET、WAZUH_INDEXER_*、DEEPSEEK_API_KEY",
            "docker compose up -d --build 或 ECS-A 使用 ./deploy/scripts/up-ecs-a.sh",
            "./deploy/scripts/smoke-test.sh 验收",
            "docker compose exec app ma-entity-seed 初始化资产画像",
        ],
    )
    add_heading(doc, "6.1 ECS-A + ECS-B 架构", 2)
    add_para(doc, "ECS-A 运行 MA-MinSight（6443 HTTPS）；ECS-B 运行 Wazuh Indexer。data_sources 中 indexer_url 必须填 ECS-B 内网地址，不能写 127.0.0.1。")

    add_heading(doc, "7. 故障排查（精选）", 1)
    add_heading(doc, "7.1 人工协查页为空", 2)
    add_bullets(
        doc,
        [
            "仪表盘「协查中」是否为 0——为 0 则尚无待协查事件。",
            "大于 0 但 inbox 为空——执行「设置 → 协查派发」；未配企微时系统仍应写入 Web inbox。",
        ],
    )
    add_heading(doc, "7.2 Agent 调查 LLM 404", 2)
    add_bullets(
        doc,
        [
            "检查 .env 中 DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL（应为 https://api.deepseek.com，勿带多余路径）。",
            "修改后 docker compose up -d --force-recreate app",
        ],
    )
    add_heading(doc, "7.3 告警不增长", 2)
    add_para(doc, "见 Web「设置 → 告警入库故障排查」；确认 Wazuh 连接、游标、Indexer 是否有新数据。")

    add_heading(doc, "8. 附录", 1)
    add_para(doc, "Web 在线帮助：控制台左侧「使用指南」菜单。")
    add_para(doc, "技术文档：docs/ecs-deployment-phase10.md、docs/human-review-phase6.md、docs/minsight-phase2-enhancement-checklist.md")
    add_para(doc, "升级：git pull && ./deploy/scripts/up-ecs-a.sh；entrypoint 自动 alembic upgrade head。")

    # Set default font size for body
    style = doc.styles["Normal"]
    style.font.size = Pt(11)
    return doc


def main() -> None:
    import shutil
    import tempfile

    doc = build_document()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        doc.save(tmp_path)
        shutil.copy2(tmp_path, OUTPUT)
        print(f"Wrote {OUTPUT}")
    except PermissionError:
        fallback = OUTPUT.with_name("MA-MinSight-操作说明-v0.2.0.docx")
        shutil.copy2(tmp_path, fallback)
        print(f"Target locked; wrote {fallback} (close Word and rename to replace original)")
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
