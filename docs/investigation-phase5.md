# 阶段 5：Agent 深度调查

## Skills（MVP）

| Skill | 说明 |
|-------|------|
| `query_asset` | 资产画像 + 7d 统计 + memories + 值班知识 |
| `query_history_alerts` | 实体近期告警 |
| `query_threat_intel` | 读 `threat_intel_entries` 缓存；外部同步见 `ma-ti-sync` |
| `submit_conclusion` | 终止并提交结构化结论 |

## 调度

- 每 **3 分钟** 选取 `pending_review` Event
- 日预算 **200** Event/天（Redis 计数）
- 排序：`queue_priority DESC, risk_score DESC`

## API

```bash
curl -X POST "http://localhost:8000/api/v1/investigations/run" -H "X-API-Key: $API_KEY"
curl "http://localhost:8000/api/v1/investigations/{id}/trace" -H "X-API-Key: $API_KEY"
```

## 配置

- `investigation.reasoner_enabled=false`（预留）
- `investigation.alert_prompt_limit=20`
