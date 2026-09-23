# 阶段 3：分诊初筛

## 流水线顺序

1. DedupHandler（60 分钟窗口）
2. WhitelistMatcher（唯一可自动放行）
3. ProfileHintScorer（仅参考分，0–20）
4. RuleScorer（severity/frequency/asset/category）
5. LlmAssistScorer（默认关闭）
6. RouteDecisionEngine
7. PersistHandler

## 路由结果

| route_decision | alerts.status |
|----------------|---------------|
| archive_* / sample_audit | ARCHIVED |
| queue_deep_review / queue_uncertain | TRIAGED |

## system_config 键

- `triage.dedup_window_minutes` = 60
- `triage.deep_review_threshold` = 70
- `triage.low_risk_threshold` = 30
- `triage.sample_audit_rate` = 0.01
- `triage.llm_assist_enabled` = false
- `triage.poll_interval_minutes` = 2

## API

```bash
curl -X POST "http://localhost:8000/api/v1/triage/run" -H "X-API-Key: $API_KEY"
curl "http://localhost:8000/api/v1/triage/stats" -H "X-API-Key: $API_KEY"
```

## 方法论约束

- `profile_hint_score` **不能**触发归档
- 仅 `whitelist_rule_id` 非空时可 `archive_whitelist`
- `triage_results` 为初筛路由，不是最终研判结论
