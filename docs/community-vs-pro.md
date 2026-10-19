# Community vs Professional

[**English**](community-vs-pro.md) | [中文](community-vs-pro.zh-CN.md)

Community Edition is published on GitHub / Gitee so teams can **ingest Wazuh alerts, reduce noise, aggregate into events**, and browse playbooks / ATT&CK coverage. Professional sells **AI investigation + chat-ops collaboration + defense feedback + accountable support** — not another "alert list UI".

## Pricing (suggested)

| Item | Suggestion |
|------|------------|
| Community | Free, Apache-2.0 |
| Professional | **¥9,800 / node / year** (negotiable; priced as a SOC companion tool) |
| Trial | Time-boxed `license.lic` issued by vendor (Community repo has **no** silent 72h Pro grace) |
| Higher tiers | Multi-node, on-site tuning, private SOP packs — separate quote |

After Community is installed, import a valid License and restart to unlock Pro on the same codebase — no reinstall.

## Capability matrix

| Capability | Community | Pro |
|------------|:---------:|:---:|
| Wazuh / Mock ingest | Yes | Yes |
| Rule triage + aggregation | Yes | Yes |
| Events / dashboard / noisy rules | Yes | Yes |
| Playbooks (curated + community pack) and ATT&CK coverage | Yes | Yes |
| Local login | Yes | Yes |
| Docker Compose self-host (License volume) | Yes | Yes |
| LLM ReAct agent investigation | No | Yes |
| Disposition grade / evidence labels | Fields exist (no Agent output when locked) | Produced by Agent |
| Behavior timeline / sample enrichment skills | In tree (usable after Agent unlock) | Yes |
| WeCom human review | No | Yes |
| Defense assets / case learning | No | Yes |
| Threat-intel sync enrichment | Limited | Yes |
| Regression / health-check eval | No | Yes |
| Commercial support and contracts | No | Yes |

## Maintainer notes

- `EDITION=community`: no silent Pro trial; skip Agent / human-review / defense / eval schedulers when unlicensed.
- Pro APIs use route-level `require_pro_license` (do not port Pro global LicenseGateMiddleware — it would block free ingest/triage).
- Repo ships `ma-minsight-public.pem`; no private keys or `license_gen`.
- Docker: `MA_MINSIGHT_LICENSE_DIR` + `./configs/license` mount so licenses survive rebuilds.

## Why this split

Community must install, show fewer alerts, populate events, and browse playbooks — or there are no stars and no leads. Pro must lock the Agent and enterprise collaboration — or open source leaves no reason to pay.

## Go-to-market path

1. README + Compose: ingest to triage to aggregate in about 15 minutes.
2. Articles: "SIEM detects, MinSight triages" with GitHub/Gitee links.
3. Console License banner + fingerprint contact.
4. Trial licenses issued only from sales.
5. Chinese content still helps CN discovery; GitHub README defaults to English.

## Release checklist

- [ ] `EDITION` is `community`
- [ ] No private pem, license.lic, or customer IPs/certs in git
- [ ] No `tools/license_gen.py`
- [ ] `ma-minsight-public.pem` present
- [ ] `docker compose up -d --build` health shows `edition=community`
- [ ] Unlicensed investigation manual run returns 402
- [ ] Playbooks list community pack / coverage
- [ ] Default `README.md` is English; `README.zh-CN.md` linked
- [ ] No claims of compliance certified or full SIEM replacement
