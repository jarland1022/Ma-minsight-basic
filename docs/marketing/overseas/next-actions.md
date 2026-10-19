# MA-MinSight — 下一步（按优先级）

联系：[`contacts.md`](contacts.md) · 社区仓：https://github.com/jarland1022/Ma-minsight-basic

对标做法：`D:\AI\Ma_waf\docs\marketing\overseas\next-actions.md`（同一套海外获客节奏，产品换成 MinSight）。

## 本周必做（LinkedIn + Upwork 主获客）

1. **WhatsApp Business**  
   - 确认 https://wa.me/8613717098262 可聊  
   - 保存 Quick Reply（见 [`contacts.md`](contacts.md)）  

2. **GitHub 社区仓英文首页**  
   - 确认 `README.md` 为英文默认，可切 [`README.zh-CN.md`](../../../README.zh-CN.md)  
   - push：`https://github.com/jarland1022/Ma-minsight-basic`  

3. **英文落地页（GitHub Pages）** — 文案与 workflow **已就绪**；你只需发布  
   - 手册：[`../GITHUB_PAGES.md`](../GITHUB_PAGES.md)  
   - push：`docs/marketing/landing.html` + `.github/workflows/pages-landing.yml`  
   - Settings → Pages → Source = **GitHub Actions**  
   - 填 Variables：`WHATSAPP_URL` / `CALENDLY_URL` / `GITHUBURL` / `EMAIL` / `COMPANY`  
   - Actions → **Deploy landing (GitHub Pages)** → Run workflow  
   - 上线后：`https://jarland1022.github.io/Ma-minsight-basic/`  
   - 本地预览：浏览器打开 `docs/marketing/landing.html`（占位符未替换属正常）  

4. **LinkedIn（主获客）** — [`linkedin-pack.md`](linkedin-pack.md)  
   - 改 Headline + About  
   - Featured 钉：**落地页** + GitHub + WhatsApp  
   - 本周发 **Post A（告警疲劳）**；隔 1–2 天发 Post B / C  

5. **Upwork 两包上架** — [`upwork-packages.md`](upwork-packages.md)（含 How to publish）  
   - Package 1：Deploy / onboard MinSight（固定价）  
   - Package 2：Monthly managed alert triage（月费）  
   - Portfolio 挂落地页 + Demo  
   - 同步搜索 Job：`Wazuh` / `SIEM` / `SOC` / `alert fatigue` 主动投标  

6. **价格口径统一** — 对外用 Founding：见 [`pricing.md`](pricing.md)  
   - 全平台清单：[`platforms-publish.md`](platforms-publish.md)  

7. **（可选）Calendly**  
   - 新建事件 `ma-minsight-consult`，Location = WhatsApp typed chat  
   - 更新 Pages Variable `CALENDLY_URL` 后重新 Deploy landing  

## 下周（内容放量）

- [ ] 录 3–5 分钟 Demo（[`demo-video-script.md`](demo-video-script.md)）或 Loom，贴 LinkedIn  
- [ ] Medium / Dev.to 一文（[`medium-devto-article.md`](medium-devto-article.md)）  
- [ ] Reddit 价值帖 1 条（[`reddit-posts.md`](reddit-posts.md)）— 别硬广  
- [ ] 短视频可用 [`../../video-prompts-xiaohongshu-douyin.md`](../../video-prompts-xiaohongshu-douyin.md) 英文章（EN Shorts）  

## 有人进线后（转化）

按 [`demo-outreach.md`](demo-outreach.md)：

```text
WhatsApp 打字摸清 SIEM/告警量 → Demo → Pilot → Pro License / Managed
```

目标：本周 **≥3 次有效咨询**；四周内 **≥1 个付费 Pilot**。

## 转化口径

```text
曝光(LinkedIn/Upwork/GitHub) → Community Docker 试用 → WhatsApp → Pilot → 付费 Pro/Managed
```

## 与 Ma-WAF 协同

| 买家痛点 | 主推 |
|----------|------|
| Web 攻击 / 入口防护 | Ma-WAF |
| Wazuh/SIEM 告警看不过来 | **MA-MinSight** |
| 两者都有 | 组合报价（WAF + triage） |
