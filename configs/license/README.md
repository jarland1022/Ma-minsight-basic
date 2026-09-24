# MA-MinSight License（社区仓库说明）

本目录用于放置：

| 文件 | 是否进 Git | 说明 |
|------|------------|------|
| `ma-minsight-public.pem` | ✅ 已收录（验签公钥） | 导入专业版 License 时用于验签 |
| `license.lic` | **禁止提交** | 客户节点授权文件（Docker 卷挂载持久化） |
| `*-private.pem` | **禁止出现在本仓库** | 仅厂商签发机保存 |

社区版默认**不提供**自动 Pro 试用宽限。导入有效 `license.lic` 并**重启应用**后，解锁 Agent / 企微协查 / 防御资产 / 评测。

Compose 已挂载 `./configs/license` → `/app/configs/license`，避免重建镜像丢失授权文件。

购买与试用：微信 `jarlandliu`，邮箱 `jarland@mingansec.com`。  
能力对照：[`docs/community-vs-pro.md`](../docs/community-vs-pro.md)。
