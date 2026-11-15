# 已验收 PR105 的 M3 消费接口适配

已正常合入 main `85f6fe854cc2058672c136b52e4ce35588d9357f`；merge 为
`e23a71e96ac915cf14a074271fb1fbd768d38507`，原 PR106 HEAD
`4aaaa5101b8df8a2a8dc772093f02289e798d3ad` 及其双版本各12/12证据保持不变。
没有重新开发或重跑已验收 M1 基础来代替新任务。

新代码测试 SHA 为 `f76bdb8ad8a79a5ceb8be2a351193e2e8fcbc83e`。
本目录是其后的 docs 证据提交，不冒称测试曾在证据提交 HEAD 执行。
双版本可执行清单相同，根为
`3e17fcdcba75ebe440df813dbb4750c2dc8e1cc0e414bbc990b7bf29172b16f9`。

| 本机 / 独立低权限运行时 Python | 新增聚焦原始 JUnit | 结果 |
|---|---|---|
| 3.11.15 / 3.11.17 | [311/tests.xml](311/tests.xml) | 4/4 |
| 3.13.13 / 3.13.18 | [313/tests.xml](313/tests.xml) | 4/4 |

只验证本次新增适配：正式 TaskClient 实际 POST202、完整服务端 TaskHandle（含event_id）、
真实 PENDING→正式 M1 CLI→DONE→原签名读取、错误job/source及幂等冲突拒绝，
还有 PG 真重启后的 HTTP 身份重建、同一任务与 source/report/HTML 原字节回读。
UID10003 只有 bearer/tenant_id/source_refs 的0700/0600私有配置，实际不能读取
APP、Worker 或管理数据库配置。Worker UID10002 只调度正式 M1 CLI，不复制执行引擎、
指定job、延长租约或并跑旧 Worker。两轮无自有 WER/意外 SSR 退出；监督器exit0，
四类自有资源清理通过。原始 pytest XML 按字节保存，阶段 XML 不重复计为测试。

[manifest.json](manifest.json) 包含 JUnit SHA/CRC、两轮源码清单与脱敏证据指纹。
任务ID只公开哈希；不发布实际 API bearer、DB凭据、私钥、正文、报告HTML或dump。
既有控制器原发布目录的实际凭据扫描为零；本目录只投影安全字段及原始通过 XML。

M2 PR103 尚未 Owner 合并，没有加载其实现；本轮不是最终 M3 整机业务验收。
TaskClient 固定127.0.0.1:8765，最终唯一 M2 SSR 必须与 API 共用 loopback namespace，
且实际创建202必须触发正式 Worker。已通过 PR103 的接口评论明确协调；不会建立
第二套 SSR 或用 Windows legacy SSR 冒充任务提交/审核/A4。
待 M2 合并后接其正式 provisioning hook，再在同一源码 SHA 完成完整浏览器链。

操作说明见 [LOCAL_APPLICATION.md](../LOCAL_APPLICATION.md)。
旧 RED、dump、A1/MAX3继续封存。本次仅更新原 PR106，不自行合并或部署。
