# MinSight 短视频提示词 / Short-form video prompts

中文：小红书 / 抖音｜English：YouTube Shorts / TikTok / LinkedIn / X  
竖屏 9:16｜Community free → Pro trial  

仓库 / Repos：
- Gitee：https://gitee.com/jarland/Ma-minsight-basic
- GitHub：https://github.com/jarland1022/Ma-minsight-basic

**中文 CTA：** 评论「分诊」｜微信 `jarlandliu`  
**English CTA:** Comment `TRIAGE`｜email `jarland@mingansec.com`

> 英文完整章节从文内 **「English edition」**（N–W）起。

---

## A. 可灵 / 即梦 · 15 秒成片分镜表

**总时长**：15s｜**风格**：暗色安全运营控制台，克制科技感，避免赛博紫光、霓虹、恐怖片氛围  
**出镜**：无真人（纯 UI / 动效）｜**字幕**：中文大字，底部安全区留白  

| 镜号 | 时长 | 画面内容 | 中文提示词（即梦/可灵） | English prompt (Kling / Jimeng) |
|------|------|----------|------------------------|----------------------------------|
| 1 | 0–3s | 满屏红色告警暴涨 | 竖屏9:16，深色SOC监控大屏，红色告警数字从200飙到3842，镜头轻微推进，紧张但不血腥，大字幕「一天三千条告警」 | Vertical 9:16, dark SOC dashboard, red alert counter skyrocketing from 200 to 3842, subtle camera push-in, tense but clean, no gore, bold Chinese subtitle |
| 2 | 3–7s | 告警洪水 → 降噪 | 同一控制台，告警列表快速滚动后数量骤降，绿色对勾出现，字幕「别再人眼刷了」 | Same console UI, alert list scrolling then count dropping sharply, green checkmark, clean tech UI, Chinese subtitle |
| 3 | 7–12s | 流水线三步 | 横向流程动画：入库→初筛→聚合→事件卡片，扁平图标，字幕「开源 MinSight 社区版」 | Flat motion graphic pipeline: ingest → triage → aggregate → event cards, dark navy background, Chinese product subtitle |
| 4 | 12–15s | CTA 定格 | 深色底，白字「评论区扣：分诊」，小字「免费自托管｜非又一个SIEM」，角落极简盾牌 logo | Dark end card, large white Chinese CTA text, small subtitle free self-hosted, minimal shield logo, no flashy glow |

**全局负面提示词（各镜可粘贴）**

```text
中文：真人脸、血腥、黑客兜帽、绿色代码雨、紫色霓虹、卡通、低清晰、水印、横屏
English: human face, blood, hooded hacker, matrix rain, purple neon glow, cartoon, blurry, watermark, landscape 16:9
```

**口播音轨（15s，男女通用短句）**

```text
Wazuh 告警一天几千条？别再人眼刷了。
开源 MinSight：入库、初筛、聚合成事件，社区版免费。
要 AI 研判，评论扣「分诊」。
```

---

## B. 可灵 / 即梦 · 45 秒成片分镜表

**总时长**：45s｜可分段生成后在剪映拼接  

| 镜号 | 时长 | 画面 | 中文提示词 | English prompt |
|------|------|------|------------|----------------|
| 1 | 0–5s | 痛点钩子 | 竖屏，值班监控墙满屏红点闪烁，前景虚化咖啡杯，字幕「报废值班？」 | Vertical, SOC wall of blinking red alerts, soft bokeh coffee cup foreground, Chinese hook subtitle, realistic office night |
| 2 | 5–12s | 误区对比 | 左右分屏：左边「只加规则」告警更多；右边「只丢大模型」无闭环，简洁信息图 | Split screen infographic: left more rules more noise; right chatbot without pipeline, clean corporate design, Chinese labels |
| 3 | 12–22s | 产品定位 | 架构流转：Wazuh图标→MinSight入库初筛聚合→事件台，字幕「SIEM发现，MinSight消化」 | Architecture motion: Wazuh to MinSight triage layer to event console, dark blue palette, Chinese caption |
| 4 | 22–34s | 功能演示感 | 模拟控制台：事件列表、技能库ATT&CK覆盖热力，鼠标点击高亮，像真实产品录屏风格 | Simulated product UI screen recording style, event queue and ATT&CK coverage board, cursor clicks, crisp UI, no real logos infringement |
| 5 | 34–40s | 社区 vs 专业 | 对照卡片动画：社区免费三列能力；专业版AI/企微/防御资产亮起锁打开 | Comparison cards animation, community free vs pro unlock AI WeCom defense, padlock opens, Chinese text |
| 6 | 40–45s | CTA | 定格：Gitee/GitHub 搜索 Ma-minsight-basic，微信 jarlandliu，评论「分诊」 | End card with repo name and WeChat CTA, vertical 9:16, high contrast Chinese typography |

