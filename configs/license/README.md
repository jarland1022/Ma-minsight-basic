# MA-MinSight License (Community)

Files in this directory:

| File | In Git? | Notes |
|------|---------|--------|
| `ma-minsight-public.pem` | Yes (verify key) | Used to verify Professional `license.lic` |
| `license.lic` | **Never commit** | Customer node license (persisted via Docker volume) |
| `*-private.pem` | **Must not appear** | Vendor signing machine only |

Community has **no** silent Pro trial. Import a valid `license.lic` and **restart** to unlock Agent / WeCom review / defense assets / eval.

Compose mounts `./configs/license` → `/app/configs/license`.

Contact: WeChat `jarlandliu` · email `jarland@mingansec.com`  
Compare editions: [`docs/community-vs-pro.md`](../docs/community-vs-pro.md) · [中文](../docs/community-vs-pro.zh-CN.md)
