# 阶段 4：事件聚合

## 聚合键（Option B）

```text
event_key = SHA256(host_norm|user_norm|category_norm|window_start)[:32]
window_start = UTC 日界 00:00:00
缺 host/user → __unknown_host__ / __unknown_user__
```

## 并入规则

- 仅并入 `status=pending_review` 的同键 Event
- `investigating` 等同键告警 → **新建 Event**

## 入口 / 出口

| 条件 | 结果 |
|------|------|
| `alerts.status=triaged` + `queue_deep_review/uncertain` | 参与聚合 |
| 聚合完成 | `alerts.status=event_linked` |
| Event | `status=pending_review`, `queue_priority` 更新 |

## API

```bash
curl -X POST "http://localhost:8000/api/v1/aggregation/run" -H "X-API-Key: $API_KEY"
curl "http://localhost:8000/api/v1/aggregation/stats" -H "X-API-Key: $API_KEY"
curl "http://localhost:8000/api/v1/aggregation/events/{id}" -H "X-API-Key: $API_KEY"
```

## 阶段 5 调度排序

```sql
ORDER BY queue_priority DESC, risk_score DESC, last_alert_at ASC
```
