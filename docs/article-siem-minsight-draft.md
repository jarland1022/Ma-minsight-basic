# 文章草稿：SIEM + MinSight（社区版免费 / 专业版收费）

> 用途：发知乎 / 掘金 / CSDN / 公众号。发布前把 GitHub、Gitee 仓库 URL 换成真实地址，并配 3～5 张控制台截图。

---

## 标题备选

1. Wazuh 告警太多？用开源 MinSight 做 SIEM 之上的智能分诊  
2. SIEM 只负责发现，MinSight 负责研判：社区版免费上手  
3. 从告警洪水到可值班事件：MA-MinSight 社区版实践

---

## 正文结构（可直接扩写）

### 1. 开头：值班员的真实痛点（约 200 字）

很多团队已经上了 Wazuh / ELK / 某国产 SIEM，问题不再是「有没有告警」，而是：

- 每天几千条，真正要看的不到 1%  
- 同一主机同一类规则反复刷屏  
- 新人看不懂规则 ID，老人靠经验「肉眼过滤」  

结论先说：**再买一个 SIEM 解决不了分诊；需要的是 SIEM 之上的研判层。**

### 2. 定位：MinSight 不是又一个 SIEM（约 300 字）

MA-MinSight 做的是：

`告警入库 → 初筛降噪 → 聚合成事件 →（专业版）AI Agent 调查 → 人工协查 → 防御资产`

它吃的是 SIEM/EDR 已经产出的告警，输出的是「更少、更可行动的事件与结论」。  
和 Wazuh 的关系：Wazuh 负责采集与检测；MinSight 负责运营侧消化。

可放一张简易架构图（Mermaid 或截图）。

### 3. 社区版：免费能跑通什么（约 400 字 + 截图）

社区版 Apache-2.0，适合自建验证：

1. `docker compose up -d --build`  
2. 配置 Wazuh Indexer 数据源（或先用 Mock）  
3. 设置页手动跑：入库 → 初筛 → 聚合  
4. 事件队列里看到合并后的 Event  

强调：**5～15 分钟应能看到「告警变事件」**，否则开源没有说服力。

仓库链接：

- GitHub：`https://github.com/<your-org>/Ma-minsight-basic`  
- Gitee：`https://gitee.com/<your-org>/Ma-minsight-basic`

### 4. 专业版：什么时候该付钱（约 400 字）

当你需要：

- LLM Agent 自动写调查结论（ReAct + Skill）  
- 企微把问题推给业务同事用白话回复  
- 判例 / 白名单 / 处置建议沉淀回防御  
- 回归评测与商用支持、对公合同  

同一套社区版安装，导入厂商签发的 `license.lic` 即可解锁（控制台 → License）。  
联系：微信 `jarlandliu`，邮箱 `jarland@mingansec.com`。

对照表可直接引用仓库 `docs/community-vs-pro.md`。

### 5. 和「只会堆规则」的区别（约 200 字）

- 只加 SIEM 规则 → 告警更多  
- 只上大模型聊天 → 没有入库/聚合/审计闭环  
- MinSight → 把检测结果变成可运营的工作流  

### 6. CTA（约 100 字）

1. Star / 克隆社区版，先跑通聚合  
2. 把机器指纹发来，可申请专业版试用 License  
3. 同系列还有 Ma-WAF 社区版（Web 防护），可组合「防护 + 检测分诊」

---

## 发布检查

- [ ] 仓库已公开且 README 可 Compose 启动  
- [ ] 文中无客户真实 IP、无内部 ECS 细节  
- [ ] 未承诺等保一次性通过  
- [ ] 闲鱼/社群转发时附带同一仓库链接，避免「无开源背书的裸卖」
