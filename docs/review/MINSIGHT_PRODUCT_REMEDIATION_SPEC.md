# MinSight 产品整改与开发规格书
**版本：V1.0**  
**依据：10 张产品界面截图、现有产品功能说明及公开竞品资料**  
**目标：提升 MinSight 的安全性、调查可信度、运维能力和商业交付成熟度**

---

# 第一部分：项目背景与开发原则

## 1.1 产品定位

产品名称：MA-MinSight

目标定位：

**AI-Assisted SOC Investigation for Wazuh**

产品英文描述：

Turn Wazuh alerts into explainable investigations, evidence-backed findings, and human-reviewed decisions.

核心价值：

1. Wazuh-native：围绕 Wazuh 提供深入的告警调查能力。
2. Evidence-driven：AI 结论必须有可追溯的调查过程和证据支持。
3. Human-controlled：AI 可以调查、分析和建议，但关键安全决策由人控制。
4. Private deployment：支持客户环境内私有化部署，具体数据流和外部服务边界必须透明。

## 1.2 当前产品已有模块

根据现有产品界面，系统包含：

- Home / Dashboard
- Investigate / Events
- Event Details
- Human Review
- Defense Assets
- Playbooks
- System / User Guide
- System / Eval
- System / License
- System / Settings

Settings 包含：

- Ingestion diagnostics
- Manual pipeline execution
- Investigation SOP templates
- System configuration

Eval 包含：

- Agent regression
- Health probes
- Regression cases
- Probe scenarios

## 1.3 开发总原则

必须遵守以下原则：

1. 不要为了满足本规格书而推翻现有架构。
2. 不要在未理解现有代码前新增数据库表、API 或服务。
3. 优先复用已有模型、接口、任务队列和权限机制。
4. 不允许通过前端隐藏按钮代替后端权限控制。
5. 不允许伪造调查成功、证据、测试通过率或安全结论。
6. 不允许把模型配置错误、API 故障、程序异常当作安全事件。
7. 不允许把 AI 推断自动提升为人工确认的环境知识。
8. 不允许在没有真实数据流验证的情况下宣传告警完全不出网。
9. 不允许未经人工审批执行封禁、隔离等安全响应。
10. 每次修改必须提供测试和回归验证。

所有建议均需要先与现有代码进行差异分析。已经实现且满足要求的功能，不应重复开发。

---

# 第二部分：P0——安全性与可靠性整改

P0 是面向外部客户交付前必须完成的工作。

## P0-01：默认管理员账户安全

### 当前问题

登录页面展示：

- Default account：admin
- changeme

这属于高风险设计。

### 目标

取消所有公开、固定的默认管理员密码。

### 需求

1. 首次启动时生成随机管理员初始密码，或要求通过安全初始化流程设置。
2. 初始密码只能通过安全方式交付。
3. 首次登录必须修改密码。
4. 禁止在前端页面、公开文档、日志中展示默认密码。
5. 支持 Docker Secret 或安全环境变量注入。
6. 增加登录失败速率限制。
7. 支持管理员主动撤销会话。
8. 检查密码存储是否使用安全哈希算法。
9. 如果已有 MFA 能力，检查其实际生效范围；没有则评估后续实现。

### 验收标准

- 新部署不能使用固定默认密码登录。
- 数据库中不存在明文密码。
- 登录页面不泄露初始凭据。
- 首次登录强制修改密码。
- 连续错误登录受到限制。
- 已撤销的会话不能继续访问受保护 API。

## P0-02：实现真正的 Pilot Viewer 只读角色

### 目标

支持客户在 5-Day SOC Morning Briefing Pilot 期间向 MinSight 服务人员提供临时只读访问。

### 权限范围

允许：

- 查看 Dashboard。
- 查看 Events。
- 查看 Event Details。
- 查看 Investigation Trace。
- 查看 Evidence。
- 查看 Human Review 内容。
- 查看 Morning Briefing。

禁止：

- 修改系统配置。
- 修改 Playbooks。
- 修改 SOP。
- 修改规则。
- 修改用户和角色。
- 执行封禁或隔离。
- 执行 Defense Assets 审批。
- 确认或关闭安全事件。
- 执行会产生写入副作用的 Pipeline。
- 修改客户环境知识。

### 技术要求

