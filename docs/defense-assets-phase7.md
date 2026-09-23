# 阶段 7：防御资产沉淀

## 确认项（1C 2A 3A 4B 5A 6A 7A 8A）

- 5min Job + `POST /defense-assets/run`
- 白名单 ≥3 确认 → `whitelist_rules.status=active`
- 判例写入即 `Event → closed`
- embedding 写入（开关默认关）+ pgvector extension 迁移
- rule_candidates 落库 + API
- 抽检不自动加白名单确认
- 仅沉淀最新 completed Investigation
- 含 `attack_confirmed` 判例

## 调度

- 每 **5 分钟** `AssetPipeline`
- Redis 锁 `defense_assets:lock:pipeline`

## API

```bash
curl -X POST "http://localhost:8000/api/v1/defense-assets/run" -H "X-API-Key: $API_KEY"
curl -X POST "http://localhost:8000/api/v1/whitelist-candidates/{id}/confirm" -H "X-API-Key: $API_KEY"
curl -X POST "http://localhost:8000/api/v1/profile-suggestions/{id}/apply" -H "X-API-Key: $API_KEY"
curl -X POST "http://localhost:8000/api/v1/disposition/{id}/confirm" -H "X-API-Key: $API_KEY"
```

## 配置

- `defense_assets.embedding_enabled=false`
- `defense_assets.embedding_search_enabled=false`
- `defense_assets.whitelist_promotion_threshold=3`

## 链路

```text
concluded → judgment_cases + candidates → confirm/promote → Event closed
```
