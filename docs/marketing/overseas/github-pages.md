# Deploy MinSight landing to GitHub Pages

**操作手册（权威）：** [`../GITHUB_PAGES.md`](../GITHUB_PAGES.md)

| Item | Value |
|------|--------|
| Public repo | https://github.com/jarland1022/Ma-minsight-basic |
| Landing source | [`../landing.html`](../landing.html) |
| Workflow | `.github/workflows/pages-landing.yml` |
| Live URL (after deploy) | `https://jarland1022.github.io/Ma-minsight-basic/` |

## Dual-repo rule

| Repo | Local | Add Variables / Pages? |
|------|-------|------------------------|
| **Community public** | `D:\AI\Ma-minsight-basic` | **YES** |
| Pro private (`AI-SEC`) | `D:\AI\AI-SEC` | **NO** |

改文案：编辑 `docs/marketing/landing.html` → push 公开仓 → Actions 自动或手动 Deploy。

Variables 名必须用：`WHATSAPP_URL` · `CALENDLY_URL` · `GITHUBURL` · `EMAIL` · `COMPANY`（注意是 `GITHUBURL`，不是 `GITHUB_URL`）。
