# 阶段 10 设计方案：ECS 部署（Docker Compose + 运维文档）

> **本阶段边界**：提供**可一键本地/ECS 拉起**的容器化交付物 + **单租户 ECS 部署/runbook 文档**；补齐生产 `.env` 模板、Nginx/TLS、安全组、备份与上线验收清单。**不做** K8s Helm、多租户 SaaS、Celery worker 拆分（保留扩展说明）、Terraform/IaC 自动化。  
> **方法论呼应**：单租户「数据留在客户侧」→ 每台 ECS 独立 Compose 栈；任务书要求 **Docker Compose（app/postgres/redis/nginx）** + **Nginx 与安全组**；阶段 9 的 `/health/ready` 与链路探针作为**上线门禁**。

---

## 一、阶段目标与验收标准

| 目标 | 验收标准 |
|------|---------|
| Docker Compose 全栈 | `docker compose up -d` 后 Web + API + 调度可跑通 |
| 数据库迁移 | 容器启动自动 `alembic upgrade head`（幂等） |
| 前端同源 | Nginx 提供 `/` 静态 + `/api` 反代（延续阶段 8） |
| pgvector | Postgres 镜像支持 `008_pgvector_extension` 迁移 |
| ECS 文档 | 阿里云 ECS（或等价 VM）从 0 到生产的步骤文档 |
| 安全 | 安全组最小暴露、JWT/API Key、密钥仅 env、禁止 8000 公网 |
| 运维 | 备份/恢复、日志、升级、故障排查、验收脚本 |
| 验收 | 文档清单：ingest → triage → … → Web 登录 + `health-check run` |

**本阶段不做**：拆分 worker 进程、K8s、RDS/ElastiCache 托管版 IaC（文档中作可选架构说明）。

---

## 二、与现有架构的衔接

当前 **APScheduler 内嵌于 `uvicorn app.main:app` lifespan**（ingestion/triage/aggregation/investigate/human_review/defense_assets/eval），阶段 10 **不拆 worker**，单 `app` 容器即可，与现码零改动。

```text
┌─────────────────────────────────────────────────────────┐
│  ECS / VM (单租户)                                       │
│  ┌──────────┐   ┌─────────────────────────────────────┐ │
│  │  nginx   │──▶│  app (FastAPI + APScheduler)        │ │
│  │  :443    │   │  :8000  internal only               │ │
│  │  static  │   └──────────┬──────────────┬───────────┘ │
│  └──────────┘              │              │             │
│                     ┌──────▼──┐    ┌──────▼──┐          │
│                     │ postgres │    │  redis  │          │
│                     │  :5432   │    │  :6379  │          │
│                     │ internal │    │ internal│          │
│                     └──────────┘    └─────────┘          │
└─────────────────────────────────────────────────────────┘
         ▲
    安全组：仅 443(或80) 对运维/VPN；22 限源 IP
    Wazuh Indexer / DeepSeek API：出站 HTTPS
```

---

## 三、Docker Compose 拓扑（推荐）

### 3.1 服务清单

| 服务 | 镜像/构建 | 端口 | 说明 |
|------|-----------|------|------|
| `postgres` | `pgvector/pgvector:pg16` 或 `postgres:16` + ext | 5432 内部 | 数据卷 `pgdata` |
| `redis` | `redis:7-alpine` | 6379 内部 | 可选 AOF |
| `app` | `Dockerfile` multi-stage | 8000 内部 | uvicorn + scheduler |
| `nginx` | `nginx:1.27-alpine` + 内置 `web/dist` | 80/443 对外 | 同源反代 |

可选 **`migrate` one-shot**（见决策 7）：仅 `alembic upgrade head` 后退出。

### 3.2 `app` Dockerfile（multi-stage 要点）

```dockerfile
# stage: web-build
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# stage: python
FROM python:3.11-slim AS app
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
RUN pip install --no-cache-dir -e .
COPY --from=web /web/dist /app/static   # 若 nginx 不单独挂载 dist

COPY deploy/docker/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> **推荐**：`web/dist` 由 **nginx 镜像** COPY（3A），`app` 仅 API。

### 3.3 `docker-compose.yml` 骨架

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: ma_minsight
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ma_minsight
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ma_minsight -d ma_minsight"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

  app:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://ma_minsight:${POSTGRES_PASSWORD}@postgres:5432/ma_minsight
      SYNC_DATABASE_URL: postgresql://ma_minsight:${POSTGRES_PASSWORD}@postgres:5432/ma_minsight
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    expose:
      - "8000"
    restart: unless-stopped

  nginx:
    build:
      context: .
      dockerfile: deploy/docker/Dockerfile.nginx
    ports:
      - "${HTTP_PORT:-80}:80"
    depends_on:
      - app
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
```

### 3.4 Entrypoint（`deploy/docker/entrypoint.sh`）

1. `wait-for` postgres/redis（或 compose healthcheck + retry loop）
2. `alembic upgrade head`
3. （可选）首次启动检测无 admin 用户 → 依赖 `009` 迁移 + `ADMIN_INITIAL_PASSWORD`
4. `exec uvicorn ...`

