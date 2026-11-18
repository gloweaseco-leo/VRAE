# PR140 与 accepted main 676fdde 的联合接线

Owner 指令：[6971592459](https://github.com/gloweaseco-leo/VRAE/pull/140#issuecomment-6971592459)。原组件提交 `acfbb379097c662d39d128a0fa8538ddef248408` 的 20 workflow / 42 Job attempt 1 SUCCESS 与 Owner 组件验收保留，**不作为新整合 HEAD 的联合验收结果**。

## 正常合并与最小语义接线

原分支 `codex2/l2-executive-vf`、原工作树正常 merge accepted main `676fdde5c14a23bb284a0cb00df25773b30ed4b3`，合并提交 `d71eb12`，没有 force/rebase。

`NativeBusiness` 同时保留 `source_views` 和 `intake`。`route/handle` 先交回已接受的 `s2_acceptance_sources`，再处理 `/brief` 与 `/brief/submit|retry|revoke`。S2 原 pack、当前任务签名、候选重放与卡片权限检查不变；S4 仍使用原双身份、CSRF、当前版本和 PG Brief 权威。摘要派生读取不改原报告 content/display hash 或 Controlled 条目。

没有修改 `vrae/l2/identity.py`、`ledger.py`、`native.py`，没有修改 `vrae/l2_ops/briefs.py`、`ledger.py`、原 Worker 租约、Guard、EvidencePack、旧浏览器启动参数或超时。

## 同一真实任务的联合验收

在原 `s2_acceptance_runtime` 加显式 `--executive` 模式；原 S2 旅程完整保留，再扩展 S4。该模式要求 accepted main 676fdde 为祖先，核心目录差异仅允许已审 S4 UI/派生模块清单；原 C3 默认范围门禁未放宽。

每个新 run 自己创建工业 APP202，原独立 Worker 在原租约内完成；沿同一 tenant/request/run/job/pack/report/Controlled receipt/PG Brief 检查五维两卡、原文、原七包、摘要及 PDF、四本账和合成接单。不拼接 fixture 或其他 run。

独立收方进程持原合成接单签名私钥；SSR 只接收公钥。测试复用原 supervisor 的私有文件控制，不新增浏览器配置/ACK 接口。控制命令绑定当前 job/report，只能在原已授权且已保存的合成内部 Brief 上执行。签名错误、旧 attempt、撤销后回执核对具体允许公开的拒绝码，避免把过期误算成验签拒绝。回执 nonce 和签名只经私有通道，不进入公开证据。

显式验证：生产者 WAITING_ACK；独立退回、失败重试、ACK；ACK 不升级客户确认/E2/E3/报价/素材权利；重启后 ACK 进程内状态消失，原 PG Brief/审核回执原字节哈希保留。另用原 live audit 验证 tenant/run/job 错绑及 C2 key 撤销；等待原 M1 自然过期，不缩短/延长 TTL；再验证原重新签名、显式报告修订和旧版拒绝。

两个 Python 的真实联合旅程在原 `s2-c3-quality` real-combination Job 运行；S4 专属 Job 保留组件/PG与联合路由专项，避免再复制一套真实整机。全部仍是 TEST_ONLY 合成来源，不是正式人审、真实客户确认或外发。

## 本地开发记录与当前限制

已运行原生 3.11/3.13 的同组 S2/S4 路由及安全专项，分别 29 PASS；最终代码复核及自然 CI 另按新 HEAD 记录。Ruff、Node 语法与 `mypy vrae`（132 文件）、原 C3 两个接线文件的 mypy 已通过。

| run | 实际结果 | 保留边界 |
| --- | --- | --- |
| s4merge311a / 14d4f7e | 正向收方 REJECTED 步骤被通用拒绝；此前已到真实 PG Brief | 当时没有细分拒绝码，根因 UNKNOWN；不以该轮通用 403 证明特定验签拒绝 |
| s4merge311b / 7814f30 | 并行演练中原 canonical Worker 退出，浏览器在原任务页失败 | 原 worker/supervisor 的 AssertionError 与清理记录保留；不归因于 S4 或宣称已知底层原因 |
| s4merge313a / 7814f30 | 并行演练中 S2 重新登录后页面不符，BROWSER_EVALUATION_FAILED | 根因未定，后改为串行排除同机并行负载变量 |
| s4merge313b / 7814f30 | 来源卡与四个摘要视口通过，回原蓝图时 HTTP403 | 七包没有被更改；驱动在新增摘要测量后补原流程重新签名，并增加打印前 HTTP200/摘要内容核验 |

上述公开失败工件位于 `../l2-operations/<run>/`，包含源码哈希、实际检查、旧 RED 与所属资源清理。原私有日志、DB dump、凭据和浏览器 profile 不发布。没有改旧权限期限或靠换镜像/扩大超时掩盖失败。

复验：`python -B -m integration.l2_ops.s2_acceptance_runtime --executive --run <唯一标签> --minor 3.11`（原生 3.13 则改 minor 与解释器）。使用原依赖镜像、Docker、Chrome/CJK；Windows 可通过 `B5B_CHROMIUM` 指向受控 Chrome。新 HEAD 自然 CI / 完整联合结果以 PR140 最新描述与对应工件为准，未记录前不得宣称联合 PASS。
