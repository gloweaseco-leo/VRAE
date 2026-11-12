# P1 实测结果与最后 SHA 的区分

功能代码：`2be7a177d5c5e33492eb63ff4847bb3a67790996`；已验收 main：
`60dbe1e1acfc84ad0849e84f3abe3712ad8ebccd`。后续仅本目录证据/文档提交；
renderer、tests/reporting 和 verify_ra3c 的功能 blob 保持该功能 SHA 不变。

| 实际运行 | passed | 原有 host skips | failures/errors | 报告 | QA44 | 历史独立 QA | 工程/回放命令 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Python 3.11.15 | 1943 | 25 | 0/0 | 71 | 224 | 139 | 25/25 expected exits |
| Python 3.13.13 | 1943 | 25 | 0/0 | 71 | 224 | 139 | 25/25 expected exits |

[3.11 命令及逐项 skip 理由](local/python311/summary.json) / [完整 JUnit](local/python311/full.xml)；
[3.13 命令及逐项 skip 理由](local/python313/summary.json) / [完整 JUnit](local/python313/full.xml)。
原始主机 skips 仅为真实隔离 HTTP/浏览器容器要求；没有新增报告/QA skip 或 xfail。
所有原报告测试函数/类的 AST 与旧 SHA 一致，仅新增一项旧渲染器 pin 拒绝回归，未弱化旧断言。

每版完成 compile、Ruff、mypy、全仓 pytest、pip check、所有 RA2A/B0-B6/B6-execution/C0-C3/D0-D1/
RA3A/RA3B/RA3C 固定验证器，以及模拟 Gold 成功/伪造 Gold 必须退出 1。原 RA3A Fake 模式保持。
另外各自使用旧引擎的精确 Git blob 重放八个旧报告 refs 成功：
[3.11 原引擎实际模块及结果](previous-engine-python311.json) / [原 stdout](previous-engine-python311.stdout.json)；
[3.13 原引擎实际模块及结果](previous-engine-python313.json) / [原 stdout](previous-engine-python313.stdout.json)。
这不意味着新 loader 能接受旧 renderer pin；该兼容性限制已显式测试和披露。

## 真实浏览器

原 HTML 在 375px 的同一 >=12px 断言实际失败，记录最小字号 **11px**，JSON/PNG 留在 prior-renderer-red。
新 renderer 1.0.2：6 个样本 × 1280/375/320 = **18 视图**，每个页面 banner 及子元素计算字号均 >=12，
完整提示首屏可见，无横向溢出。**108 次**实际内部证据锚点点击、0 外部请求/异常、6 个真实单页 A4 PDF。
新 HTML/hash 与 browser record 再次逐项核对；仅屏幕 mobile banner 字号改动，打印布局未更改。

## 原始记录与边界

完整 [source-and-results-proof.json](source-and-results-proof.json) 核对：1416 个 accepted-main blob/mode 保留，
94 个旧 RA3C 验收文档/产物文件保留（原 README 仅追加新版入口，其原版仍在旧 SHA），
源/Guard 容器原始摘要不变、原 tests AST 不变、生产 renderer 逆向替换两处后与旧源码逐字一致。
独立 QA48、RA3B/intelligence/native contracts、安全/Gold/CI/依赖及 Phase0 文件未改。

默认 Git archive 的 CRLF 导出在严格源码摘要校验中被拒绝；这是封存过程问题，没有修改测试期望。
原 CRLF 记录保留，最终显式 LF 导出的 214 个文件先验 Git blob 身份，再运行旧引擎。
JSON 记录原始字节与 Git 文本换行的区别见 README；完整原始日志/JSON/截图/PDF/CI artifact 在五个 ZIP
及 archive-index 的逐条 byte/SHA 清单内，不能把转换后的工作字节误报为原 Git blob。

## 真正 hosted CI

功能 SHA 的四项 [run 43165855835](https://github.com/gloweaseco-leo/VRAE/actions/runs/43165855835) 全部 SUCCESS。
四项 checkout **218a1b87f877010a0feb5042da4a6251d8478487**，原始 Git 父提交为 main + 功能 SHA，
结果 tree 与功能 HEAD 相同。两版 Python 各 1943 passed/25 host skips；隔离 HTTP 1967 passed/1 skip；
隔离浏览器原 245 command exits、16 worker lifecycles、worker kill 137 和 48 negative exit-1 probes 原义保留。
[实际第一轮证明](ci-functional/proof.json) / [安全原 artifact 核验](ci-functional/security-proof.json)。

最后证据提交后的 **最终新 HEAD 四项 CI** 将另行执行，原始日志/元数据放在忽略目录
`../.checks/ci-<run>/`，最终 SHA/checkout/parents/run 链接在 PR #47 交付段回读核验。
不提交 post-CI 源变更来移动验收 SHA，不把本页功能 SHA 的第一轮冒充最终轮。

private / NOT_APPROVED / 不可客户分享，Human Gold 0/26 不变。工程视觉候选不是 Owner 最终通过，
也不是统计质量、企业资质、表单送达、营收/排名或商业结果证明。无真实模型、网站、客户报告、审批、
部署或 RA3D 生产实现；最终提交后停止等待新 SHA 上独立验收。
