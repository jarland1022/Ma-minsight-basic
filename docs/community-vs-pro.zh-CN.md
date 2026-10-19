[English](community-vs-pro.md) | **中文**

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
| 控制台 EN / 中文切换 | ✅ | ✅ |
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
- Pro API 走路由级 `require_pro_license`（**不要**把专业版全局 `LicenseGateMiddleware` 搬进社区版）。  
- 仓库含 `ma-minsight-public.pem`；**不含**私钥与 `license_gen`。  
- Docker：`MA_MINSIGHT_LICENSE_DIR` + `./configs/license` 挂载。  
- GitHub 默认英文 `README.md`；中文见 `README.zh-CN.md`。控制台默认 English，可切中文（见 `docs/i18n.md`）。

## 发布检查

- [ ] `EDITION` 为 `community`
- [ ] 默认 `README.md` 为英文，并链接 `README.zh-CN.md`
- [ ] 仓库无 `*-private.pem`、`license.lic`
- [ ] 无 `tools/license_gen.py`
- [ ] 含 `ma-minsight-public.pem`
- [ ] `/health` 返回 `edition=community`
- [ ] 未授权时 `investigation` 返回 402
- [ ] 控制台默认英文，可切换中文