1. 检查现有 RBAC 模型。
2. 在后端 API 层实施权限控制。
3. 检查所有写入 API、管理 API 和任务执行 API。
4. 对只读角色实施最小权限。
5. 支持账号过期时间。
6. 账号到期后自动拒绝访问。
7. 所有访问行为可审计。
8. 支持 MFA；如现有架构不支持，明确列为后续任务。
9. 如支持 IP 限制，允许管理员配置。

### 验收标准

使用 Pilot Viewer 登录后：

- 能查看授权范围内的数据。
- 不能通过直接调用 API 修改数据。
- 不能执行任何响应操作。
- 不能通过修改请求参数提升权限。
- 到期后所有访问均被拒绝。
- 管理员能够查看该账号的访问审计记录。

## P0-03：分离 Security Investigation 与 System Operation Failure

### 当前问题

已有界面显示：

LLM error: DEEPSEEK_API_KEY is not configured

但该问题进入了 Human Review。

这是不正确的。

LLM 配置错误属于系统运行故障，不属于安全事件，也不应该要求业务人员回答。

### 目标

建立两套独立的处理体系：

A. Security Investigation

处理安全告警和安全事件。

B. System Operation / Investigation Failure

处理模型 API、Wazuh、数据库、网络、Skill 执行和程序异常。

### 建议状态

安全调查：

- pending_review
- investigating
- human_pending
- concluded
- closed
- failed（仅在确有调查执行失败时使用，并明确失败状态）

系统运行：

- healthy
- degraded
- failed
- blocked
- retrying

### 需求

1. 模型 API 配置缺失时，调查任务应进入失败状态。
2. 记录失败阶段和错误代码。
3. 不允许生成虚假的 Agent 结论。
4. 不允许把配置异常加入 Security Human Review。
5. 管理员可以查看失败详情。
6. 修复配置后支持重新运行调查。
7. 重试不能重复创建无意义的事件或重复写入证据。
8. 保留失败前的调查上下文和执行记录。

### 验收标准

- DEEPSEEK_API_KEY 未配置时，调查失败。
- 失败原因显示为系统错误，而不是安全事件结论。
- Human Review Inbox 不出现该错误。
- 配置修复后可以重新调查。
- 重新调查生成新的执行记录，不覆盖原始失败记录。

## P0-04：统一事件状态和结论语义

### 目标

避免 Status、Verdict、Severity、Risk Score、Priority 和 Evidence Strength 混淆。

### 字段定义

Status：事件处理状态。

Verdict：AI 或分析师对事件性质的判断。

Severity：安全影响严重程度。

Risk Score：系统根据明确规则或模型计算的风险评分。

Priority：分析师处理优先级。

Evidence Strength：当前证据支持判断的强度。

### Verdict 建议枚举

- attack_confirmed
- likely_false_positive
- insufficient_information
- needs_human_review

必须明确哪些字段属于 AI 判断，哪些属于人工确认。

### 验收标准

- 所有相关页面使用一致的字段定义。
- 不允许 Risk Score 直接映射为 attack_confirmed。
- 不允许 Evidence Strength 自动等同于 Verdict。
- 不允许 Status 表示安全结论。
- 前端筛选、后端接口和数据库字段保持一致。

## P0-05：调查失败时的结论保护

### 目标

任何不完整调查都不能伪装成成功调查。

### 需求

每次 Investigation 应记录：

- Investigation ID
- Event ID
- Start time
- End time
- Agent version
- Model
- Prompt version（如可获取）
- Skills invoked
- Skills succeeded
- Skills failed
- Evidence collected
- Final verdict
- Investigation status
- Failure reason

当关键调查步骤失败时：

1. 明确标记失败步骤。
2. 显示缺失的证据。
3. 根据已有证据决定是否可以形成有限结论。
4. 如果不足以形成结论，必须输出 insufficient_information 或明确的失败状态。
5. 不允许凭空补全不存在的调查结果。

### 验收标准

模拟模型 API 失败、Skill 超时、Wazuh 查询失败等场景，检查系统不会错误输出 attack_confirmed 或 likely_false_positive。

## P0-06：数据流与隐私边界

### 目标

准确描述客户数据是否离开客户环境。

### 必须审查的数据流

- Wazuh Alerts
- Investigation Context
- LLM Requests
- Threat Intelligence Requests
- Embedding Requests
- Application Logs
- Error Logs
- Telemetry
- Backup Data

### 需求

