# B5-P0 本地验收与首次 Hosted 交接

Owner 授权为 `B5_P0_B5A_TO_B3_TESTONLY_REHEARSAL_CODE_GO`；基线 `ae2505f74f7a81d7a563c05d1a811aaa526c2839`。独立分支 `codex2/ra4c-b5p0-signed-to-testonly-intent`。本文件不代表 Owner FINAL PASS，正式人员审批、客户分享、完整 B5B、Beta 及 G1/G2/G3 均没有解禁。

## 本地原始结果

本地源码冻结门禁、真实 PG/HTTP 和 Chromium 已全部通过。Hosted 尚未运行，结果仅以首次 PR 原始交接评论为准。

| 环境 | PG/HTTP + 边界 | Chromium | 截图 | 实际清理记录 |
|---|---:|---:|---:|---:|
| Python 3.11.15 | 55/55，0 skips | 63/63 | 12 | 55 |
| Python 3.13.13 | 55/55，0 skips | 63/63 | 12 | 55 |

原始结果位于 `evidence/local-final4-311/` 和 `evidence/local-final4-313/`；各自包含未改写 native JUnit、实际 SQLSTATE/原始对象哈希/清理 JSON、12 张截图及逐文件字节清单。两轮检查的 18 个新增源文件字节均未变化。

旧默认全量两版本均为 2450 passed、25 skipped、0 failed；25 项要求隔离 Chromium/Worker 或 `--network none` 容器，不在宿主机强行执行。原有 Hosted 16 项完整保留，包括对应隔离 jobs。原始本地 XML 保留在私有运行目录，SHA 与跳过原因见 `evidence/old-default-summary.json`。Ruff、mypy 74 source files、Node syntax 均通过，原始输出与 SHA 见 `evidence/static-checks.json`。

## 实际数据库与交互证据

每个 Python 使用独立 PG16 集群，安全场景在其内逐个建立真实独立数据库；浏览器另外建立独立 PG16 与 HTTP 子进程。使用已验收 0001–0003 和 B3 standalone TEST_ONLY DDL，无生产 migration。每轮必须完成 53 个真实 PG/HTTP 场景和 2 个边界单元用例，零失败、零跳过。

404 必须持久保存 1 intent、6 Claims、4 sections、1 audit、1 internal outbox；200 为 1 intent、3 Claims、4 sections、1 audit、1 internal outbox。原始 SOURCE/HTML/TARGET/Guard 等每个对象只导出实际 SQL 字节的 SHA 与长度，不公开原始对象。正向旅程和浏览器写入前后受保护根哈希必须一致。revision race 负例通过可信 fixture 增加新版本，其目录根变化是有意的注入，旧原文不被替换，且不得产生 intent。

负例覆盖伪造表单 authority/key/CSRF、Origin/Host/cookie、当前 issuer/subject/role/Locator/version/assignment、epoch/witness/anchor、双连接重复与冲突点击、实际 COMMIT 入口撤权与会话到期、关闭 PG、revision race、TCP 响应丢失和 HTTP 子进程重启。实际 Reviewer 连接还必须以 `42501` 拒绝业务表原始 SELECT、角色提升和原始 DML。授权缺少 probe key 的原生 `P0002` 与连接失败导致的 UNKNOWN 严格区分。

Chrome 每轮必须包含 1280/375/320px × 404/200 的真实表单及回执，共 12 张截图和 63 个断言，包括中文实际 raster、指针和键盘、触点高度、无全页横向溢出、NOT APPROVED、无额外网络和同一案例稳定回执。每轮还必须核实 53 个测试数据库及 2 套专属 PG 环境共 55 个清理记录；Docker 标签、资源消失与端口关闭为实际检查结果。

## 开发 RED 原样留存

- 首轮 Chrome 在 375px Enter 后没有导航。原生 CDP keyDown 缺少 carriage-return text；修正键盘协议后开发轮完成 63/63、12 截图。首轮失败 JSON、断言与 375px 截图保留于 `evidence/browser-dev-311-01/`；重复的开发绿色截图留在私有目录。
- 早期会话到期用例的 15 秒 token 在候选入口前已到期，未达到计划中的 COMMIT 入口。改为真实 60 秒到期，并在实际 candidate 后等待到期、使用 90 秒 HTTP timeout。原生失败 XML 和哈希保留于 `evidence/development-red/`。
- 49 项开发 PG/HTTP 全通过的那一轮期间增加了证据检查器与用例，源码变更门禁正确拒绝其成为最终 PASS；`evidence/dev-all-311-01/` 保留该事实。
- 第一轮冻结双 Python 均为 54/55。新增过期 witness fixture 错用 UPDATE，被已验收不可变元数据 trigger 以 `55000 / RA4A_IMMUTABLE_METADATA` 拒绝。仅将 fixture 改为 INSERT 独立已过期 witness；保护未改、未 skip/xfail。两个 Python 的三个定向绑定用例随后全部通过。原始双版本失败 XML、源码快照和哈希保留。
- 第二轮双版本 PG/HTTP 均为 55/55，3.13 还完整通过 63 浏览器断言与 12 截图。3.11 在并行浏览器运行中遇到 30 秒 `Page.navigate` 超时；同源码串行浏览器复测在任何 HTTP 前遇到 `Network.clearBrowserCookies` 超时，0 断言、0 业务记录。两个原始 CDP RED 和实际 PG 清理记录保留。B5 自有浏览器驱动随后改为每个尺寸/案例建立独立的原生 BrowserContext，保留真实 cookie/签名/指针/键盘检查，并增加阶段诊断及退出校验；没有调整导航的 30 秒阈值或应用权限。旧 3.13 完整绿色原件保留于私有归档，其摘要和清单哈希公开留存；最终结果必须来自更新驱动后的冻结全轮。
- 320px 人工检查发现复用框架的“只读、不保存核对结果”底部说明与新增内部持久化矛盾。仅在 B5 自有组装层替换页脚及新表单说明，不改已验收 frame/CSS；浏览器现在同时验证表单和回执的保存说明。为停止验证旧文案，第三轮两条 pytest 子进程经精确 PID/parent/绝对 JUnit 路径核对后终止，其专属 PG 容器、network、volume 和端口逐项验证清理；该轮明确标为 CANCELLED，不计 PASS。修正文案的定向浏览器随后完成 63/63、12 截图；最终全量重新冻结执行。

## 发布与首次 Hosted 周期

只允许 Owner 指定范围的新文件。已有 6,782 个 Git blob 与 mode 必须逐项保持基线身份。私有 `.runtime/` 不进入索引；公开文本扫描实际 fixture 凭据、witness capability、JWT 和 DSN。新增文档目录的局部 `.gitattributes` 保留原始证据字节，避免 Git 换行转换破坏 native XML/JSON/PNG 清单。

本地全门禁通过后才允许一次受控推送和一个 Draft PR。首轮必须核对旧 16 项加新 2 项的实际 18 jobs、attempt=1、精确 HEAD/merge-ref、原始 native artifacts、源文件身份与 artifact SHA。Hosted 结果通过 PR 原始交接评论另行提交；本地文档不预先宣称其通过。首轮结束即停止，不 rerun、不补推、不合并、不部署，等待 Owner 独立 FINAL PASS。
