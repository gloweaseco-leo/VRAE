# PR176 已部署及 Preview 私有交接

Owner 明确批准部署 PR176，并确认沿用原 Preview 身份续期及私有交接。
实际部署源码为 `7a097486e36892484034e1ee69be7d6dff2c4dbe`。
本目录只记录部署事实，不修改已批准源码；文档提交不是运行镜像源码 SHA。

- 原诊断入口：`https://dong.tail27555e.ts.net`。
- 镜像：`sha256:7c3b0dc2f566223170d32d8465c54fb37fea38d2fae769c8f0221290b898e78d`。
- 原实例 `vrae-windows` 的 PG、Worker、APP、REVIEW、AI 及转发继续运行。
- 原初始化追加 migration006；原签发器启用 `VRAE-AUTO-DIAGNOSIS-1` 一次授权入口。
- 模型沿用原费用许可及共享账本，日上限 CNY5，许可仍截至 2026-11-30T15:59:59Z。

## 已完成的实际核验

`verification.json` 记录续期 Preview 身份的实际 mTLS 调用：健康、OpenAPI、
一次授权契约均为200；错误 Bearer 为403；服务响应绑定实际部署 SHA。
`public-check.json` 通过原公网443/Funnel地址复核相同结果。该调用来自同一宿主上
新建的 bridge 操作器，不冒称独立外部网络或 VF/Vercel BFF 出站验证。

冷备份已写入独立 Linux 私有卷 `vrae-windows-pr176-backups`，包含原 PG、报告 Ledger
及原操作材料的受保护备份。原20份采集 artifact 哈希全部保留。
共享模型账本只读核对仍为原9笔，逻辑哈希与部署前完全一致；未复制、重置或退款。
隔离 AI 已实际读取并验证新版本许可，供应商目的地址固定2个，配置有效。
没有提交客户网址、没有付费模型探测；不以健康或配置核验冒充真实 AI 诊断验收。

## VF 后续接入

沿用原 `vf_preview_20261120a` APP 角色，epoch=1及原私钥保持不变；更新叶证书及角色期限。
新的单次邀请绑定新主体，目标列表为空，旧邀请和任务记录未被恢复或改写。
Preview 身份/邀请到期：**2026-11-21T05:16:57Z，北京时间11月21日13:16:57**。
这是本次24小时续期，不等于全局Nov30许可期限。

六项连接变量已通过原认证账号，直接写入 `gloweaseco-1757s-projects/veyfront` 的
`Preview / feature/vf-b-offline-g1-adapter`，并经 Vercel connector 重新确认其分支、
目标环境、Sensitive 类型及更新时间。见 `private-delivery.json` 和
`private-delivery-metadata.json`。没有回读秘密，密钥/令牌未写入NTFS、GitHub或聊天。

**VF 团队需重新部署该 Preview 分支，以加载续期证书、源码 SHA 和新邀请。**
没有改 VF 源码、启用开关、Production 或触发 VF 部署；未声称 VF BFF/UI 已完成端到端验收。
新邀请在实际消费后应从 Preview 环境删除，按原方式恢复用户会话；客户只输入网址和勾选一次授权。

## 宿主恢复及运行条件

宿主曾因 D 盘空间耗尽而发生 Docker/WSL I/O 故障。Owner 释放空间并要求继续后，
使用官方 Docker 重启和 WSL 关闭/重新启动恢复原数据盘连接；未注销发行版、
重装或重置 Docker、未执行文件系统修复。原数据盘挂载恢复后，旧业务容器因旧 PG
内部转发地址失效进入重启循环，已由原受信控制器重启并重新绑定实际 PG 地址。
随后在无待处理任务时完成备份和升级。

最后核验 D 盘仅约300MB空闲，仍需继续释放宿主空间以防再次中断。
本轮未清理其他项目、历史证据或数据卷，未改变系统代理、VPN、DNS或路由。
此前 Windows 登录、Docker/Tailscale/网络和开机条件仍适用。

恢复参考：[Docker 数据保全](https://docs.docker.com/desktop/settings-and-maintenance/backup-and-restore/)、
[Microsoft WSL 磁盘说明](https://learn.microsoft.com/en-us/windows/wsl/disk-space)。
