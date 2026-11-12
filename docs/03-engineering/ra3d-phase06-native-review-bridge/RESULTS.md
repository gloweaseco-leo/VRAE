# Phase 0.6 实际结果与原始证据

验收对象是只读原生合成桥，不是生产人审。输入与 expected pins 固定来自 main 696d4ae695041f0eeefa56d22039682a989380b2。每个原生模块的 Git blob、原始 Git bytes SHA256、本地 bytes SHA256 和实际 import 路径在 exporter JSON 中；未导入其他 worktree 或 PR #48。

## 原生 API 实测

双 Python 各执行真实 EvidencePack.load / FindingPackage.load / GuardResult.load / build_draft / ReportDraft.load / render。各 **2 个 native 正例通过 + 18 个非法副本明确拒绝**，无 stub/mocked Guard，也不生成新可信 pins。单独 wrapper 保存 command.json、stdout、stderr 与 exit=0；前序直接执行也保留原始 JSON。

| 原始运行 | Python | 正例 | 明确拒绝 | 状态 |
| --- | --- | --- | --- | --- |
| [export-20261112T090629720947Z.json](evidence/export-20261112T090629720947Z.json) | 3.11.15 | 2 | 18 | NATIVE_REPLAY_AND_REFUSAL_PASS |
| [export-20261112T091039824307Z.json](evidence/export-20261112T091039824307Z.json) | 3.11.15 | 2 | 18 | NATIVE_REPLAY_AND_REFUSAL_PASS |
| [export-20261112T091222635248Z.json](evidence/export-20261112T091222635248Z.json) | 3.13.13 | 2 | 18 | NATIVE_REPLAY_AND_REFUSAL_PASS |

404：1 issue / INQUIRE / native REVIEW_REQUIRED；200：0 issue / native=null。HTML 与独立 held pins 一致：404 6170722c97015cf113c3d7898c5cc342bf7cfea0113038bd07a48fdfd55d808c；200 4d815b29563341930c8a7a2b75f3aad416f04b3dc08683b7902c6f286d5e28a5。主联系 quote 对应原始 body UTF-8 [158,177)，不是手填 mock。

| 非法尝试 | 实际拒绝类 | 原始错误码 | 首个拒绝层 |
| --- | --- | --- | --- |
| N01_SOURCE_BYTE | EvidenceError | EVIDENCE_INTEGRITY | NATIVE_REPLAY |
| N02_QUOTE | GuardError | GUARD_INTEGRITY | NATIVE_REPLAY |
| N03_UTF8_OFFSET | GuardError | GUARD_INTEGRITY | NATIVE_REPLAY |
| N04_HELD_PACK_REF | EvidenceError | EVIDENCE_INTEGRITY | NATIVE_REPLAY |
| N05_HELD_GUARD_REF | GuardError | GUARD_INTEGRITY | NATIVE_REPLAY |
| N06_HELD_DRAFT_REF | BridgeRefusal | HELD_DRAFT_REF_MISMATCH | BRIDGE_HELD_DRAFT_PIN |
| N07_HELD_HTML_SHA | BridgeRefusal | HELD_HTML_SHA_MISMATCH | BRIDGE_HELD_HTML_PIN |
| N08_TENANT_SCOPE | GuardError | SCOPE_MISMATCH | NATIVE_REPLAY |
| N09_CITATION_SCOPE | GuardError | GUARD_INTEGRITY | NATIVE_REPLAY |
| N10_NOT_RUN_GUARD | GuardError | INPUT_INTEGRITY | NATIVE_REPLAY |
| N11_REJECTED_GUARD | GuardError | GUARD_INTEGRITY | NATIVE_REPLAY |
| N12_UNAPPROVED_PROSE | GuardError | GUARD_INTEGRITY | NATIVE_REPLAY |
| N13_HTML_BYTES | ReportError | REPORT_REPLAY_MISMATCH | NATIVE_REPLAY |
| N14_VERSION | ReportError | REPORT_METADATA | NATIVE_REPLAY |
| N15_ZERO_AS_ISSUE | ReportError | REPORT_REPLAY_MISMATCH | NATIVE_REPLAY |
| N16_RENDERER_VERSION | ReportError | REPORT_PIN_VERSION | NATIVE_REPLAY |
| N17_NATIVE_HASH | ReportError | REPORT_REPLAY_MISMATCH | NATIVE_REPLAY |
| N18_FOREIGN_PACKAGE | FindingError | FINDING_INTEGRITY | NATIVE_REPLAY |