**BGM 提示**：轻快科技感，BPM 110–120，无人声歌曲抢口播。

---

## C. 口播人设版 · 男声（稳、运维感）

**人设提示词（给配音员 / 剪映音色）**

```text
30岁左右男声，语气冷静务实，像安全运维主管讲解，语速中等偏快，不卖货腔，不夸张情绪。
关键词：可信、专业、短句、顿挫清楚。
```

### C1 · 15 秒男声

```text
告警一天三千条，还在靠人眼刷？
再买 SIEM 解决不了分诊。
开源 MinSight，社区版免费：入库、初筛、聚合成事件。
要 AI 自动研判，评论区扣「分诊」。
```

### C2 · 45 秒男声

```text
很多团队 Wazuh 早就装了。难的不是没告警，是告警太多，真正要盯的不到百分之一。

规则越加越吵；把告警丢给大模型，又没有入库、聚合和审计闭环。

MA-MinSight 不是又一个 SIEM，它是 SIEM 之上的分诊层：告警进来，先初筛，再聚成事件。社区版开源，自己 Docker 就能跑；专业版再解锁 AI Agent、企微协查和防御资产。

同一套系统，导入 License 就能升级。
评论「分诊」拿社区版；要试用，加微信 jarlandliu。
```

### C3 · 60 秒男声（小红书中长）

```text
如果你也在值SOC班，大概懂这种感觉：屏幕全是红的，同一主机同一规则反复刷，新人看不懂规则ID，老人靠经验肉眼过滤。

这时候再买一套 SIEM，通常只会更吵。缺的是分诊和研判，不是第二个检测引擎。

MA-MinSight 做的是：把 Wazuh 这类告警收进来，规则初筛，按主机用户类别聚成事件。社区版 Apache 开源，技能库还能看 ATT&CK 覆盖。需要 AI 写结论、企微找业务白话回复，再上专业版。

十五分钟目标很明确——先看到告警变成事件。
仓库搜 Ma-minsight-basic，Gitee、GitHub 都有。
评论「分诊」，我发链接；专业版试用，微信 jarlandliu。
```

---

## D. 口播人设版 · 女声（清、干货感）

**人设提示词（给配音员 / 剪映音色）**

```text
25–32岁女声，清晰干练，像技术博主讲干货，亲和但不撒娇，语速略快，重点词加重。
关键词：清楚、利落、可信、少语气词。
```

### D1 · 15 秒女声

```text
Wazuh 告警爆炸？别只会加人眼。
开源 MinSight：入库、降噪、聚成事件，社区版免费自托管。
它不是又一个 SIEM，是 SIEM 上面的分诊层。
评论扣「分诊」，我发仓库。
```

### D2 · 45 秒女声

```text
先说结论：告警太多，再买 SIEM 往往没用，你要的是分诊层。

MA-MinSight 社区版，免费开源。对接 Wazuh 之后，走入库、初筛、聚合，控制台直接看事件，技能库还能看 ATT&CK。

专业版才上 AI Agent 研判、企微协查、防御资产沉淀——同一套安装，导入 License 升级，不用重装。

适合已经有检测、但值班看不过来的团队。
评论「分诊」领社区版；要试用专业版，微信 jarlandliu。
```

### D3 · 60 秒女声

```text
有没有人和我一样：SIEM 装好了，告警却把班值废了？

只加规则，误报更多；只把告警贴进 ChatGPT，看起来能分析，但没有入库、聚合、审计闭环。

所以我们做了 MA-MinSight。定位很清楚——SIEM 负责发现，MinSight 负责消化。社区版把告警变成可值班事件；专业版再让 AI 和企微把事件变成结论。

自己 Docker 就能跑，数据留在你自己的环境。
仓库名 Ma-minsight-basic。评论区打「分诊」，链接私你；加微信 jarlandliu 聊专业版试用。
```

---

