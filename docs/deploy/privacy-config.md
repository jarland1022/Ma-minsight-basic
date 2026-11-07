# 生产 / Docker 隐私配置说明（P0-06 R-B / AUTH-R3）

**状态:** 与 `app/privacy/config.py` 对齐  
**相关:** `deploy/env/production.env.example` · `.env.example` · `docs/DATA_FLOW.md`

## 1. 优先级（后端强制）

1. **`PRIVACY_*` 环境变量**（最高；管理员无法用 `system_config` 覆盖）  
2. **`strict_mode` 钳制**（关闭明文 PII / embed 等）  
3. **`system_config` 中 `privacy.*`**（Admin API 可改，仍低于 env）  
4. **代码默认值**

Docker Compose 通过 `env_file: .env` 注入；**不会**在 compose 内硬编码隐私开关。

## 2. `PRIVACY_*` 清单

| 环境变量 | 代码默认 | 生产模板建议 | 必须？ | Admin DB 可改？ | 安全影响 |
|----------|----------|--------------|--------|-----------------|----------|
| `PRIVACY_PSEUDONYM_SECRET` | 空 → 由 JWT 派生；**production + 默认 JWT → None（fail-closed）** | **必填强随机** | 生产强烈必须 | 否（仅 env / settings） | 缺失则拒绝需伪名的外发 |
| `PRIVACY_STRICT_MODE` | `false` | `false`（按客户开启） | 否 | 是（`privacy.strict_mode`）但 env 可强制 | 强制关闭明文与 embed |
| `PRIVACY_LLM_EGRESS_ENABLED` | `true`（仍需 API Key） | `true` | 否 | 是，可被 env 覆盖 | `false` 阻断 LLM 出站 |
| `PRIVACY_TI_EGRESS_ENABLED` | `true`（仍需厂商 Key） | `true` | 否 | 是 | 关闭 TI 出站 |
| `PRIVACY_WECOM_EGRESS_ENABLED` | `true` | `true` | 否 | 是 | 关闭 WeCom 出站 |
| `PRIVACY_EMBED_EGRESS_ENABLED` | `false` | `false` | 否 | 是 | 默认关闭 embedding 外发 |
| `PRIVACY_WEBHOOK_EGRESS_ENABLED` | `true` | `true` | 否 | 是 | 关闭 eval webhook |
| `PRIVACY_LLM_ALLOW_PUBLIC_IP_PLAINTEXT` | `false` | `false` | 否 | 是（`privacy.llm.*`） | 勿为部署方便改为 true |
| `PRIVACY_LLM_ALLOW_USERNAME_PLAINTEXT` | `false` | `false` | 否 | 是 | 同上 |
| `PRIVACY_LLM_ALLOW_HOSTNAME_PLAINTEXT` | `false` | `false` | 否 | 是 | 同上 |
| `PRIVACY_LLM_ALLOW_FULL_URL` | `false` | `false` | 否 | 是 | 同上 |
| `PRIVACY_WECOM_ALLOW_HOST_USER` | `false` | `false` | 否 | 是 | 同上 |
| `PRIVACY_ALLOWED_LLM_BASE_URLS` | 空 | 严格模式时填写 | 严格模式必须 | 是 | URL allowlist |
| `PRIVACY_CUSTOMER_SCOPE_ID` | DB 名 | 客户租户 ID | 建议 | 否（env） | 伪名跨环境隔离 |

另：`DEEPSEEK_API_KEY` 为空 → LLM **不发 HTTP**（与通道开关独立）。

## 3. Fail-closed 行为（代码）

| 条件 | 行为 |
|------|------|
| 空 `DEEPSEEK_API_KEY` | `LLMClient` 抛错，无出站 |
| production + 默认 JWT + 空伪名密钥 | `pseudonym_secret is None` → Gateway deny |
| 通道 `PRIVACY_*_EGRESS_ENABLED=false` | Gateway `channel_disabled`，无 HTTP |
| Gateway / 变换失败 | `EgressDeniedError`；**无**明文回退 |

## 4. 部署检查清单

1. 从 `deploy/env/production.env.example` 复制 `.env`，填入强 `JWT_SECRET` 与 `PRIVACY_PSEUDONYM_SECRET`。  
2. 确认 `APP_ENV=production`。  
3. 空 LLM/TI/WeCom Key = 对应集成不外发（仍建议显式关闭不需要的通道）。  
4. 勿在模板或仓库提交真实密钥。  
5. 伪名化 ≠ 匿名化；勿宣传 air-gap，除非完成 RV 运行时验证。

## 5. 与 A..E 验收关系

本文件补齐 **R3 配置披露**；**不**将 RV-01..08 标为 PASS。
