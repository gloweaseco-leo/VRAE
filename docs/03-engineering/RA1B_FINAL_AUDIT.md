# RA-1B 恢复核验与最终工程审计

> B6后续记录：[可靠性收口](RA1B_B6_RELIABILITY.md)。下文SECURITY_BLOCKED为历史失败，
> 最终候选结论以B6门禁及Draft PR #6上对应最终SHA的四项CI实际结果为准。

## 最终状态：SECURITY_BLOCKED

最终文档HEAD `66d910284c0ad1d4fe1bf2ac32b09c37bd3b3807` 的
[run42968878052](https://github.com/gloweaseco-leo/VRAE/actions/runs/42968878052)
出现真实失败，优先于下述历史PASS。Python3.11、3.13及isolated-http均success；
isolated-browser job130352416147失败，前15场景Worker退出0，最后worker_kill预期137，
但紧接着的inspect仍显示浏览器Running，监督器抛出
`SECURITY_BLOCKED: browser did not exit after control disconnect`。
finally中的docker rm和volume rm成功、删除后inspect为1，证明强制回收完成；
**不能证明控制通道断开后的自动退出可靠**，不得绕过断言或用重跑PASS掩盖。
可能涉及退出时序竞争，尚未确认根因，不宣称已修复。
按Owner停止条件停止受影响浏览器工作，保持Draft，不合并、不部署、不进入RA-2。
下一轮须先定位强杀后Chromium/relay退出时序及进程证据，再修复并完整验收；
禁止关闭Sandbox、放宽出网或删除清理断言。

[完整失败日志](ra1b-evidence/hosted-final-browser-failure.log)；
[198文件原始artifact13833300062](https://github.com/gloweaseco-leo/VRAE/actions/runs/42968878052/artifacts/13833300062)，
ZIP SHA256 `486674355430fd6e3901fb615c9ae33bc9448dbec9cbef82ac33043aa888fa5d`。
未见未授权连接或写入成功证据，但清理门禁未通过，整体不得宣称PASS。
下文仅为首次实现CI的历史记录，不代表最终结论。

## 首次实现CI历史记录

2026-11-11 恢复开发后重新 fetch：远端 main 仍为
`8bc460764dedb6a87c2e7806b2d3b382875596de`，未覆盖既有成果。
实现提交 `474ef34c1f7f1f839e2e3f90ca080c2b0130a202`，首次 PR CI 检出合并引用
`32f6b7eb6001da7204cdeae8260ab72431d5944c`（不是合并到 main）。
[run 42966852022](https://github.com/gloweaseco-leo/VRAE/actions/runs/42966852022)
于 05:36–05:39 UTC 实际执行，四个 job 全部 success：

| Job | 结果 | 原始日志 |
|---|---|---|
| 130345932431 / CPython 3.11.18 | 425通过 / 0失败 / 25跳过；五项工程门禁通过 | [3.11](ra1b-evidence/hosted-311.log) |
| 130345932401 / CPython 3.13.18 | 425通过 / 0失败 / 25跳过；五项工程门禁通过 | [3.13](ra1b-evidence/hosted-313.log) |
| 130345932548 / Linux isolated-http | 449通过 / 0失败 / 1浏览器专用跳过；五项工程门禁通过 | [HTTP](ra1b-evidence/hosted-http.log) |
| 130345932213 / Linux isolated-browser | 内核、Sandbox门禁及16场景达到预期；无场景跳过 | [浏览器监督日志](ra1b-evidence/hosted-browser.log) |

五项门禁为 compileall、Ruff、mypy、pytest、pip check；原 RA-0/RA-1A 测试保留。
Runner 为 Ubuntu26.04.1，image ubuntu-26.04 / 20261101.186.1。
浏览器测试与普通 pytest 分开计数：15次 pytest 通过，另一次 Worker 强杀137；
删除后 inspect 的1为预期对象不存在，不能将这些退出码误报为测试失败或普通测试通过。
详细198份托管浏览器原始文件保存在
[CI artifact 13831223248](https://github.com/gloweaseco-leo/VRAE/actions/runs/42966852022/artifacts/13831223248)，
上传ZIP SHA256 `b66392c95d715da65d78f895443b81cffd550bccc69b11ce1e1d35fdd6d590fe`。
Artifact受GitHub保留期约束；仓库另保留本地完整实验归档及哈希索引。

本次恢复提交只补充文档与已执行CI日志，不改变实现、依赖、权限或测试断言。
因此以上计数绑定实现提交；最终文档HEAD的CI在PR另行报告，不冒称已经运行。

实现后的第二轮代码审查覆盖 Broker → RA-1A、CDP消息/任务边界、容器参数、
seccomp和强杀清理。这里的独立审计指与实现分开的审查活动，不冒称外部认证或另一位审计人员。
无新增Python运行依赖、大型框架、微服务产品或业务范围膨胀。
NET_ADMIN只用于合成Worker启动阶段配置防火墙，降权后清空；浏览器capabilities始终为空。
Namespace/chroot syscall许可用于启用Chromium自身Sandbox，没有关闭Sandbox。
未授权连接及实际写入在合成验收中的成功次数均为0，内核阻断独立于浏览器资源路由。
完整攻击触发标记、Broker拒绝、诱饵方法/目标、资源限制和清理记录见
[证据索引](ra1b-evidence/README.md)，历史失败未删除。

首次CI工程判断曾为PASS；已被上方最终HEAD的SECURITY_BLOCKED取代。
最终验收仍由Owner和首席架构师决定；保持Draft PR，不自行合并。
该判断不代表生产安全认证或真实站点适配通过。

剩余限制：跨域CDN暂全部拒绝；Other/favicon可能使观察保留ACCESS_BLOCKED；
观察窗口有界，DOM仅基础几何可见性；截图/DOM/URL可能含敏感信息，默认私有。
生产身份、私有对象存储/留存/脱敏、持久调度及监督器失效回收、分布式限额、
供应链补丁治理和实际公网IPv6仍需独立验收。哈希只证明一致性，不是来源签名。
未实施真实第三方网站访问、模型调用、生产数据库、部署、业务外发或RA-2。
无新服务采购；既有机器和CI实际账单未知，不记为零。
