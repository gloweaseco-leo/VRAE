# RA-4C1 · 精确 ReviewTarget 只读接入

Owner Issue #64，起始已验收 main `9d138ba57e0b442b9dace1a2247d7aaa46ca38ac`。沿用现有 Python SSR 控制台、任务池、原生核对页和证据页；没有第二套 UI、状态机或哈希引擎。保持 Draft，等待独立 FINAL PASS。

最终协调：[Owner 评论 6829155014](https://github.com/gloweaseco-leo/VRAE/pull/65#issuecomment-6829155014) 指定新已验收 main `e9ec1bd7f36a0446af14f04b66b71e4d45ebfb97`。已在原 worktree 普通 merge，提交 `2c6e48e8c31a50ec8cf5fee153ce3d20d6be4540`，父提交依次 `f175c20e2e001689f50aec5bc9fc8bd3a1ba07f4` / `e9ec1bd7f36a0446af14f04b66b71e4d45ebfb97`。RA4A P1 合成 PG/RLS/queue 已验收代码完整保留；本 UI 不接入 PostgreSQL、真实身份或决定接口。最终除原四项 CI 外还要求新 main 的两项专用 PG CI 真实通过。

操作：仓库根目录执行 `python -B -m apps.operator_console.preview --test-only --synthetic-fixtures`，打开输出的 127.0.0.1 地址。选择 404 或 200 任务→原生核对→“查看完整核对对象与逐条来源”→原始字节→返回；浏览器后退/前进保留相同任务、版本与 target digest。其他 9 项合成任务和原有 8 类阶段均保留。

## 来源接线

`ConsoleService.review` 在原有 scoped assigned task 校验与 NativeVerifier 重放后，将真实 `_payload`、完整 HTML bytes 和同一次读取的原始 source 交给 `ReviewTargetBridge`。桥只调用已验收 `vrae.reviewing.build_target` / `validate_target`，不实现新的 digest 算法，不调用 simulation 或 submit。

`review-target-pins.json` 来自已验收 Git 对象的 D1/D2 fixture 和双 Python 历史 scenarios 记录；`hold-pins.py` 一次性提取并拒绝覆盖。目标摘要直接从原记录持有，不从当前报告/请求/DTO重新计算期望值。合成策略、对象地址及 source/payload/HTML pins 与当前输入分离；D1/D2 成功的完整不可变字节重放缓存不缓存身份、授权或版本账本。

同一独立 holds 还从已验收 C0 fixture 提取 task→case/owner 绑定。即使整条 DTO 的 run/stage/pins 都换成另一有效案例，也在读取 source 前拒绝，不能由 DTO 选择自己的信任案例。这是明确合成 fixture 绑定，不能充当真实身份、RLS 或生产任务账本。

| 固定案例 | 原生含义 | 已验收 target digest |
|---|---|---|
| 404 | 1 个静态路径问题；H0 保留，假设/行动仍条件性 | `5705ac9e45e5118bc162bdece42f040a61360cf090b09500f7e9de5c89a9d256` |
| 200 | 0 个问题；native H0 / ReportVersion 均 null，仅内部范围 | `c309bb1878103fdcb71200de644a685a52a04ab38d29325571cbc3a7f2bb4050` |

HTML 全字节、CSS/layout asset、页脚、draft payload、来源 manifest/对象、Guard 输入/版本、策略快照、原生 H0、每条 Claim pointer/范围/处置上限均由原生目标绑定。保留完整 limitations、recorded coverage、examined pages。网页文字仅证明来源有该文字，不证明资质、企业身份或商业效果。

## 只读消费合同

`TargetRead` 是不可变 bytes 的 `operator-console-target-read-0.1` 投影；直接构造不构成信任，使用前由 `ReviewTargetBridge.load(task, payload, document, html, source)` 重放真实 target 并逐字对照独立已持有目标与完整投影。

| 字段 | 不变量 / 未来可信 backend 接缝 |
|---|---|
| tenant_id / task_id / owner_scope | 先由独立 ReadAuthority 验证身份及 assignment，再查记录；未知/跨租户/未分配统一拒绝 |
| latest_report_version | 当前从独立固定 fixture 持有 1，**不是生产最新版本账本**；未来必须来自受保护的一致性读取/版本事务 |
| target_digest / target | 只能与外部持有的精确目标和本次完整原生重放一致；自签摘要、trusted=true、假 role 均无效 |
| native_h0 / native_report_version | 404 与原生 ReportVersion/H0 一致；200 必须保留 null，不能升级可审批报告 |
| target 的 source/policy/object/Guard/renderer pins | 来自独立的可信存储/策略上下文；不能让报告或上传 DTO提供自身信任 |
| limitations / coverage / claim dispositions | 原生完整回显；ACK_LITERAL_FACT 仅字面来源，HYPOTHESIS/RECOMMENDATION 仍 HUMAN_REVIEW_REQUIRED；不是实际决定 |
| source_kind / state / missing_conditions | 当前 SYNTHETIC_TEST_ONLY / READ_ONLY_NOT_AUTHORIZED；真实 identity、RLS、对象存储、事务、审计/outbox 不可用 |

URL 为 scope 内只读应用路由，不枚举外站、不接受任意 URL。target→source 链接携带 version、draft、target 三项条件；核验与来源展示使用同一次读取的 snapshot，防止验证后再次读取导致跨 case 替换。旧 C0 两参数来源链接仍兼容，但同样经过 native + D1/D2 核验。没有导出/下载/审批/退回/拒绝/分享路由。非 fixture/context 请求拒绝，预览保持双 TEST_ONLY 开关、loopback、no-store、CSP 和零外部页面流量。

错误：身份/assignment 不匹配为 UNAUTHORIZED；版本/摘要不匹配 STALE_VERSION；来源/HTML/布局/目标/策略伪造 SOURCE_INTEGRITY；非法查询 INVALID_INPUT。均返回中性页面且无原始证据数据。403/WAF/robots/UNKNOWN 保留“不能据此判断网站缺陷”。

未来 `FutureRealReviewAdapter.prepare` 始终委托原 `prepare_production_review` 拒绝所有输入，和任何模拟决定完全分开。只有后续 Owner 单独放行且 RA4A/B 可信身份、授权、最新版本账本、受保护不可变对象与持久事务验收后，才可另增真实 read adapter；本轮不推定其 API，不读取 Codex1 未合并分支。

## 验收协议

原 58 项应用测试保持原 blob；新增 43 项真实 source/target 边界，双 Python bounded 回归同时实际收集 127 项已验收 reviewing 原测试。原 QA V2 64+54、历史 V1 53 RED 与 Gold 0/26 不改。新 Chromium 脚本复用既有 UI 操作并增加精确 target→source→back/forward、200/null、非法摘要及范围拒绝；保留原始截图/CDP/DOM/版本与源文件哈希。

最终先提交所有本地证据，再推送精确 HEAD，运行四项全新 GitHub CI。post-CI 原始 run/jobs/PR/merge 对象、四日志和安全 ZIP 只存本授权目录并在 PR body 公布精确 SHA/父 SHA/计数/哈希，不为把回执写回 Git 而漂移验收 HEAD。保持 Draft，不合并、不部署、不触及真实审批或客户访问。RA4 EXIT / RA5 / E2/E3 / Human Gold 仍 NO_GO。
