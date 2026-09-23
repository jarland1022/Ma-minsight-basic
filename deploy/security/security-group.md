# MA-MinSight 安全组建议（单租户 ECS）

> 原则：**仅暴露 Web 入口**；数据库、Redis、FastAPI 8000 **不对公网开放**。

## 入站规则

| 优先级 | 协议 | 端口 | 源 | 说明 |
|--------|------|------|-----|------|
| 允许 | TCP | 443 | 运维网段 / VPN / 办公出口 | HTTPS Web 控制台（标准单机部署） |
| 允许 | TCP | 6443 | 运维网段 / VPN / 办公出口 | **ECS-A** HTTPS（`docker-compose.ecs-a.yml`，见 `up-ecs-a.sh`） |
| 允许 | TCP | 80 | 同上（可选） | HTTP → 301 跳转 HTTPS |
| 允许 | TCP | 8080 | 127.0.0.1 或运维网段（可选） | ECS-A 调试 HTTP（`.env` 中 `HTTP_PORT=8080`） |
| 允许 | TCP | 22 | 堡垒机固定 IP | SSH 运维（建议密钥登录） |
| **拒绝** | TCP | 5432 | 0.0.0.0/0 | PostgreSQL |
| **拒绝** | TCP | 6379 | 0.0.0.0/0 | Redis |
| **拒绝** | TCP | 8000 | 0.0.0.0/0 | FastAPI 直连 |

## 出站规则

| 协议 | 端口 | 目标 | 说明 |
|------|------|------|------|
| TCP | 443 | 0.0.0.0/0 | DeepSeek / 企微 / 公网 API |
| TCP | 9200 | Wazuh Indexer 网段 | 客户 SIEM（按实际修改） |
| TCP | 443 | Wazuh 若 HTTPS | 按 adapter 配置 |

## 企微回调

- 公网 URL 示例：`https://ma-minsight.customer.com/api/v1/human-review/wecom/callback`
- 需在企微后台配置，与 `WECOM_*` 环境变量一致

## 密钥

- 全部通过 `.env` 注入，**不要**写入镜像或 Git
- 生产必须修改：`POSTGRES_PASSWORD`、`API_KEY`、`JWT_SECRET`（≥32 字节）、`ADMIN_INITIAL_PASSWORD`

## 合规提醒

- 处置动作默认为建议，需人工 confirm（已在产品逻辑中 enforce）
- 日志避免打印完整 API Key / JWT / 告警 raw_data 中的敏感字段