## E. 剪映组装提示词（把 AI 镜头 + 口播拼起来）

```text
1. 新建竖屏项目 1080×1920
2. 按分镜导入 AI 片段，卡点对齐口播句末
3. 字幕：思源黑体/阿里巴巴普惠体，标题字号偏大，每屏不超过 12 字
4. 前 1 秒必须有钩子字幕；3 秒内出现产品名
5. 末 3 秒定格 CTA，停留够长方便截图
6. 导出：抖音/小红书 建议 高清 30fps
7. 封面：大字「Wazuh告警太多？」+ 角标「社区版免费」
```

---

## F. 发布文案（可复制）

### 抖音标题

```text
告警一天三千条，还在人眼刷？开源分诊 MinSight
```

### 小红书标题

```text
Wazuh 告警爆炸？开源 MinSight 做 SIEM 之上的分诊（社区版免费）
```

### 话题

```text
#网络安全 #Wazuh #SIEM #安全运营 #开源 #SOC #程序员
```

### 置顶评论

```text
评论「分诊」发社区版：
Gitee https://gitee.com/jarland/Ma-minsight-basic
GitHub https://github.com/jarland1022/Ma-minsight-basic
专业版试用：微信 jarlandliu（发机器指纹）
```

---

## G. 合规提醒

- 不承诺等保包过、抓黑客、零误报  
- 演示数据脱敏，不出现真实客户 IP  
- 价格口头说「按节点年费详询」即可  

---

## H. 硬广版口播（转化导向 · 慎用，建议第 3 条以后发）

**人设**：直接、敢报动作，仍不碰违规承诺。

### H1 · 15 秒硬广

```text
别再裸奔值班了。
开源 MinSight 社区版，免费把 Wazuh 告警收进来、降噪、聚成事件。
要 AI 写结论、企微找人回话——专业版，按节点年费。
评论「分诊」领仓库；加微信 jarlandliu 要试用。
```

### H2 · 30 秒硬广

```text
三句话讲清楚：
第一，MinSight 不是又一个 SIEM，是 SIEM 上面的分诊层。
第二，社区版免费，Docker 自己装，数据在你内网。
第三，专业版解锁 AI Agent、企微协查、防御资产，同一套系统导入 License 就升。

适合已经有 Wazuh、告警看不过来的团队。
现在评论「分诊」，我发 Gitee/GitHub；要报价和试用，微信 jarlandliu。
```

### H3 · 硬广字幕条（贴画面）

```text
条1：社区版免费自托管
条2：专业版 · AI研判 + 企微协查
条3：微信 jarlandliu · 评论「分诊」
```

---

## I. 方言 / 网感版口播

### I1 · 东北腔网感（抖音完播友好 · 男声）

```text
（15s）
嘿，告警刷一天，眼睛都花了是不是？
再买 SIEM？那叫火上浇油。
开源 MinSight，社区版免费：告警进来、过筛、合成事件。
想让 AI 帮你研判，评论扣「分诊」，整！
```

```text
（45s）
跟你唠实在的：Wazuh 装上了不稀奇，稀奇的是值班还能活人。
一天几千条，同一主机反复响，新人懵、老人靠蒙。

MinSight 干啥？SIEM 负责发现，它负责消化。
社区版开源，自己 Docker 拉起来；专业版再上 AI、企微、防御沉淀。
不用重装，导入 License 就升级。

评论「分诊」我发链接；试用加微信 jarlandliu。整明白了就冲。
```

### I2 · 四川话网感（女声也可）

```text
（15s）
告警炸起了哈？莫再人眼刷起。
开源 MinSight，社区版免费：入库、初筛、聚成事件。
要 AI 研判，评论打「分诊」，我发你仓库。
```

```text
（45s）
先说清楚哦：MinSight 不是又一个 SIEM，是 SIEM 上面做分诊的。
社区版免费自托管；专业版才有 AI Agent、企微协查、防御资产。
已经有 Wazuh、值班看不完的，最合适。
评论「分诊」领社区版；要试用，微信 jarlandliu。
```

### I3 · 普通话「打工人吐槽」网感（男女皆可）

```text
（15s）
同事还在人眼刷告警的时候——
我已经用开源 MinSight 把告警聚成事件了。
社区版免费，评论「分诊」抄作业。
```