1. 找出所有外部网络请求。
2. 明确哪些请求包含告警内容、资产信息或用户信息。
3. 明确哪些请求仅传输 IP、域名、Hash 等查询指标。
4. 检查日志是否记录 API Key、Token 或敏感事件内容。
5. 检查是否存在未披露的遥测或数据上报。
6. 为客户提供 Data Flow Diagram。
7. 记录外部模型服务和威胁情报服务的可配置项。

### 验收标准

提供完整的数据流清单和网络通信验证结果。

未经验证，不允许使用“所有告警不出网”“完全本地处理”等宣传语。

## P0-07：中英文国际化一致性

### 目标

修复 EN 模式下出现中文内容的问题。

### 范围

- Dashboard
- Events
- Event Details
- Human Review
- Defense Assets
- Playbooks
- Eval
- Settings
- User Guide
- 所有错误提示
- 所有空状态
- 所有弹窗和操作按钮

### 需求

1. 使用统一 i18n 机制。
2. 不允许在业务组件中散落硬编码文案。
3. 对动态错误信息提供可读的本地化描述。
4. 保持 verdict、status 等内部枚举稳定。
5. 支持 EN / 中文切换。

### 验收标准

完整遍历 EN 页面，不出现未预期中文内容；中文模式下也不能出现大量未翻译的用户可见文本。

## P0-08：配置与安全操作审计

### 需求

对以下行为记录审计：

- 用户登录和退出。
- 用户及角色变化。
- 系统配置修改。
- Playbook 修改。
- SOP 修改。
- Defense Assets 确认或拒绝。
- 事件状态变更。
- Pipeline 手动执行。
- 权限变更。
- 数据导出。

审计记录至少包括：

- Actor
- Action
- Resource
- Timestamp
- Result
- Source IP（如可用）
- Before / After（适用于配置变更）
- Correlation ID

敏感字段不得直接写入审计日志。

### 验收标准

管理员可以检索审计记录，并能区分成功操作和失败操作。

---

# 第三部分：P1——建立核心竞争力

## P1-01：Investigation Timeline

### 目标

让客户能够看到 AI 实际做了什么，而不只是看到一个最终结论。

### 建议调查时间线

1. Alert ingested
2. Alert normalized
3. Asset lookup
4. Historical alert lookup
5. Entity graph lookup
6. Threat intelligence lookup
7. SOP selected
8. LLM analysis
9. Evidence validation
10. Verdict generated
11. Human review（如需要）

### 每个步骤记录

- Step ID
- Step name
- Start time
- End time
- Duration
- Status
- Data source
- Input reference
- Output reference
- Error details

### UI 要求

在 Event Details 增加 Investigation Timeline 区域。

用户可以展开每个步骤，查看：

- 执行内容。
- 查询的数据源。
- 返回结果摘要。
- 是否成功。
- 耗时。
- 对最终结论的贡献。

注意：不得把内部思维链作为产品证据。应展示可审计的操作记录、数据来源、观察结果和结论依据。

### 验收标准

每个调查步骤都可以追溯；失败步骤清晰可见；不暴露 API Key、敏感凭据和内部隐藏推理内容。

## P1-02：Incident Correlation

### 目标

将相关的多条告警聚合成一个 Incident。

### 需求

1. 检查当前 Event Aggregation 实现。
2. 分析是否已有聚合规则和关联数据模型。
3. 支持按时间、资产、用户、IP、攻击行为和关联证据聚合。
4. 一个 Incident 可以包含多条 Alerts。
5. Incident 有独立状态、风险、优先级和调查记录。
6. 支持查看 Incident Timeline。
7. 支持从 Incident 跳转到原始 Alerts。
8. 支持防止重复告警导致重复 Incident。
9. 支持人工合并或拆分（需要审计）。

### 验收标准

构造多条属于同一攻击活动的告警，系统能合理聚合；无关告警不会被强行合并；每条原始告警仍可追溯。

## P1-03：Environment Knowledge

### 目标

让 MinSight 理解客户自己的安全环境。

### 知识类别

- Authorized Scanner
- VPN Egress
- Maintenance Window
- Service Account
- Admin Account
- Test Environment
- Critical Asset
- Known Benign Behavior
- Authorized Remote Access

### 每条知识建议字段

- Entity
- Knowledge Type
- Description
- Source
- Source Type
- Confidence
- Scope
- Valid From
- Expires At
- Created By
- Reviewed By
- Last Reviewed
- Status

