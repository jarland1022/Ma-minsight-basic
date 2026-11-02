# MA-MinSight Community

**English** | [中文](README.zh-CN.md)

Self-hosted **SIEM alert triage** for teams that already run Wazuh (or similar).

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Edition](https://img.shields.io/badge/Community-open%20source-brightgreen)](docs/community-vs-pro.md)

Repositories:
- GitHub: https://github.com/jarland1022/Ma-minsight-basic
- Gitee: https://gitee.com/jarland/Ma-minsight-basic

## What it does

- Routes low-signal noise vs cases that need a human (ingest → rule triage → event aggregation → console)
- Playbooks / ATT&CK coverage board for the investigation workspace
- Optional **Professional** upgrade: AI agent investigation, human review, defense-asset loop, eval suite
- Optional assisted overnight review / **morning note** for day shift (commercial / Pro workflows)

## What it does NOT do

- Silent firewall / WAF policy push
- Replace your SIEM
- Require sending your logs to our cloud (runs on **your boundary**)

## Try / demo

| Asset | Link |
|-------|------|
| Product (EN) | https://www.mingansec.com/en/minsight.html |
| Docker trial guide | https://www.mingansec.com/en/docker-trial.html |
| Sample morning note (demo data) | https://www.mingansec.com/en/morning-note-sample.html |
| 3-min walkthrough (Loom) | https://www.loom.com/share/f0560485ff674c7d91d08908977760a7 |

**Community Edition** (this repo): open-source console — **Ingest → rule triage → event aggregation → console**.

**Professional** (AI agent, WeCom/human review, defense-asset loop, eval, commercial support) unlocks with a **License** — not enabled by default.  
Contact: email `jarland@mingansec.com` · WeChat `jarlandliu`.  
Compare editions: [`docs/community-vs-pro.md`](docs/community-vs-pro.md) · [中文对照](docs/community-vs-pro.zh-CN.md).

## Feedback

Open a GitHub Issue with: **SIEM type**, **alert volume/day**, and whether you need **overnight coverage**.

## What Community includes

| Capability | Notes |
|------------|--------|
| Install | Docker Compose / local Python + Vite |
| Alert ingest | Wazuh Indexer / Mock sources |
| Rule triage | Noise reduction, allowlists, archive or escalate; noisy-rules on the dashboard |
| Event aggregation | Host + user + category + time window → Event |
| Playbooks | Curated catalog + community pack; ATT&CK coverage board |
| Console | Dashboard, event queue, user guide, License page (**English default**, switch to 中文) |
| License | Public verify key ships in-repo; import `license.lic` and restart to unlock Pro |

**Not included (requires Pro License):** LLM ReAct agent, WeCom human review, defense-asset learning, regression / health-check eval, on-site commercial delivery.

## Quick start

Requires Docker (recommended), or Python ≥3.11 + Node 18+ with PostgreSQL and Redis.

```bash
git clone https://github.com/jarland1022/Ma-minsight-basic.git
# China mirror: git clone https://gitee.com/jarland/Ma-minsight-basic.git
cd Ma-minsight-basic

cp .env.example .env
# Set POSTGRES_PASSWORD, API_KEY, JWT_SECRET, etc.

docker compose up -d --build
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1/ (or `HTTP_PORT` in `.env`) | Web console (nginx) |
| App `/health` | Should report `edition=community` |

Default admin password comes from `ADMIN_INITIAL_PASSWORD` in `.env` (example: `changeme`). After login:

1. **Settings → Run pipelines manually**: ingest → triage → aggregate  
2. Open **Events** and confirm Event rows appear  
3. Browse **Playbooks** / ATT&CK coverage  

The console defaults to **English**. Use **EN | 中文** on the login page or header to switch; the choice is stored in the browser. See [`docs/i18n.md`](docs/i18n.md).

### Local development (optional)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

cd web && npm install && npm run dev
```

## Upgrade to Professional

1. Open **System → License** and copy the machine fingerprint.  
2. Obtain `license.lic` from the vendor (`ma-minsight-public.pem` is already under `configs/license/`).  
3. Import the `.lic` in the UI (or place it at `configs/license/license.lic`) and **restart the app**.  
4. Unlocks: AI agent, human review, defense assets, eval (including disposition grading).

Community has **no** silent 72-hour Pro trial; trial licenses are issued by fingerprint.

## Layout

```text
app/                 # FastAPI (Community always on; Pro APIs need License)
web/                 # React console (EN default, ZH switch)
alembic/             # DB migrations (incl. disposition grade 018)
app/playbooks/       # catalog + community_pack + ATT&CK
configs/license/     # public key (never commit private keys / license.lic)
deploy/              # Docker / nginx
docs/                # docs & articles
EDITION              # community
LICENSE / NOTICE     # Apache-2.0
```

## Docs

- [`docs/community-vs-pro.md`](docs/community-vs-pro.md) — Community vs Pro (English)  
- [`docs/community-vs-pro.zh-CN.md`](docs/community-vs-pro.zh-CN.md) — 中文对照  
- [`docs/i18n.md`](docs/i18n.md) — Console language (EN default / 中文)  
- [`docs/article-siem-minsight.md`](docs/article-siem-minsight.md) — Chinese launch article  
- [`docs/video-prompts-xiaohongshu-douyin.md`](docs/video-prompts-xiaohongshu-douyin.md) — CN/EN short-video prompts  
- [`docs/marketing/overseas/`](docs/marketing/overseas/) — **LinkedIn / Upwork / overseas GTM**  
- [`docs/marketing/landing.html`](docs/marketing/landing.html) · [`docs/marketing/GITHUB_PAGES.md`](docs/marketing/GITHUB_PAGES.md) — **English landing → GitHub Pages**  
- [Ma-WAF Community](https://github.com/jarland1022/Ma-waf-basic) — open-source WAF  

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