```text
（45s）
职场真相：SIEM 越买越忙，不是你不努力，是缺分诊层。
MinSight 社区版：入库、初筛、聚合，先让值班活下来。
专业版再让 AI 写结论、企微找业务回话。
仓库 Ma-minsight-basic。评论「分诊」；微信 jarlandliu。
```

**方言配音提示词（剪映）**

```text
东北：男声，爽利，尾音微扬，语速偏快，不要过度搞笑变形。
四川：女声或男声，亲切，关键字咬清「免费」「分诊」「微信」。
打工人：中性普通话，略带吐槽，但结尾收住专业。
```

---

## J. 五集系列完整口播（建议隔天发 · 同一 CTA）

每集片尾统一：

```text
评论「分诊」领社区版｜微信 jarlandliu 试用专业版
```

### 第 1 集 · 告警太多怎么办（45s）

```text
Wazuh 一天几千条，真正要盯的不到百分之一。
同一规则反复刷，新人看不懂，老人靠肉眼。
再买 SIEM 往往更吵——你要的是分诊层。
开源 MinSight：入库、初筛、聚成事件。社区版免费。
```

### 第 2 集 · 为什么 ChatGPT 不够（45s）

```text
把告警贴进大模型，能写一段分析，但缺三样：
稳定入库、按主机聚合、可审计闭环。
MinSight 先把流水线跑通，再在专业版用 AI 写结论。
顺序反了，只会得到漂亮的废话。
```

### 第 3 集 · 社区版 15 分钟上手（60s · 建议真录屏）

```text
真跑一遍：git clone，复制 .env，docker compose up。
登录控制台，设置里手动跑：入库、初筛、聚合。
事件队列出现 Event，技能库还能看 ATT&CK。
仓库名 Ma-minsight-basic，Gitee 打开更快。
```

### 第 4 集 · 技能库能看什么（45s）

```text
社区版不只是列表。
技能库有精选 Playbooks 和社区扩展包，还能看 ATT&CK 覆盖。
值班时不是从零猜，而是按剧本推进。
AI 自动调查是专业版；剧本浏览社区版就能用。
```

### 第 5 集 · 专业版值不值得（45s）

```text
社区版够你验证「告警能变事件」。
专业版买的是：AI Agent 研判、企微白话协查、防御资产沉淀、有人支持。
同一套安装，导入 License 升级，不用重装。
按节点年费，详询微信 jarlandliu。先评论「分诊」跑社区版。
```

---

## K. 封面 A/B 文案（测点击）

| 组 | 主标题 | 副标题 | 角标 |
|----|--------|--------|------|
| A 痛点 | Wazuh 告警太多？ | 别再人眼刷了 | 社区版免费 |
| B 反差 | 别再买第二个 SIEM | 你缺的是分诊层 | 开源 |
| C 结果 | 告警 3000 → 事件几十 | 15 分钟跑通 | MinSight |
| D 身份 | SOC 值班自救指南 | 入库·初筛·聚合 | 免费 |

小红书优先 A/D；抖音优先 B/C。

---

## L. 私信 / 评论转化话术（SOP）

### L1 · 用户只回「分诊」

```text
你好，社区版（免费自托管）：
Gitee https://gitee.com/jarland/Ma-minsight-basic
GitHub https://github.com/jarland1022/Ma-minsight-basic

建议路径：docker compose up → 设置里跑 入库/初筛/聚合 → 看事件队列。
卡在哪一步可以直接截图发我。
若需要 AI 研判 / 企微协查，加微信 jarlandliu，发机器指纹申请试用。
```

### L2 · 用户问「多少钱」

```text
社区版开源免费。
专业版按节点年费（含 AI Agent、企微协查、防御资产与支持），具体按部署规模报价。
你可以先跑社区版验证；要正式试用/报价，微信 jarlandliu。
```

### L3 · 用户问「和 Wazuh 什么关系」

```text
Wazuh 负责采集和检测；MinSight 负责运营侧消化——入库、降噪、聚成事件，（专业版）再 AI 研判。
不是替换 Wazuh，是加在上面的分诊层。
```

### L4 · 用户问「要不要上云 / 数据安全」

```text
主路径是自托管，数据留在你自己的环境。
Docker Compose 即可；生产加固和驻场可走专业版支持。
```

### L5 · 3 分钟未深聊的轻推

```text
方便说下你现在用的是 Wazuh 还是别的 SIEM、大概日告警量吗？
我可以按你的场景建议：先社区版自助，还是直接开专业版试用。
```

