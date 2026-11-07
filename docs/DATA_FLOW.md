# MinSight 数据处理与外发披露（P0-06-A）

**版本:** 1.0.0  
**状态:** 与运行时 `GET /api/v1/privacy/disclosure` 对齐  
**声明:** 本地/私有网络部署 **不等于** 数据永不离开客户环境。伪名化 **不是** 匿名化。

## 1. 总览

MinSight 将 Wazuh 告警拉取并存储于客户侧 PostgreSQL。当配置了外部集成时，**派生后的调查上下文**可能经 `EgressGateway` 发往第三方或客户自有 Endpoint。

权威运行时披露（管理员）：`GET /api/v1/privacy/disclosure`  
通道开关状态：`GET /api/v1/privacy/policy`

## 2. 字段分类

| 类别 | 含义 | 默认外发 |
|------|------|----------|
| `SECRET_NEVER` | API Key、密码、Token、私钥 | 禁止（脱敏或整请求拒绝） |
| `PII_DEFAULT` | 用户名、主机名、私有 IP、URL query 等 | 伪名化 / 掩码 |
| `ANALYTIC_ALLOWED` | 规则、严重级别、类别、风险分等 | 允许 |
| `CONSENT_REQUIRED` | 完整 URL、丰富 HR/SOP 文本等 | 最小化；明文需显式策略 |

## 3. 通道边界

| 通道 | 可能目的地 | 可能包含 | 独立禁用 |
|------|------------|----------|----------|
| LLM | `DEEPSEEK_BASE_URL`（默认可为公有云；可 BYO） | 派生告警字段、SOP/HR/工具摘要（经保护） | `privacy.llm_egress_enabled` / `PRIVACY_LLM_EGRESS_ENABLED` |
| TI | AbuseIPDB / GreyNoise | **公网 IP** 指标 | `privacy.ti_egress_enabled` |
| WeCom | 企微 API / webhook | 协查 markdown（主机/用户默认伪名化） | `privacy.wecom_egress_enabled` |
| Embedding | `OPENAI_BASE_URL/embeddings` | 判例/查询文本（保护后）；**默认关闭** | `privacy.embed_egress_enabled` |
| Webhook | Eval 告警 URL | 失败标题/详情（保护后） | `privacy.webhook_egress_enabled` |

## 4. BYO Endpoint

客户自有 OpenAI-compatible Endpoint **仍是外发目的地**，除非客户能证明该 Endpoint 完全位于其信任边界内。  
**BYO 不会绕过 `EgressGateway` 保护。**

## 5. 不支持的宣传口径

在未经运行时验证（DNS/流量抓取）前，**不得**宣传：

- 「安全告警完全留在客户环境」
- 「MinSight 无任何外部通信」
- 「数据已完全匿名」

详见 `docs/review/P0_06_DATA_FLOW_AUDIT.md` 声明矩阵。