N06/N07 是桥接层对独立 held draft/html pin 的比较；其余使用 native 错误，不把本地自定义字段伪装成 native API。所有负例均使用 detached 原始输入副本，原始 expected pins 保留在每条记录。没有“重签 Guard 后继续”或非法输入变成空绿报。具体 mutation 与复跑代码见 export_bridge.py；所有 raw error 保留。

## 真实新鲜 Chromium

最终：[browser-2026-11-12T09-43-59-927Z/results.json](evidence/browser-2026-11-12T09-43-59-927Z/results.json)，Chromium Chrome/156.0.8078.4，**170 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，24 张原始 PNG。三宽度 1280/375/320、两份 dossier，33 次实际来源打开（6 次主入口 + 27 次逐条 claim）与返回。每条断言包含焦点、UI 反馈与内存轨迹；六份当时输入的精确 bytes 在 input-files/。

实测包含：12px 顶部私有提示与 above-fold、零横向溢出；原生 report id/version/真实捕获时间；原始 byte slice/quote/body/citation、键盘 Tab/Space、回查后焦点；404 事实/三条候选编辑分层；200 无 CTA Guard 字段且 native=null；逐条 claim 全部核对才可继续内存模拟；全量 native hash；原生 HTML 在独立 sandbox renderer 中实际加载，其 URL、NOT APPROVED 正文、scripts=0/forms=0 已读取；模拟操作后原生 JSON 字节不变；刷新清空。

源弹窗在打开时聚焦标题、滚动位置为 0，12px NOT APPROVED 提示可见；长原生引用可展开，减少手机默认滚动。页面外部请求 **0**，Runtime 异常 **0**；没有 enabled send/share/export。CDP loopback 控制不属于页面 API 请求。观测仅限受测页面，不声称 OS 级所有流量为零。

| 场景 | 1280 桌面 | 375 手机 | 320 窄屏 |
| --- | --- | --- | --- |
| 原生 404 | [1280](evidence/browser-2026-11-12T09-43-59-927Z/native-404-1280.png) | [375](evidence/browser-2026-11-12T09-43-59-927Z/native-404-375.png) | [320](evidence/browser-2026-11-12T09-43-59-927Z/native-404-320.png) |
| 404 原始字节 | [1280](evidence/browser-2026-11-12T09-43-59-927Z/native-evidence-404-1280.png) | [375](evidence/browser-2026-11-12T09-43-59-927Z/native-evidence-404-375.png) | [320](evidence/browser-2026-11-12T09-43-59-927Z/native-evidence-404-320.png) |
| 404 单条来源弹窗 | [1280](evidence/browser-2026-11-12T09-43-59-927Z/native-claim-dialog-404-1280.png) | [375](evidence/browser-2026-11-12T09-43-59-927Z/native-claim-dialog-404-375.png) | [320](evidence/browser-2026-11-12T09-43-59-927Z/native-claim-dialog-404-320.png) |
| 404 仅内存结果 | [1280](evidence/browser-2026-11-12T09-43-59-927Z/native-result-404-1280.png) | [375](evidence/browser-2026-11-12T09-43-59-927Z/native-result-404-375.png) | [320](evidence/browser-2026-11-12T09-43-59-927Z/native-result-404-320.png) |
| 原生 200 零问题 | [1280](evidence/browser-2026-11-12T09-43-59-927Z/native-200-1280.png) | [375](evidence/browser-2026-11-12T09-43-59-927Z/native-200-375.png) | [320](evidence/browser-2026-11-12T09-43-59-927Z/native-200-320.png) |
| 200 原始字节 | [1280](evidence/browser-2026-11-12T09-43-59-927Z/native-evidence-200-1280.png) | [375](evidence/browser-2026-11-12T09-43-59-927Z/native-evidence-200-375.png) | [320](evidence/browser-2026-11-12T09-43-59-927Z/native-evidence-200-320.png) |
| 200 来源弹窗 | [1280](evidence/browser-2026-11-12T09-43-59-927Z/native-claim-dialog-200-1280.png) | [375](evidence/browser-2026-11-12T09-43-59-927Z/native-claim-dialog-200-375.png) | [320](evidence/browser-2026-11-12T09-43-59-927Z/native-claim-dialog-200-320.png) |
| 200 内部范围模拟 | [1280](evidence/browser-2026-11-12T09-43-59-927Z/native-result-200-1280.png) | [375](evidence/browser-2026-11-12T09-43-59-927Z/native-result-200-375.png) | [320](evidence/browser-2026-11-12T09-43-59-927Z/native-result-200-320.png) |

