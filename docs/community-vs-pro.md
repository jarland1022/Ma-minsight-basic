# 社区版与专业版

社区版放在 GitHub / Gitee，让人能在自己的机器上把 Wazuh 告警**收进来、降噪、聚成事件**，并浏览技能库与 ATT&CK 覆盖。专业版卖的是 **AI 深度研判 + 企微协作 + 防御闭环 + 有人负责**，不是再卖一套「能列表显示告警」的 UI。

## 定价（建议）

| 项目 | 建议 |
|------|------|
| 社区版 | 免费，Apache-2.0 |
| 专业版 | **¥9,800 / 节点 / 年**（可按合同调整；对标 SOC 工具而非纯开源捐赠） |
| 试用 | 由厂商签发限时 `license.lic`（社区仓库**无**自动 72h Pro 宽限） |
| 更高档 | 多节点、驻场调优、私有化 SOP 包另议 |

社区版装上后，导入有效 License 并重启即可在同一套代码上解锁 Pro，无需重装。

## 能力对照

| 能力 | 社区版 | 专业版 |
|------|:------:|:------:|
| Wazuh / Mock 入库 | ✅ | ✅ |
| 规则初筛 + 聚合 | ✅ | ✅ |
| 事件台 / 仪表盘 / 噪声规则 | ✅ | ✅ |
| 技能库（精选 + 社区包）与 ATT&CK 覆盖 | ✅ | ✅ |
| 本地账号登录 | ✅ | ✅ |
| Docker Compose 自托管（含 License 卷） | ✅ | ✅ |
| LLM ReAct Agent 调查 | ❌ | ✅ |
| 结论处置分级 / 证据标签 | 展示字段（无 Agent 时不产出） | ✅ 自动产出 |
| 行为时间线 / 样本富化等增强 Skill | 代码随仓库（Agent 解锁后可用） | ✅ |
| 企微人工协查 | ❌ | ✅ |
| 防御资产 / 判例学习 | ❌ | ✅ |
| 威胁情报同步增强 | 有限 | ✅ |
| 回归评测 / 链路探针 | ❌ | ✅ |
| 商用支持与对公合同 | ❌ | ✅ |

## 技术说明（给维护者）

- `EDITION=community`：无静默 Pro 试用；未授权时不启动 Agent / 协查 / 防御 / 评测调度器。  
- Pro API 走路由级 `require_pro_license`（**不要**把专业版全局 `LicenseGateMiddleware` 搬进社区版，否则会误伤免费入库/初筛）。  
- 仓库含 `ma-minsight-public.pem`；**不含**私钥与 `license_gen`。  
- Docker：`MA_MINSIGHT_LICENSE_DIR` + `./configs/license` 挂载，避免重建丢授权。

## 为什么这样切

社区版必须能**自己装上、看到告警变少、事件列表有数据、技能库可浏览**，否则没有 Star，也没有咨询。专业版必须锁住 Agent 与企业协作，否则开源之后没有付款理由。

## 获客路径

1. README + Compose 让人 15 分钟跑通入库→初筛→聚合。  
2. 文章讲清「SIEM 发现、MinSight 分诊」，挂 GitHub/Gitee 双链（见 `docs/article-siem-minsight.md`）。  
3. 控制台 License 条幅 + License 页放指纹与联系方式。  
4. 试用 License 只从销售侧签发。  
5. 中文内容（Wazuh 告警太多怎么办）比空仓库更容易被搜到。

## 发布检查

- [ ] `EDITION` 为 `community`
- [ ] 仓库无 `*-private.pem`、`license.lic`、客户 IP/证书
- [ ] 无 `tools/license_gen.py`
- [ ] 含 `ma-minsight-public.pem`
- [ ] `docker compose up -d --build` 后 `/health` 返回 `edition=community`
- [ ] 未授权时手动跑 `investigation` 返回 402
- [ ] 技能库能列出 community pack / coverage
- [ ] README 联系方式为真实微信/邮箱
- [ ] 未声称「已通过等保」或「替代全部 SIEM」
