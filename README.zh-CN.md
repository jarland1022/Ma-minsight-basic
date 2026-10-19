# MA-MinSight 社区版

[English](README.md) | **中文**

自托管的 **SIEM 告警分诊控制台（开源社区版）**。对接 Wazuh（或同类）告警后，完成：

**入库 → 规则初筛 → 事件聚合 → 控制台查看**（含技能库 / ATT&CK 覆盖视图）

专业版（AI Agent 深度研判、企微人工协查、防御资产闭环、评测与商用支持）**通过 License 解锁**，不在「免费默认可跑」范围。联系：微信 `jarlandliu`，邮箱 `jarland@mingansec.com`。对照：[`docs/community-vs-pro.zh-CN.md`](docs/community-vs-pro.zh-CN.md) · [English](docs/community-vs-pro.md)。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Edition](https://img.shields.io/badge/Community-open%20source-brightgreen)](docs/community-vs-pro.zh-CN.md)

仓库：
- GitHub：https://github.com/jarland1022/Ma-minsight-basic
- Gitee：https://gitee.com/jarland/Ma-minsight-basic

> GitHub 默认展示英文 [`README.md`](README.md)。本页为中文说明。  
> 控制台默认 **English**，登录页 / 顶栏可切换 **中文**（浏览器本地记住）。详见 [`docs/i18n.md`](docs/i18n.md)。

## 社区版能做什么

| 能力 | 说明 |
|------|------|
| 自己安装 | Docker Compose / 本地 Python + Vite |
| 告警入库 | Wazuh Indexer / Mock 数据源 |
| 规则初筛 | 降噪、白名单、路由到归档或待聚合；仪表盘噪声规则视图 |
| 事件聚合 | 主机+用户+类别+时间窗 → Event |
| 技能库 | 精选 Playbooks + 社区扩展包；ATT&CK 覆盖看板 |
| 控制台 | 仪表盘、事件队列、使用指南、License（EN/中文可切换） |
| License | 仓库已含验签公钥；导入 `license.lic` 后重启即可升专业版 |

**不含（需专业版 License）：** LLM ReAct Agent、企微协查、防御资产学习、回归/探针评测、厂商驻场与合同交付。

## 快速开始

需要 Docker（推荐）或 Python ≥3.11 + Node 18+、PostgreSQL、Redis。

```bash
git clone https://github.com/jarland1022/Ma-minsight-basic.git
# 国内：git clone https://gitee.com/jarland/Ma-minsight-basic.git
cd Ma-minsight-basic

cp .env.example .env
# 编辑 POSTGRES_PASSWORD、API_KEY、JWT_SECRET 等

docker compose up -d --build
```

| 地址 | 作用 |
|------|------|
| http://127.0.0.1/ （或 `.env` 中 `HTTP_PORT`） | 控制台（nginx） |
| 容器内 `/health` | 应返回 `edition=community` |

默认管理员见 `.env` 的 `ADMIN_INITIAL_PASSWORD`（示例为 `changeme`）。登录后建议：

1. **设置 → 手动运行流水线**：入库 → 初筛 → 聚合  
2. **事件队列** 确认已生成 Event  
3. **技能库** 浏览 Playbooks / ATT&CK 覆盖  

语言：右上角 **EN | 中文**。

### 本地开发（可选）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

cd web && npm install && npm run dev
```

## 升级到专业版

1. 控制台 **系统 → License**，复制机器指纹。  
2. 联系厂商获取 `license.lic`（公钥 `ma-minsight-public.pem` 已在仓库 `configs/license/`）。  
3. 在页面导入 `.lic`，或放到 `configs/license/license.lic`，**重启应用**。  
4. 解锁后：Agent 调查、人工协查、防御资产、评测可用。

社区版**没有**自动 72 小时 Pro 试用；试用授权由厂商按指纹签发。

## 相关文档

- [`docs/community-vs-pro.zh-CN.md`](docs/community-vs-pro.zh-CN.md) — 能力与定价对照  
- [`docs/i18n.md`](docs/i18n.md) — 控制台语言说明  
- [`docs/article-siem-minsight.md`](docs/article-siem-minsight.md) — 介绍文章  
- [`docs/marketing/overseas/`](docs/marketing/overseas/) — **LinkedIn / Upwork 海外获客包**（对标 Ma-WAF；先看 `next-actions.md`）  
- [`docs/marketing/landing.html`](docs/marketing/landing.html) · [`docs/marketing/GITHUB_PAGES.md`](docs/marketing/GITHUB_PAGES.md) — **英文落地页 → GitHub Pages**  
- [Ma-WAF Community](https://github.com/jarland1022/Ma-waf-basic) — 开源 WAF 社区版  

## 许可

Apache License 2.0。详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