## 保留全部 FAIL / ERROR

| 原始运行 | PASS | FAIL | ERROR | SKIP |
| --- | --- | --- | --- | --- |
| [browser-2026-11-12T09-12-56-840Z](evidence/browser-2026-11-12T09-12-56-840Z/results.json) | 0 | 0 | 1 | 0 |
| [browser-2026-11-12T09-25-07-080Z](evidence/browser-2026-11-12T09-25-07-080Z/results.json) | 4 | 1 | 1 | 0 |
| [browser-2026-11-12T09-27-31-870Z](evidence/browser-2026-11-12T09-27-31-870Z/results.json) | 23 | 1 | 1 | 0 |
| [browser-2026-11-12T09-30-19-642Z](evidence/browser-2026-11-12T09-30-19-642Z/results.json) | 143 | 0 | 0 | 0 |
| [browser-2026-11-12T09-34-57-588Z](evidence/browser-2026-11-12T09-34-57-588Z/results.json) | 170 | 0 | 0 | 0 |
| [browser-2026-11-12T09-43-59-927Z](evidence/browser-2026-11-12T09-43-59-927Z/results.json) | 170 | 0 | 0 | 0 |

首轮沙箱 CDP Page.enable 超时未计 PASS，经批准以仅本地文件/封锁外网的 Chromium 重试。第一个实际 FAIL 是 404 证据面板缺 evidence_ref，补齐实际 evidence/snapshot/locator 后重跑；没有改原生 source/Guard 或降低预期。第二个 FAIL 的原检查只看主 frame tree，未识别 sandbox file iframe 的独立 renderer；保留原 FAIL，新增附着 OOPIF 读取实际 URL/DOM 的更强检查。之后 143 PASS 的中间运行保留；截图审阅再改善弹窗默认焦点/固定私有提示并新增断言，最终为 170 PASS。断言 FAIL 后的执行 ERROR 也原样保留，不拆除重复记号来美化计数。

原 Chromium stderr 含本机启动/网络服务诊断，保留原始 CRLF；不将“页面 Runtime 异常=0”说成进程完全没有诊断。一次前期 Python -c 的 PowerShell 引号解析 SyntaxError 未写文件，随后改用受版本控制的 inspect_inputs.py；摘要生成器首次 Node 执行也因反引号转义 SyntaxError 退出 1，未写 RESULTS，修正后生成。两者不计成功测试。任何封存/命令问题单列，不清洗原始记录。

## 封存与门禁

seal-evidence.mjs 验证独立 held pins、原 HTML SHA、每条显示 pointer 与 native claim 完全一致、每个 quote 的原始 byte slice、所有截图 SHA、最终浏览器输入一致、旧 Phase0.5 资产复用和所有 1793 个 main 文件 mode/blob 保留。manifest 排除自身和临时浏览器 profile/runtime，避免循环 SHA。audit-delivery.mjs 在最终提交后只读验证 clean tree、清单 raw bytes 与 Git blob 以及最终源文件一致；精确最终 SHA 记录在 Draft PR 中。

GitHub CI 若触发，必须对应最终 HEAD + 最新已验收 main，实际四项结果和原始日志链接记录在 Draft PR；它们是主干回归，不能冒充 native 来源投影或真人流程验收。Phase0 的未来 A01–A48 保持 NOT_RUN，PR48 QA 不修改、不认领。本轮无真实身份/审批/分享/客户访问，Human Gold 0/26，RA3D production NO_GO。
