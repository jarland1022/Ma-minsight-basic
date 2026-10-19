# 在公开仓库发布落地页（Ma-minsight-basic）

**正确仓库：** https://github.com/jarland1022/Ma-minsight-basic（Public）  
**不要**在私有专业版仓库里开 Pages / 加 Variables。

| 仓库 | 用途 |
|------|------|
| `Ma-minsight-basic`（公开） | 社区版代码 + **英文落地页** + GitHub Pages |
| 私有 AI-SEC / Pro | 完整商业代码，保持 Private，勿挂营销站 |

落地页发布后地址一般为：

`https://jarland1022.github.io/Ma-minsight-basic/`

对标 Ma-WAF：`https://jarland1022.github.io/Ma-waf-basic/`

---

## 1. 推送本仓库（含 workflow）

确保远程已有：

- `.github/workflows/pages-landing.yml`
- `docs/marketing/landing.html`

```powershell
cd D:\AI\Ma-minsight-basic
git add .github/workflows/pages-landing.yml docs/marketing/
git status
git commit -m "Add public landing page and GitHub Pages workflow"
git push origin main
```

---

## 2. 添加 Variables（关键）

打开：**https://github.com/jarland1022/Ma-minsight-basic**

1. **Settings**  
2. **Secrets and variables** → **Actions**  
3. 上方 **Variables**（不是 Secrets）  
4. **New repository variable**：

| Name | Value |
|------|--------|
| `WHATSAPP_URL` | `https://wa.me/8613717098262` |
| `CALENDLY_URL` | `https://calendly.com/leonliu/ma-minsight-consult`（若尚未建事件，可先填 WhatsApp 同链或已有 ma-waf-consult） |
| `GITHUBURL` | `https://github.com/jarland1022/Ma-minsight-basic` |
| `EMAIL` | `jarland@mingansec.com` |
| `COMPANY` | `Mingansec` |

可选：`CNAME` = 自定义域名。

**不要**点 Actions 里的 *Create your own workflow*。

---

## 3. 打开 Pages

同一仓库：**Settings → Pages → Source → GitHub Actions**

---

## 4. 运行发布

1. 顶部 **Actions**  
2. 左侧 **Deploy landing (GitHub Pages)**  
3. **Run workflow**  
4. 变绿后打开：`https://jarland1022.github.io/Ma-minsight-basic/`  

自测：Chat on WhatsApp / Email / Try on GitHub 三个按钮。

---

## 5. 接到获客漏斗

1. LinkedIn Featured 钉落地页（[`overseas/linkedin-pack.md`](overseas/linkedin-pack.md)）  
2. Upwork 简介放落地页（[`overseas/upwork-packages.md`](overseas/upwork-packages.md)）  
3. Medium / Reddit CTA 用同一 URL（[`overseas/platforms-publish.md`](overseas/platforms-publish.md)）  

本地预览（不替换占位符）：用浏览器打开 `docs/marketing/landing.html`。