---

## 四、ECS 部署文档结构（`docs/ecs-deployment-phase10.md`）

### 4.1 推荐规格（单租户中小规模）

| 资源 | 最低 | 推荐 | 说明 |
|------|------|------|------|
| ECS | 2C4G | 4C8G | Agent 调查 + PG 同机 |
| 系统盘 | 40GB | 80GB SSD | 含 Docker 镜像 + PG 数据 |
| 带宽 | 按量 5Mbps | 10Mbps | Wazuh 拉取 + LLM API |
| OS | Ubuntu 22.04 / Alibaba Cloud Linux 3 | | Docker CE + Compose v2 |

### 4.2 部署步骤（摘要）

1. 安装 Docker CE + Compose plugin  
2. 克隆/上传发布包，`cp deploy/env/production.env.example .env`  
3. 生成强密钥：`API_KEY`、`JWT_SECRET`（≥32 字节）、`POSTGRES_PASSWORD`  
4. `docker compose build && docker compose up -d`  
5. 安全组：**仅开放 443**（或 80→301 跳转）；**禁止** 5432/6379/8000 入站  
6. 配置 Wazuh Indexer 出站、DeepSeek API Key、企微回调 URL  
7. **上线验收**（见 §六）

### 4.3 安全组规则（示例）

| 方向 | 协议 | 端口 | 源/目标 | 说明 |
|------|------|------|---------|------|
| 入站 | TCP | 443 | 运维网段 / VPN | Web 控制台 |
| 入站 | TCP | 22 | 堡垒机 IP | SSH 运维 |
| 入站 | * | * | 0.0.0.0/0 | **拒绝** DB/Redis/API |
| 出站 | TCP | 443 | 0.0.0.0/0 | LLM / Wazuh / 企微 |
| 出站 | TCP | 9200 | Wazuh Indexer 网段 | 按客户 SIEM |

### 4.4 TLS

- **方案 A**：ECS 上 Nginx + Certbot（Let’s Encrypt 或客户证书）  
- **方案 B**：前置 SLB/ALB + 证书，后端 HTTP → nginx:80  
- 文档两种都写，默认 **Certbot + nginx**（国内可用客户上传证书）

### 4.5 企微回调

- 公网 URL：`https://ma-minsight.customer.com/api/v1/human-review/wecom/callback`  
- 需在企微后台配置，与 `WECOM_*` 环境变量一致

---

## 五、运维 Runbook（交付物）

| 主题 | 内容 |
|------|------|
| 日常 | `docker compose ps`、Dashboard、pipeline last_run |
| 日志 | `docker compose logs -f app`、日志级别、敏感字段不落盘策略 |
| 备份 | `pg_dump` 定时任务脚本 `deploy/scripts/backup-postgres.sh` |
| 恢复 | `restore-postgres.sh` + compose down/up |
| 升级 | 拉新镜像 → `compose up -d --build` → 自动 migrate |
| 回滚 | 保留上一版镜像 tag + DB 备份 |
| 扩缩 | 单 ECS 垂直扩容；水平拆分见「未来 worker/RDS」附录 |

---

## 六、上线验收清单（Gate）

```bash
# 1. 就绪探针
curl -fsS http://127.0.0.1/health/ready   # 经 nginx 或直连 app

# 2. 登录 Web（改默认密码）
# admin → 强制改密（文档要求，可选 010 后脚本）

# 3. 链路探针（阶段 9）
curl -X POST https://ma-minsight.example.com/api/v1/health-checks/run \
  -H "Authorization: Bearer $TOKEN"

# 4. Mock 接入源 pull（无 Wazuh 时）
curl -X POST .../api/v1/console/run/triage

# 5. 安全：8000/5432 从公网不可达（nmap 自测）
```

---

## 七、目录结构（新增）

```text
deploy/
  docker/
    Dockerfile              # app 镜像
    Dockerfile.nginx        # nginx + web/dist
    entrypoint.sh
    wait-for-it.sh          # 或 compose healthcheck 足够则省略
  nginx/
    ma-minsight.conf             # 生产 nginx（由 example 升级）
    ma-minsight.ssl.conf.example
  env/
    production.env.example  # 生产 .env 模板（不含真实密钥）
  scripts/
    backup-postgres.sh
    restore-postgres.sh
    smoke-test.sh           # 调用 /health/ready + health-check
  security/
    security-group.md       # 安全组说明
docker-compose.yml
docker-compose.prod.yml     # 可选 override（资源 limit、日志驱动）
docs/
  ecs-deployment-phase10.md # 主文档
```

---

## 八、环境变量（生产模板要点）

在 `.env.example` 基础上，`deploy/env/production.env.example` 强调：

