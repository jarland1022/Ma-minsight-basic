# 阶段 10：ECS 部署（Docker Compose）

## 确认项（1A 2A 3A 4A 5C 6A 7C 8A）

- 单 `app` 容器（FastAPI + APScheduler）
- postgres + redis + app + nginx 四服务 Compose
- nginx 镜像 multi-stage 构建 `web/dist`
- `pgvector/pgvector:pg16`
- ECS 单机文档 + 托管 DB/Redis 附录
- HTTPS：Nginx + SSL 配置示例
- entrypoint 迁移 + compose 等 PG/Redis healthy
- Compose + 脚本 + 完整 runbook

## 快速启动（本地 / ECS）

```bash
cp deploy/env/production.env.example .env
# 编辑 POSTGRES_PASSWORD、API_KEY、JWT_SECRET、ADMIN_INITIAL_PASSWORD

docker compose up -d --build
# 可选生产日志轮转：
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 验收
chmod +x deploy/scripts/smoke-test.sh
export API_KEY=...   # 与 .env 一致
./deploy/scripts/smoke-test.sh
```

浏览器访问 `http://<host>/` ，使用 `.env` 中 `ADMIN_INITIAL_PASSWORD` 配置的管理员密码登录（生产禁止弱口令；首次登录将强制改密与 MFA 绑定）。

## 目录

| 路径 | 说明 |
|------|------|
| `docker-compose.yml` | 四服务栈 |
| `docker-compose.prod.yml` | 日志轮转 override |
| `deploy/docker/Dockerfile` | app 镜像 |
| `deploy/docker/Dockerfile.nginx` | nginx + 前端构建 |
| `deploy/docker/entrypoint.sh` | 等待 DB/Redis + `alembic upgrade head` |
| `deploy/nginx/ma-minsight.conf` | HTTP 同源反代 |
| `deploy/nginx/ma-minsight.ssl.conf.example` | HTTPS 示例 |
| `deploy/env/production.env.example` | 生产 env 模板（含 `PRIVACY_*`；详见 `docs/deploy/privacy-config.md`） |
| `deploy/scripts/` | backup / restore / smoke-test |
| `deploy/security/security-group.md` | 安全组建议 |

## ECS 单机部署步骤

### 1. 规格建议

| 项 | 最低 | 推荐 |
|----|------|------|
| CPU/内存 | 2C4G | 4C8G |
| 磁盘 | 40GB SSD | 80GB SSD |
| OS | Ubuntu 22.04 / Alibaba Cloud Linux 3 | |

### 2. 安装 Docker

```bash
# Ubuntu 示例
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

### 3. 部署应用

```bash
git clone <repo> /opt/ma-minsight && cd /opt/ma-minsight
cp deploy/env/production.env.example .env
nano .env   # 设置强密码与 API Key

docker compose up -d --build
docker compose ps
docker compose logs -f app
```

### 4. 安全组

见 [`deploy/security/security-group.md`](../deploy/security/security-group.md) — **仅开放 443/80 与受限 22**。

### 5. HTTPS（6A）

**方式 A — 客户证书 / Certbot**

1. 将证书放到 `deploy/nginx/certs/fullchain.pem` 与 `privkey.pem`
2. 合并 `deploy/nginx/ma-minsight.ssl.conf.example` 到 nginx 配置，或挂载自定义 `default.conf`
3. 在 `docker-compose.yml` 中为 nginx 增加端口 `443:443` 与 certs volume

**方式 B — 云 SLB 终止 TLS**

- SLB 443 → ECS:80（nginx HTTP）
- 无需在容器内配置证书

### 6. Wazuh / 企微

- 在 `.env` 配置 `WAZUH_INDEXER_*`、`DEEPSEEK_API_KEY`
- 企微回调 URL：`https://<域名>/api/v1/human-review/wecom/callback`
- 通过 Web Settings 或 API 配置 `data_sources` 指向 Wazuh Indexer

### 7. 上线验收

```bash
./deploy/scripts/smoke-test.sh
# Web 登录 → 修改 admin 密码
# Settings → 运行 health_check / regression（可选）
# 配置 Wazuh 后观察 Dashboard pipeline_last_run
```

## 运维

```bash
# 日志
docker compose logs -f app nginx

# 备份
./deploy/scripts/backup-postgres.sh

# 恢复（会短暂停 app）
./deploy/scripts/restore-postgres.sh backups/ma_minsight_YYYYMMDD_HHMMSS.sql.gz

# 升级
git pull && docker compose up -d --build
# entrypoint 自动 alembic upgrade head
```

## 附录 A：托管 PostgreSQL / Redis（5B）

若使用云 RDS / Redis，可精简 Compose：

1. 从 `docker-compose.yml` 移除 `postgres` / `redis` 服务
2. 在 `.env` 设置：

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@rds-host:5432/ma_minsight
SYNC_DATABASE_URL=postgresql://user:pass@rds-host:5432/ma_minsight
REDIS_URL=redis://:pass@redis-host:6379/0
DB_HOST=rds-host
REDIS_HOST=redis-host
```

3. 确保 ECS 安全组 **出站** 可访问 RDS/Redis 端口，且 RDS 白名单含 ECS 内网 IP
4. RDS 需支持 `CREATE EXTENSION vector`（pgvector，迁移 008）

## 附录 B：未来 worker 拆分

当前调度内嵌于 `app` 进程。若需独立 worker：

- 新建 `worker` 服务，CMD 仅启动 scheduler 模块（需后续代码拆分）
- `app` 仅 uvicorn，关闭 lifespan 中的 scheduler

---

任务书阶段 1–10 全部交付完成。
