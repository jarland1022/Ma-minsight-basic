# 阶段 6：人工协查（企业微信）

## 确认项（1C 2A 3A 4C 5A 6A 7A 8A）

- 企微自建应用 + Webhook 降级 outbound
- 路由 `#EVT-{uuid前8位}`
- Agent 复跑不占日 budget（Redis `investigate:skip_budget:{event_id}`）
- 人工回复原文注入 Prompt
- 24h 超时自动重发（最多 2 次）
- 每 Event 仅 1 条 `sent` 协查
- 环上抽检落库 + API，IM 推送默认关
- 不做人工作直判，统一 Agent 复跑
- 未配置企微时，协查派发仍创建 Web inbox 协查单（不发 IM）

## 调度

- 每 **2 分钟**：dispatch + expire + audit_sample 生成
- Redis 锁 `human_review:lock:dispatch`

## API

```bash
curl -X POST "http://localhost:8000/api/v1/human-review/run" -H "X-API-Key: $API_KEY"
curl -X POST "http://localhost:8000/api/v1/human-review/responses" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"raw_content":"确认误报 #EVT-a1b2c3d4"}'
curl -X POST "http://localhost:8000/api/v1/audit-samples/run" -H "X-API-Key: $API_KEY"
```

## 环境变量

- `WECOM_CORP_ID` / `WECOM_AGENT_ID` / `WECOM_SECRET` — 自建应用
- `WECOM_WEBHOOK_URL` — outbound 降级
- `WECOM_CALLBACK_TOKEN` — 回调验签

## 链路

```text
human_pending → human_review_requests(sent) → 人工回复
  → Event(pending_review) + Prompt 注入 → Agent 复跑 → concluded
```