---

## M. 一周排期示例

| 天 | 平台 | 内容 | 口播 |
|----|------|------|------|
| D1 | 抖音 | 15s 镜号表 A | 女声 I3 或 D1 |
| D2 | 小红书 | 第 1 集 | 女声 D2 |
| D3 | 抖音 | 15s 硬广 H1 | 男声 |
| D4 | 小红书 | 第 3 集真录屏 | 男声 C3 |
| D5 | 抖音 | 东北腔 I1 | 男声 |
| D6 | 小红书 | 第 5 集专业版 | 女声 D2 改结尾 |
| D7 | 双平台 | 复盘置顶评论转化，加码私信 L5 | — |

先追 **评论「分诊」数量** 和 **私信要链接数**，再优化封面组 A/B。

---

# English edition (YouTube Shorts / LinkedIn / X / TikTok)

**Positioning one-liner:** SIEM finds alerts. MinSight digests them.

**CTA (EN):** Comment `TRIAGE` for the Community repo · Pro trial: email `jarland@mingansec.com` or WeChat `jarlandliu`

**Repos:**
- GitHub: https://github.com/jarland1022/Ma-minsight-basic  
- Gitee (CN mirror): https://gitee.com/jarland/Ma-minsight-basic  

**Do not claim:** “replaces your SIEM”, “zero false positives”, “instant compliance certification”.

---

## N. EN · 15s AI storyboard (Kling / Jimeng / Runway)

| Shot | Time | Visual | On-screen caption (EN) | Image/video prompt |
|------|------|--------|------------------------|--------------------|
| 1 | 0–3s | Alert counter explodes | 3,000 alerts a day | Vertical 9:16 dark SOC dashboard, red alert counter 200→3842, subtle push-in, tense clean UI, bold English caption |
| 2 | 3–7s | Noise drops to events | Stop scrolling by hand | Same console, list scrolls then count collapses, green checkmark, clean tech UI |
| 3 | 7–12s | Pipeline motion | Open-source MinSight Community | Flat motion: ingest → triage → aggregate → event cards, dark navy, English product caption |
| 4 | 12–15s | End card | Comment TRIAGE · Free self-host | Dark end card, large white CTA, subtitle “Not another SIEM”, minimal shield logo, no purple neon |

**Negative prompt:** human face, blood, hooded hacker, matrix rain, purple neon, cartoon, blurry, watermark, 16:9 landscape

**15s VO (gender-neutral):**

```text
Thousands of Wazuh alerts a day—and you’re still eyeballing them?
Buying another SIEM won’t fix triage.
Open-source MinSight Community: ingest, triage, aggregate into events—free to self-host.
Want AI investigation? Comment TRIAGE.
```

---

## O. EN · 45s AI storyboard

| Shot | Time | Visual | Caption |
|------|------|--------|---------|
| 1 | 0–5s | SOC wall of red dots | Alert fatigue? |
| 2 | 5–12s | Split: more rules vs chatbot with no pipeline | Wrong fixes |
| 3 | 12–22s | Architecture: Wazuh → MinSight → events | SIEM finds. MinSight digests. |
| 4 | 22–34s | Fake product UI: events + ATT&CK board | Community can run this |
| 5 | 34–40s | Community vs Pro unlock cards | Upgrade with a license |
| 6 | 40–45s | CTA | GitHub Ma-minsight-basic · Comment TRIAGE |

**Global style prompt:**

```text
Vertical 9:16 cybersecurity product marketing, restrained dark navy UI, crisp typography, no gore, no hooded hacker cliché, no purple neon glow, corporate-trustworthy
```

---

## P. EN voiceover · Male (calm SOC lead)

**Voice casting prompt:** Male, ~30, calm and practical, mid-fast pace, no hype salesman tone.

### P1 · 15s

```text
Three thousand alerts a day—still scrolling by hand?
Another SIEM just adds noise.
Open-source MinSight: ingest, triage, aggregate into events. Community is free.
Need AI investigation? Comment TRIAGE.
```

### P2 · 45s