### 来源类型

- AI inferred
- Analyst confirmed
- IT administrator confirmed
- External synchronized
- Imported

### 安全要求

1. AI 推断不得自动变成人工确认。
2. 知识必须支持过期时间。
3. 知识变更必须有审计记录。
4. 知识应有适用范围。
5. 资产或 IP 变化后需要重新验证。
6. 不允许仅凭单次 AI 判断永久创建白名单。

### 验收标准

调查可以引用环境知识，但必须显示知识来源、可信度和有效期。

## P1-04：Evidence Ledger

### 目标

将调查中的证据变成可追溯的数据对象。

### 建议字段

- Evidence ID
- Investigation ID
- Event ID / Incident ID
- Evidence Type
- Source
- Query Reference
- Observation
- Timestamp
- Related Entity
- Supports Verdict
- Refutes Verdict
- Confidence
- Data Reference

### 需求

1. 支持正向证据和反向证据。
2. 每条证据能追溯到原始数据。
3. 证据不能被静默修改。
4. 证据新增、删除和修订都应保留审计。
5. 证据引用必须与最终结论关联。

### 验收标准

用户可以查看某个结论由哪些证据支持，以及有哪些反证。

## P1-05：Pipeline Run History

### 目标

让管理员能够排查所有自动和手动 Pipeline。

### 字段

- Run ID
- Pipeline
- Trigger
- Triggered By
- Started At
- Finished At
- Duration
- Processed
- Success
- Failed
- Status
- Error Details

### 需求

1. 统一展示 Pipeline 执行记录。
2. 支持按时间、类型、状态筛选。
3. 支持查看失败原因。
4. 支持安全重试。
5. 防止重复执行。
6. 对有副作用的任务实施幂等性保护。
7. 对任务执行设置超时和并发限制。

### 验收标准

管理员可以定位失败任务，理解失败原因，并安全地重新执行。

## P1-06：Eval Quality Dashboard

### 目标

从简单的 PASS/FAIL 测试页面，升级为调查质量管理工具。

### 测试分类

A. Mock Regression

验证代码逻辑和工作流。

B. Live Model Regression

使用真实模型配置测试实际调查能力。

C. Integration Health Probes

验证 Wazuh、数据库、模型 API 和外部服务连接。

### 质量指标

- Verdict accuracy
- False positive rate
- False negative rate
- Insufficient information handling
- Human review accuracy（在有可靠人工标签的前提下）
- Evidence completeness
- Required skill execution success
- Investigation failure rate
- Regression pass rate

### 要求

1. 区分 Mock 和真实模型测试。
2. 保存测试集版本。
3. 保存 Agent / Prompt / Model 版本。
4. 支持 Expected vs Actual 对比。
5. 失败时展示具体原因。
6. 支持历史趋势。
7. 支持将经过审核的生产案例转化为 Regression Case。

### 特别要求

不得把 Mock 测试通过率包装成真实生产准确率。

## P1-07：Morning Briefing

### 目标

让 MinSight 产生客户每天都能直接感受到的价值。

### 建议报告结构

1. Executive Summary
2. Alerts Observed
3. Investigations Completed
4. High-priority Findings
5. Requires Analyst Review
6. Recommended Actions
7. Questions Requiring Human Input
8. Investigation Limitations

### 统计要求

必须区分：

- New alerts ingested
- Alerts investigated
- Alerts archived
- Alerts recommended for closure
- Events requiring human review
- Failed investigations

不允许把建议归档数量当成系统实际归档数量。

每个重要 Finding 必须可以跳转到对应 Event、Incident 和 Evidence。

### 验收标准

报告中的每个统计数字都有明确的数据来源和统计口径。

## P1-08：Dashboard 分离

### Analyst Dashboard

优先展示：

- High-priority incidents
- Pending review
- Human review
- Failed investigations
- Overdue investigations
- Recommended actions

### Admin Dashboard

优先展示：

- Ingestion health
- Pipeline status
- Model API health
- Investigation cost
- Token usage
- P95 duration
- Eval regression
- Audit failures
- Noisy rules

### 验收标准

分析师无需浏览大量管理指标就能找到待处理工作；管理员可以快速发现系统异常。

---

# 第四部分：P2——商业化扩展

以下功能不应优先于 P0 和 P1：

