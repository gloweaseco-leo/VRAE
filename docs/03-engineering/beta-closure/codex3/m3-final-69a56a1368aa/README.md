# M3 整机业务最终候选：原生证据

唯一源码候选：`69a56a1368aab40bc93f91d35e9e0c951648b10b`，source tree `5145aa93ce624876d53c652c1eb9a610f0ef0715`。
已验收基线：`df5428c503f22a86429b2b9a4263551776d7253a`。本证据只作为原PR106回执链接；
证据提交是候选的文档子提交，通过不可变tag `codex3/pr106-m3-evidence-69a56a1368aa` 引用，
不会移动源码分支HEAD。双Python正式运行和自然CI都以该源码候选为准。

| 实际运行 | 原生pytest | Chrome断言 | 截图 | 单页中文A4 PDF | 真PG/服务重启 |
|---|---:|---:|---:|---:|---:|
| Host3.11.15 / Worker3.11.17 | 4/4 | 125/125 | 18 | 2 | 2 |
| Host3.13.13 / Worker3.13.18 | 4/4 | 125/125 | 18 | 2 | 2 |

每轮都从原beta_internal.py真实CLI启动PG16/API/独立Worker/唯一M2 SSR。
先通过真实APP202/Worker生成两个初始身份入口任务；浏览器随后在1280/375/320
每种宽度各提交404/200新任务，共6个，与初始任务不同。实际观察PENDING，
Worker由启动器自动执行，浏览器只刷新状态，测试RPC不驱动生产者。
DONE后重新签名打开本次新报告，完成修订、拒绝、批准各两份内部回执，
报告仍NOT_APPROVED、人审和外部交付均false。200保持0个问题/证据不足。

真实浏览器保存并导出两份中文单页A4，验证PDF页面尺寸、Unicode映射及截图哈希；
真正重启PG/API/Worker/唯一SSR两次，旧会话拒绝，重新认证后沿原持久路由
找回同一job、版本、报告SHA、回执和A4。另验证未签名报告拒绝、跨任务回执拒绝。
每轮最终有8份真实结果与6份PG持久回执，角色无新原始表权限，
SSR三次退出均为正常exit0，Chrome退出与所有自有资源清理通过。

- [311原始JUnit](311/tests.xml) · [311审计摘要](311/evidence.json)
- [313原始JUnit](313/tests.xml) · [313审计摘要](313/evidence.json)
- [311 404 A4](311/browser/a4-404.pdf) · [311 200 A4](311/browser/a4-200.pdf)
- [313 404 A4](313/browser/a4-404.pdf) · [313 200 A4](313/browser/a4-200.pdf)
- [311界面示例](311/browser/report-1280-404.png) · [313手机界面示例](313/browser/report-320-200.png)
- [全部原字节SHA256/CRC32索引](manifest.json) · [操作说明](../LOCAL_APPLICATION.md)

source-manifest是隔离原生运行卷清单；宿主浏览器指针依赖在manifest另列。
原生pytest XML原字节保存，组件阶段XML不重复计作pytest，Chrome断言单独计数。
真实报告source/report/html与原始回执、私有日志留在本机C3.private，不随本证据公开。
控制器在持有所有实际DB/API凭据时完成公开候选文件精确扫描，匹配0；
签名私钥始终在SSR外且不持久化到公开输入。

本结果是M3内部合成L0→L1业务候选，等待Owner独立验收；
不宣称真实人工审批、外部交付、生产部署或旧B7/A1专项FINAL PASS。
旧RED/dump/A1/MAX3继续封存。自然CI完整结果与官方Artifact在PR106另附原始链接。