```text
Most teams already run Wazuh. The hard part isn’t detection—it’s digestion.
A tiny fraction of alerts matter. The same host and rule keep paging you. Juniors can’t read rule IDs; seniors eyeball the queue.

Piling on more SIEM rules usually makes it louder. Pasting alerts into a chatbot writes prose—without ingest, aggregation, or an audit trail.

MA-MinSight sits above your SIEM: ingest, rule triage, aggregate into events.
Community Edition is Apache open source—Docker it yourself.
Pro unlocks the AI agent, chat-ops review, and defense-asset loop—same install, import a license.

Comment TRIAGE for the repo. For a Pro trial, email jarland@mingansec.com.
```

### P3 · 60s

```text
If you work a SOC shift, you know the feeling: a wall of red, the same rule looping, newcomers lost, veterans filtering by gut.

Buying another SIEM rarely helps. You need a triage layer—not a second detection engine.

MA-MinSight ingests alerts from Wazuh-class sources, triages them, and aggregates by host, user, and category into workable events.
Community includes the console and ATT&CK-oriented playbooks. Pro adds AI conclusions, human review over chat, and defense learning.

Fifteen-minute goal: see alerts become events.
Repo: Ma-minsight-basic on GitHub.
Comment TRIAGE—or email jarland@mingansec.com for Pro.
```

---

## Q. EN voiceover · Female (clear tech-creator)

**Voice casting prompt:** Female, 25–32, clear and crisp, slightly fast, confident, no cute / ASMR tone.

### Q1 · 15s

```text
Wazuh alert storm? Stop relying on eyeballs.
Open-source MinSight Community: ingest, reduce noise, aggregate into events—free self-host.
It’s not another SIEM. It’s the triage layer on top.
Comment TRIAGE for the repo.
```

### Q2 · 45s

```text
Bottom line: when alerts explode, another SIEM often won’t save you—you need triage.

MA-MinSight Community is free and open source. After you connect Wazuh, run ingest → triage → aggregate, then work from the event queue. Playbooks show ATT&CK coverage too.

Pro adds the AI agent, chat-based human review, and defense-asset retention—upgrade with a license, no reinstall.

Best fit: teams that already detect, but can’t staff the queue.
Comment TRIAGE. Pro trial: jarland@mingansec.com.
```

### Q3 · 60s

```text
Anyone else ship a SIEM… then drown in alerts?

More rules → more noise. ChatGPT on raw alerts → nice paragraphs, no ingest, no aggregation, no audit loop.

So we built MA-MinSight. Clear job split: SIEM finds, MinSight digests.
Community turns alerts into events you can actually work.
Pro lets AI and chat-ops turn events into conclusions.

Self-hosted. Your data stays with you.
Search Ma-minsight-basic on GitHub. Comment TRIAGE, or email jarland@mingansec.com for Pro.
```

---

## R. EN hard-sell (use after trust content)

### R1 · 15s

```text
Stop burning shifts on raw alerts.
MinSight Community—free—pulls Wazuh alerts in, triages, aggregates to events.
Need AI write-ups and chat-ops review? That’s Pro, per-node annual.
Comment TRIAGE for the repo. Email jarland@mingansec.com for a trial.
```

### R2 · 30s

```text
Three facts:
One—MinSight is not another SIEM; it’s the triage layer above it.
Two—Community is free, Docker self-hosted, data in your network.
Three—Pro unlocks AI agent, human review, defense assets—same stack, license upgrade.

If you already run Wazuh and can’t keep up, start Community today.
Comment TRIAGE. Quote / trial: jarland@mingansec.com.
```

---

## S. EN five-episode series VO

**Unified end card:**

```text
Comment TRIAGE for Community · Pro trial: jarland@mingansec.com
```

### Ep.1 · Alert fatigue (45s)

```text
Thousands of Wazuh alerts a day—maybe one percent deserve eyes.
Same rule, same host, endless pages.
Another SIEM often gets louder. You need triage.
Open-source MinSight: ingest, triage, events. Community is free.
```

### Ep.2 · Why ChatGPT isn’t enough (45s)

```text
Pasting alerts into an LLM can draft analysis—but you’re missing three things:
reliable ingest, host-window aggregation, and an auditable loop.
MinSight runs the pipeline first; Pro uses AI for conclusions.
Reverse that order and you get pretty noise.
```

### Ep.3 · Community in 15 minutes (60s · prefer real screen recording)

```text
Real path: git clone, copy .env, docker compose up.
In Settings, run ingest → triage → aggregate.
Open Events—you should see Event records. Playbooks show ATT&CK coverage.
Repo name: Ma-minsight-basic on GitHub.
```