```bash
POSTGRES_PASSWORD=          # compose 注入
HTTP_PORT=80
# 必须修改
API_KEY=
JWT_SECRET=                   # ≥32 chars
ADMIN_INITIAL_PASSWORD=       # 首次登录后改密
DEEPSEEK_API_KEY=
WAZUH_INDEXER_USER=
WAZUH_INDEXER_PASSWORD=
# 可选
HEALTH_ALERT_WEBHOOK_URL=     # 或 eval.alert_webhook_url
```

Compose 内 **DATABASE_URL/REDIS_URL 由 compose 覆盖**，避免 localhost 硬编码。

---

## 九、可选架构（文档附录，不实现）

| 模式 | 适用 | 变更 |
|------|------|------|
| 单机 Compose | POC / 中小客户 | 本阶段默认 |
| ECS + RDS + Redis 云服务 | 大规模 / 合规 | 仅改 env 端点，Compose 去掉 postgres/redis |
| app + worker 拆分 | 调度与 API 分离 | 需代码：scheduler 仅 worker 启动 |

---

## 十、测试与 CI（轻量）

| 项 | 说明 |
|----|------|
| `docker compose config` | CI 校验 compose 语法 |
| `docker build` | 可选 GitHub Action / 本地 |
| `deploy/scripts/smoke-test.sh` | 部署后人工/CI 调用 |

不强制本阶段加 GitHub Actions（可 8B 仅文档）。

---

## 十一、待确认项（8 项）

请回复如 `1A 2A 3A ...` 格式。

### 1. 应用容器拓扑

| 选项 | 说明 |
|------|------|
| **1A** | **单 `app` 容器**（API + APScheduler，与现码一致）（推荐） |
| **1B** | `app` + `worker` 双容器（需改 lifespan 拆分 scheduler） |
| **1C** | Compose profile：`default=1A`，`worker` profile 预留空服务 |

### 2. Compose 服务范围

| 选项 | 说明 |
|------|------|
| **2A** | postgres + redis + app + nginx 四服务（推荐） |
| **2B** | postgres + redis + app（nginx 装宿主机） |
| **2C** | 仅 app + nginx（DB/Redis 用云托管，compose 不含） |

### 3. 前端静态资源

| 选项 | 说明 |
|------|------|
| **3A** | **nginx 镜像 multi-stage 构建** `web/dist`（推荐） |
| **3B** | 宿主机 volume 挂载 `web/dist` |
| **3C** | app 容器顺带挂载 static（FastAPI 不提供静态，需 nginx） |

### 4. PostgreSQL 镜像

| 选项 | 说明 |
|------|------|
| **4A** | `pgvector/pgvector:pg16` 官方镜像（推荐） |
| **4B** | `postgres:16` + 启动脚本 `CREATE EXTENSION` |
| **4C** | 文档不写 compose PG，仅 RDS 连接说明 |

### 5. ECS 文档主场景

| 选项 | 说明 |
|------|------|
| **5A** | **单机 ECS 全栈 Compose**（推荐默认章节） |
| **5B** | 仅云托管 DB/Redis + ECS 跑 app/nginx |
| **5C** | **5A 主文档 + 5B 附录**（推荐） |

### 6. HTTPS

| 选项 | 说明 |
|------|------|
| **6A** | Nginx + 客户证书 / Certbot 文档 + `ma-minsight.ssl.conf.example`（推荐） |
| **6B** | 仅 HTTP（内网 POC），生产必须前置 SLB |
| **6C** | SLB/ALB 终止 TLS，后端 HTTP |

### 7. 数据库迁移时机

| 选项 | 说明 |
|------|------|
| **7A** | **app entrypoint 每次启动 `alembic upgrade head`**（推荐） |
| **7B** | 独立 `docker compose run migrate` one-shot job |
| **7C** | 7A + compose `depends_on` 等 PG healthy 后再 migrate |

### 8. 交付物深度

| 选项 | 说明 |
|------|------|
| **8A** | Compose + Dockerfile + 脚本 + 完整 ECS/runbook 文档（推荐） |
| **8B** | **仅文档**（无 Dockerfile，客户自行安装 Python） |
| **8C** | 8A + systemd 裸机备选 + 备份 cron 示例 |

---

## 十二、默认推荐组合

**1A 2A 3A 4A 5C 6A 7C 8A**

确认后实现顺序：

1. `deploy/docker/Dockerfile` + `Dockerfile.nginx` + `entrypoint.sh`  
2. 根目录 `docker-compose.yml` + `production.env.example`  
3. 升级 `deploy/nginx/ma-minsight.conf`（含 `/health/ready` 可选直连）  
4. `deploy/scripts/{backup,restore,smoke-test}.sh`  
5. `docs/ecs-deployment-phase10.md` + README 部署章节  
6. （可选）CI `docker compose config`  

---

## 十三、与全阶段交付的关系

阶段 10 完成后，客户侧标准路径：

```text
docker compose up -d
  → migrate + seed
  → https://host/ 登录
  → 配置 Wazuh data_source
  → health-check run 通过
  → 生产 ingest/triage/… 调度自动运行
```

**任务书阶段 1–10 闭环。**
