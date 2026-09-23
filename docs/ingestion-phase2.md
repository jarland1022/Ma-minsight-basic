# 阶段 2：告警接入与 Wazuh Indexer 适配

## 架构概览

```
APScheduler (5min) ──► IngestService.run_all_active()
                              │
                              ├─ Redis ingest:lock:{source_id}
                              ├─ WazuhAdapter.pull() → Indexer search_after
                              ├─ map_to_normalized()
                              └─ INSERT alerts ON CONFLICT DO NOTHING
```

## Wazuh Indexer 配置

在 `data_sources` 表注册一条记录，例如：

```sql
INSERT INTO data_sources (id, name, adapter_type, config, cursor_state, is_active)
VALUES (
  gen_random_uuid(),
  'wazuh',
  'wazuh',
  '{
    "indexer_url": "https://wazuh-indexer:9200",
    "username_env": "WAZUH_INDEXER_USER",
    "password_env": "WAZUH_INDEXER_PASSWORD",
    "index_pattern": "wazuh-alerts-*",
    "verify_tls": true,
    "initial_lookback_hours": 24,
    "batch_size": 500
  }'::jsonb,
  '{}'::jsonb,
  true
);
```

环境变量：

```bash
WAZUH_INDEXER_USER=admin
WAZUH_INDEXER_PASSWORD=your-password
```

## 字段映射

| 标准字段 | Wazuh 来源 |
|---------|-----------|
| source_alert_id | `_id` |
| occurred_at | `timestamp` |
| rule_id / rule_name | `rule.id` / `rule.description` |
| severity | `rule.level` → 1-5 |
| host_name | `agent.name` |
| src_ip | `data.srcip` / `agent.ip` |
| user_name | `data.dstuser` / `data.srcuser` |
| file_hash | `syscheck.sha256_after` |
| alert_category | `rule.groups` → 映射表 |
| raw_data | 完整 document |

## API（需 `X-API-Key`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/ingestion/sources` | 列出数据源 |
| POST | `/api/v1/ingestion/sources/{id}/pull` | 手动拉取 |
| GET | `/api/v1/ingestion/sources/{id}/status` | 游标与状态 |

## CLI

```bash
python -m app.ingestion.cli pull --source wazuh
python -m app.ingestion.cli pull --source wazuh --no-lock
```

## Mock 适配器（测试/演示）

`adapter_type=mock_wazuh`，config 示例：

```json
{"fixture_names": ["auth_failed.json", "syscheck_modified.json"]}
```

## 游标格式

```json
{
  "version": 1,
  "mode": "search_after",
  "last_occurred_at": "2026-06-23T10:15:30.123Z",
  "last_sort_values": ["2026-06-23T10:15:30.123Z", "abc123"],
  "last_successful_run_at": "2026-06-23T10:20:00Z",
  "total_ingested": 152340
}
```

## 启动

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

调度间隔读取 `system_config.ingestion.poll_interval_minutes`（默认 5）。
