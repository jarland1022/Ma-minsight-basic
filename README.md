# MA-MinSight

基于 AI Agent 的通用安全告警分诊与研判系统。

## 阶段 10 交付物（Docker / ECS）

```bash
cp deploy/env/production.env.example .env
# 编辑 POSTGRES_PASSWORD、API_KEY、JWT_SECRET 等

docker compose up -d --build
./deploy/scripts/smoke-test.sh
```

- `docker-compose.yml` — postgres + redis + app + nginx
- `deploy/docker/` — Dockerfile、entrypoint（自动 migrate）
- `deploy/nginx/` — 同源反代 + SSL 示例
- `deploy/scripts/` — backup / restore / smoke-test
- `docs/ecs-deployment-phase10.md` — ECS runbook

详见 [`docs/ecs-deployment-phase10.md`](docs/ecs-deployment-phase10.md)。

## 业务人员使用说明

- Web 控制台左侧 **「使用指南」**：面向非安全专家的在线帮助（协查怎么写、结论含义、FAQ）。
- 完整手册：[`docs/MA-MinSight-操作说明.docx`](docs/MA-MinSight-操作说明.docx)（v0.2.0 起增加「业务人员快速上手」专章）。
- 重新生成手册：`py -3 scripts/generate_operations_manual_zh.py`

### ECS-A：HTTPS 6443（公网 IP 访问）

若通过 `https://<公网IP>:6443/` 访问，**不能**只用 `docker compose up --build`，否则会丢失 6443 端口与 SSL 配置。

```bash
# .env 中需包含：
# HTTP_PORT=8080
# COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml:docker-compose.ecs-a.yml

# 证书（勿提交 git）：
# deploy/nginx/certs/fullchain.pem
# deploy/nginx/certs/privkey.pem
#
# 无证书时（IP 访问，浏览器会提示不安全）：
# ./deploy/scripts/gen-self-signed-certs.sh 120.79.165.121
# 或一步生成并启动：
# ./deploy/scripts/up-ecs-a.sh --self-signed 120.79.165.121

chmod +x deploy/scripts/up-ecs-a.sh deploy/scripts/gen-self-signed-certs.sh
./deploy/scripts/up-ecs-a.sh

# 验收
curl -k https://127.0.0.1:6443/health/ready
docker compose ps   # nginx 应显示 0.0.0.0:6443->443/tcp
```

## 阶段 9 交付物

- `app/eval/` — 回归集、链路探针、Mock LLM、ProbeInject
- `app/api/routes/regression.py` / `health_checks.py`
- `app/scheduler/eval_jobs.py`
- `alembic/versions/010_eval_seed.py`
- `docs/regression-health-phase9.md`
- Web「评测」页 + Dashboard 评测健康条

## 阶段 8 交付物

- `web/` — React + Ant Design 控制台
- `app/console/` + `app/api/routes/auth|dashboard|events|...`
- `app/services/auth.py` — JWT 双轨认证
- `deploy/nginx.ma-minsight.conf.example`
- `alembic/versions/009_console_seed.py`
- `docs/web-console-phase8.md`

## 阶段 7 交付物

- `app/defense_assets/` — AssetPipeline、判例/候选/处置/升格
- `app/scheduler/defense_asset_jobs.py` — 5 分钟调度
- `app/api/routes/defense_assets.py`
- `alembic/versions/007_defense_asset_seed.py` / `008_pgvector_extension.py`
- `docs/defense-assets-phase7.md`

## 阶段 6 交付物

- `app/human_review/` — 企微 outbound/inbound、协查 dispatch、Agent 复跑触发
- `app/scheduler/human_review_jobs.py` — 2 分钟调度
- `app/api/routes/human_review.py` / `audit_samples.py`
- `alembic/versions/006_human_review_seed.py`
- `docs/human-review-phase6.md`

## 阶段 5 交付物

- `app/skills/` — query_asset / query_history_alerts / query_threat_intel + submit_conclusion
- `app/agent/` — ReAct loop、orchestrator、prompts、日预算
- `app/api/routes/investigations.py`
- `alembic/versions/005_investigation_seed.py` — 配置 + brute_force SOP
- `docs/investigation-phase5.md`

## 阶段 4 交付物

- `app/aggregation/` — 事件聚合（Option B 键、并入/新建、queue_priority）
- `app/scheduler/aggregation_jobs.py` — 2 分钟定时聚合
- `app/api/routes/aggregation.py` — run / stats / event 详情
- `alembic/versions/004_event_aggregation.py`
- `docs/aggregation-phase4.md`

## 阶段 3 交付物

- `app/triage/` — 固定分诊流水线（去重/白名单/画像参考/规则分/LLM/路由）
- `app/scheduler/triage_jobs.py` — 2 分钟定时 triage
- `app/api/routes/triage.py` — 手动触发 / 统计 / 详情
- `docs/triage-phase3.md`

## 快速开始（数据库）

- `app/ingestion/` — 适配器框架、Wazuh Indexer、Mock、IngestService
- `app/api/routes/ingestion.py` — 最小 ingestion API
- `app/scheduler/ingestion_jobs.py` — APScheduler 5 分钟轮询
- `app/ingestion/lock.py` — Redis 分布式锁
- `docs/ingestion-phase2.md` — 配置与字段映射

## 快速开始（数据库）

```bash
cp .env.example .env
# 编辑 DATABASE_URL / REDIS_URL / API_KEY / WAZUH_INDEXER_*

pip install -e ".[dev]"
alembic upgrade head
pytest tests/ -q
```

## 启动 API + 调度

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 启动 Web 控制台（开发）

```bash
cd web && npm install && npm run dev
# 浏览器 http://localhost:5173
# 使用环境变量 ADMIN_INITIAL_PASSWORD 设置的管理员密码登录（生产禁止弱口令）
```

## 手动拉取

```bash
python -m app.ingestion.cli pull --source wazuh
curl -X POST http://localhost:8000/api/v1/ingestion/sources/{id}/pull -H "X-API-Key: $API_KEY"
```

## 威胁情报同步

从近 7 天告警中的外网 IP 拉取 AbuseIPDB / GreyNoise 结果，写入 `threat_intel_entries` 供 Agent `query_threat_intel` 使用。

```bash
# .env 至少配置 ABUSEIPDB_API_KEY 或 GREYNOISE_API_KEY
ma-ti-sync
ma-ti-sync --ip 203.0.113.1 --force
./deploy/scripts/sync-threat-intel.sh
```

Docker 部署后需重建 app 镜像以安装 `ma-ti-sync` 入口；改 `.env` 后 `docker compose up -d --force-recreate app`。

## 资产画像入库

PostgreSQL enum 标签为大写（`HOST`/`IP`），勿直接写小写 SQL。推荐 ORM 脚本：

```bash
./deploy/scripts/seed-entity-assets.sh
# 或
docker compose exec app ma-entity-seed
```

## 单租户部署说明

每台 ECS 独立部署一套实例，数据保留在客户侧，无需 `tenant_id`。

## 事件聚合键（已确认）

`host_name + user_name + alert_category + 24h 窗口`，见 `events` 表聚合维度字段。
