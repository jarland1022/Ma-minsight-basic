# MA-MinSight Community

自托管的 **SIEM 告警分诊控制台（开源社区版）**。对接 Wazuh（或同类）告警后，完成：

**入库 → 规则初筛 → 事件聚合 → 控制台查看**

专业版（AI Agent 深度研判、企微人工协查、防御资产闭环、评测与商用支持）**通过 License 解锁**，不在「免费默认可跑」范围。联系：微信 `jarlandliu`，邮箱 `jarland@mingansec.com`。对照：[`docs/community-vs-pro.md`](docs/community-vs-pro.md)。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

## 社区版能做什么

| 能力 | 说明 |
|------|------|
| 自己安装 | Docker Compose / 本地 Python + Vite |
| 告警入库 | Wazuh Indexer / Mock 数据源 |
| 规则初筛 | 降噪、白名单、路由到归档或待聚合 |
| 事件聚合 | 主机+用户+类别+时间窗 → Event |
| 控制台 | 仪表盘、事件队列、静态技能库（Playbooks）、使用指南 |
| License 页 | 查看指纹、导入专业版 `license.lic` |

**不含（需专业版 License）：** LLM ReAct Agent、企微协查、防御资产学习、回归/探针评测、厂商驻场与合同交付。

## 快速开始

需要 Docker（推荐）或 Python ≥3.11 + Node 18+、PostgreSQL、Redis。

```bash
cp .env.example .env
# 编辑 POSTGRES_PASSWORD、API_KEY、JWT_SECRET 等

docker compose up -d --build
```

| 地址 | 作用 |
|------|------|
| http://127.0.0.1:8080/ | 控制台（经 nginx，以 compose 端口为准） |
| http://127.0.0.1:8000/health | API 健康检查（直连 app 时） |

默认管理员账号以种子数据 / `.env` 为准（见使用指南）。登录后建议先打开 **设置 → 手动运行流水线**：入库 → 初筛 → 聚合。

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

1. 控制台打开 **系统 → License**，复制机器指纹。
2. 联系厂商获取 `ma-minsight-public.pem` + `license.lic`。
3. 将公钥放到 `configs/license/`，在页面导入 `.lic`，**重启应用**。
4. 解锁后：Agent 调查、人工协查、防御资产、评测调度器与 API 可用。

## 目录

```text
app/                 # FastAPI 后端
web/                 # React 控制台
alembic/             # 数据库迁移
deploy/              # Docker / nginx
docs/                # 文档（含社区 vs 专业版）
EDITION              # community
LICENSE / NOTICE     # Apache-2.0
```

## 相关产品

- [Ma-WAF Community](https://github.com/jarland1022/Ma-waf-basic.git) — 开源 WAF 社区版
- SIEM：推荐自建 Wazuh；MinSight 是 SIEM **之上的分诊层**，不是又一个 SIEM。

## 许可

Apache License 2.0。详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
