# 阶段 9：评测回归 + 链路健康检查

## 确认项（1C 2A 3A 4A 5C 6C 7C 8C）

- Agent 回归为主；初筛/聚合由 health_check 分 stage 探针覆盖
- DB 种子 + JSONL import/export API
- 默认 Mock LLM；Admin 可选 `use_real_llm=true`
- `health_probe` 专用 data_source + 探针标记 + 不占 budget/企微/防御资产
- 分 stage 场景 + `probe_full_chain`
- Cron 默认关闭（`eval.*_cron` 配置启用）
- Web「评测」页 + Dashboard 健康条
- 失败 audit_log + Dashboard 红标 + 可选 Webhook

## 后端

- `app/eval/` — RegressionRunner、HealthCheckRunner、ProbeInject、Mock LLM
- `app/api/routes/regression.py` / `health_checks.py`
- `GET /health/ready` — DB + Redis
- `alembic/versions/010_eval_seed.py` — 配置、5 回归 case、5 探针 scenario

## CLI

```bash
python -m app.eval.cli regression run
python -m app.eval.cli health-check run --all
python -m app.eval.cli regression import --file cases.jsonl
```

## API 示例

```bash
curl -X POST "http://localhost:8000/api/v1/regression/run" -H "Authorization: Bearer $TOKEN"
curl -X POST "http://localhost:8000/api/v1/health-checks/run" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/api/v1/regression/runs" -H "Authorization: Bearer $TOKEN"
```

## Web

- 侧栏 **评测** — 回归/探针运行与历史
- Dashboard — 评测健康条 + 失败 Alert

## 配置

- `eval.regression_cron` / `eval.health_check_cron` — null 表示不调度
- `eval.alert_webhook_url` — 失败企微 Markdown Webhook