1. MSSP 多租户管理。
2. 更多 SIEM 集成。
3. 自动封禁和主机隔离。
4. 高级 SOAR 编排。
5. 更多模型支持。
6. 高级报表和客户自定义报告。
7. 自定义 Agent。

开发原则：先验证客户需求，再投入较大开发成本。

---

# 第五部分：Cursor 执行流程

## Phase 0：代码库审查

在修改任何代码前，先执行完整代码审查。

需要检查：

- 项目目录结构。
- 前端技术栈。
- 后端技术栈。
- 数据库和 ORM。
- API 路由。
- 认证与授权。
- 用户角色。
- Event 和 Alert 数据模型。
- Investigation 数据模型。
- Human Review 数据模型。
- Defense Assets 数据模型。
- Pipeline 和任务调度。
- Agent 和 Skill 实现。
- 模型 API 调用。
- Eval 实现。
- 日志和审计。
- Docker 部署方式。
- 测试框架。
- 中英文国际化机制。

输出：

`docs/review/CODEBASE_AUDIT.md`

内容包括：

1. 当前架构。
2. 核心模块及其代码位置。
3. 已实现功能。
4. 未实现功能。
5. 部分实现但存在缺陷的功能。
6. 已存在的相关数据库表和 API。
7. 技术债务。
8. 安全风险。
9. 与本规格书的差距。
10. 推荐实施顺序。

注意：只分析，不修改代码。

## Phase 1：制定实施计划

基于代码审查结果，输出：

`docs/review/IMPLEMENTATION_PLAN.md`

每个任务必须说明：

- 对应规格编号。
- 当前实现情况。
- 需要修改的文件。
- 是否需要数据库变更。
- 是否需要 API 变更。
- 是否影响现有功能。
- 实施方案。
- 测试方案。
- 回滚方案。
- 验收标准。

如果现有代码已经实现某项需求，应标记为已满足，不要重复开发。

## Phase 2：实施 P0

按 P0-01 至 P0-08 的顺序实施。

每次只实施一个或一组高度相关的任务。

每个任务完成后：

1. 执行单元测试。
2. 执行集成测试。
3. 执行安全测试。
4. 执行前端构建。
5. 检查日志和异常。
6. 检查是否影响已有功能。
7. 更新实施记录。

输出：

`docs/review/P0_IMPLEMENTATION_REPORT.md`

## Phase 3：实施 P1

按照 P1-01 至 P1-08 实施。

如果某项功能已有基础，应优先增强现有实现，不要另建一套平行架构。

特别注意：

- Investigation Timeline 和 Evidence Ledger 需要共享可追溯的数据关系。
- Incident Correlation 必须保留原始 Alert。
- Environment Knowledge 必须区分人工确认和 AI 推断。
- Eval 必须区分 Mock、Live Model 和 Integration。
- Morning Briefing 必须有明确统计口径。

输出：

`docs/review/P1_IMPLEMENTATION_REPORT.md`

## Phase 4：最终验证

必须至少覆盖：

### 安全测试

- 默认凭据测试。
- 登录失败限速测试。
- RBAC 越权测试。
- Pilot Viewer 只读测试。
- API 直接调用测试。
- 敏感配置保护测试。
- 审计记录测试。

### 业务测试

- 正常 Wazuh 告警调查。
- 误报场景。
- 攻击场景。
- 证据不足场景。
- 需要人工回答场景。
- 模型 API 不可用。
- Wazuh API 不可用。
- Skill 执行超时。
- Pipeline 重复执行。
- 事件聚合和重复告警。

### 运维测试

- Docker 全新部署。
- Docker 重启。
- 配置变更。
- 模型服务恢复。
- 数据源恢复。
- 数据备份和恢复。
- 账号过期。
- 中英文切换。

输出：

`docs/review/FINAL_ACCEPTANCE_REPORT.md`

---

# 第六部分：开发完成的定义

MinSight 不应仅以“页面能打开”或“接口返回 200”作为完成标准。

每项功能都必须满足：

1. 有明确的业务行为。
2. 有明确的数据来源。
3. 有明确的权限控制。
4. 有失败处理。
5. 有审计或日志。
6. 有自动化测试。
7. 不破坏已有功能。
8. 有可复现的验收步骤。

**最终目标：让 MinSight 成为一款可以安全部署、可靠调查、证据可追溯、人工可控、能够持续评估质量的 Wazuh AI SOC 产品。**