### Ep.4 · Playbooks (45s)

```text
Community isn’t only a table view.
You get curated playbooks, a community pack, and an ATT&CK coverage board.
Analysts follow a script instead of guessing from zero.
Automated AI investigation is Pro; browsing playbooks is free in Community.
```

### Ep.5 · Is Pro worth it? (45s)

```text
Community proves alerts can become events.
Pro buys: AI agent investigation, chat-ops review, defense-asset learning, and support.
Same install—import a license, no reinstall.
Per-node annual pricing—email jarland@mingansec.com.
Comment TRIAGE and run Community first.
```

---

## T. EN cover / title A-B tests

| Variant | Hook title | Subtitle | Badge |
|---------|------------|----------|-------|
| A Pain | Wazuh alert overload? | Stop scrolling by hand | Free Community |
| B Contrast | Don’t buy a second SIEM | You need a triage layer | Open source |
| C Result | 3,000 alerts → dozens of events | Run it in 15 minutes | MinSight |
| D Role | SOC shift survival guide | Ingest · Triage · Aggregate | Free |

**YouTube Shorts / TikTok titles:**

```text
Thousands of alerts a day—still eyeballing them?
Not another SIEM. A triage layer on top of Wazuh.
Open-source MinSight Community (free self-host)
```

**LinkedIn (slightly more formal):**

```text
Alert fatigue isn’t a detection problem—it’s a triage problem.
MA-MinSight Community (Apache-2.0) sits above Wazuh-class SIEMs: ingest → triage → aggregate.
Pro adds AI investigation and chat-ops review.
Repo: github.com/jarland1022/Ma-minsight-basic
```

**Hashtags:**

```text
#CyberSecurity #SOC #SIEM #Wazuh #OpenSource #AlertFatigue #SecOps #DevSecOps
```

---

## U. EN DM / comment SOP

### U1 · User comments `TRIAGE`

```text
Here’s MA-MinSight Community (free, self-hosted):
https://github.com/jarland1022/Ma-minsight-basic

Suggested path: docker compose up → Settings: ingest / triage / aggregate → Events queue.
Stuck? Send a screenshot.
For AI investigation / chat-ops review (Pro), email jarland@mingansec.com with your machine fingerprint—or WeChat jarlandliu.
```

### U2 · “How much?”

```text
Community is free and open source.
Pro is per-node annual (AI agent, human review, defense assets, support)—quote depends on footprint.
Run Community first; for trial/pricing: jarland@mingansec.com.
```

### U3 · “Relation to Wazuh?”

```text
Wazuh detects and collects. MinSight digests—ingest, noise reduction, event aggregation, and (Pro) AI investigation.
It doesn’t replace Wazuh; it sits on top as a triage layer.
```

### U4 · “Cloud / data residency?”

```text
Primary path is self-hosted—data stays in your environment.
Docker Compose to start; hardening and on-site help are available with Pro support.
```

### U5 · Soft nudge

```text
Are you on Wazuh or another SIEM, and roughly what’s your daily alert volume?
I can suggest Community DIY vs a Pro trial for your case.
```

---

## V. EN week schedule (intl platforms)

| Day | Platform | Asset | VO |
|-----|----------|-------|----|
| D1 | TikTok / Shorts | 15s storyboard N | Q1 female |
| D2 | LinkedIn | Ep.1 text + clip | P2 male |
| D3 | Shorts | Hard-sell R1 | P1 male |
| D4 | YouTube Shorts | Ep.3 screen record | P3 male |
| D5 | X / TikTok | Cover C + 15s | Q1 |
| D6 | LinkedIn | Ep.5 Pro value | Q2 |
| D7 | All | Pin U1 reply; DM U5 to warm leads | — |

**Metrics:** count of `TRIAGE` comments · repo clicks · trial emails.

---

## W. Bilingual end-card (CN + EN, same video)

Use when posting to both CN and global audiences:

```text
评论「分诊」/ Comment TRIAGE
Community: github.com/jarland1022/Ma-minsight-basic
Pro: jarland@mingansec.com · WeChat jarlandliu
```

**Bilingual 15s VO (optional dual subtitle track):**

```text
EN: SIEM finds. MinSight digests. Community free—comment TRIAGE.
CN: SIEM 负责发现，MinSight 负责消化。社区版免费——评论「分诊」。
```
