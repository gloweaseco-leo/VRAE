# 实际验收矩阵

既有 `tests/operator_console/test_console.py` 58 节点保持原 blob；新 `test_targets.py` 43 节点。双 Python 同时实际执行 127 个原 reviewing 用例。`regress.py` 要求 228 个节点全部通过、无 skip/error/xfail，并核验实际 D1/D2 call receipt、源文件运行前后 SHA 和 404/200 映射。完整默认回归及原 QA V2 64+54 由最终四项 hosted CI 执行。

| 独立业务边界 | 真实执行 / 拒绝预期 |
|---|---|
| 原生重放 | 清空成功 memo 后计数真实 ReportDraft.load；C0 与 D1/D2 均重放，不仅检查标签 |
| 完整目标 | 使用原 build_target/validate_target；对照独立已验收摘要，逐项核对 H0/null、HTML、资产、来源、Guard 与完整限制 |
| 原始字节 | Claim pointer、UTF-8 起止、精确 quote 与原始 source body 相符 |
| 无外网 | 实际正向重放期间 DNS/connect/urlopen 被设置为必失败；原生重放仍通过，调用列表为空 |
| HTML/页脚/CSS | 更换完整 bytes，原 trust 下必须拒绝 |
| 原生 payload | private/其他内容被改，必须拒绝 |
| source quote/UTF-8 范围 | 原 source 改动，必须拒绝 |
| Guard/evidence refs | 伪造 ref，或 200 的有效 Guard 混入 404，拒绝 |
| source policy/version | 策略版本、metadata 版本被改，拒绝 |
| 自签摘要 | 使用真正 ReviewTarget.target_digest 为伪造目标重新计算摘要，仍拒绝 HTML/asset/policy/source/object/Guard/renderer/pack/claims/H0/kind 改动 |
| trust port 伪造 | 变更 SyntheticTrust 的策略、对象或 Guard 版本，仍必须原生重放/独立目标拒绝 |
| renderer memo | 资产变更令原生 memo key 失配，不能复用原目标为新布局背书 |
| 生产信任捷径 | DTO 添加 trusted=true、自报 APPROVED、未知 DTO 版本、租户或 latest version，拒绝 |
| 200 资格提升 | H0/kind 伪造、404/200 替换，拒绝；保留零问题/null |
| 200 PASS 措辞 | 将 limitations/recorded_coverage 改成全站 PASS、资质或询盘成功描述，拒绝 |
| 真实审核端口 | 原 prepare_production_review 和 FutureRealReviewAdapter 对 None、空 dict、OWNER/verified/trusted dict 均实际抛拒绝；不调用模拟决定 |
| scope | 匿名、角色 dict、跨租户、未分配任务均拒绝，不返回证据 |
| version/target | 旧版本或错误 target digest，包括 source 链接，拒绝且无 ev-ref 数据 |
| mutation/URL/disposition | 真实路由拒绝 POST、额外 URL/trusted/disposition 参数，无决定/下载/分享 |
| 重复 JSON/未知处置 | 重复 key、伪造 FACTORY_CERTIFICATION_VERIFIED，拒绝 |
| 单次 snapshot | 带 target 的 source 请求只允许一次 repository source read，不能先验证后再读出另一 case |
| 全 DTO 跨案例替换 | task-404 的整条 run/stage/pins 都改为有效 200，独立 task→case/owner holds 仍在 source lookup 前拒绝；不是让 DTO 选择自己的信任 |

已有 58 例保留 title/search HTML、bidi、非法 URL/长输入、未分配查询前拒绝、native source/HTML/Guard tamper、所有 8 阶段/11 任务及中性 403/WAF/robots/UNKNOWN 等覆盖。测试数量不替代以上独立边界。

## 浏览器

原控制台共用 HTML/CSS/服务，Chromium 156 真鼠标、键盘和 history 导航。1280/375/320 各执行：pool→task→review→target→source→返回，后退/前进保持同一 digest；404 与 200/null、完整 hash 披露、逐项 Claim 来源、中性阻断/UNKNOWN、错误摘要无泄露、真实中文筛选、XSS 输入和禁止非 fixture/跨 Origin/写操作/任意 URL。

初始已完成记录 `evidence/browser-2026-11-12T15-30-27-003Z`：**123/123，33 张原始 PNG**，仅作为对应旧源码的历史记录。task→case 独立绑定补强后新轮次必须再次完整通过，并以 ACCEPTANCE.json 指定的源哈希匹配记录为最终依据。DOM 与 CDP 原始 commands/network/responses、Chrome 版本、应用源文件/图片 SHA 均保留；≥12px privacy、≥44px 主要触摸区域、所有目标/展开/来源页无横向溢出，零外部页面请求。没有人类可用性评分。

首次 3 个断言后的 CDP Runtime.evaluate 导航超时保留；改为等待真实 Page.loadEventFired 再取 DOM，没有关闭 Chromium sandbox、改变业务断言、字号门槛或网络预期。

两份早期 bounded JUnit 虽各为 228 passed，但在运行中补充测试导致源哈希断言失败，没有 receipt，不计作最终通过。最终源冻结后的两份 receipt 才是有效结果。

最终四项 CI 回执使用实际 checkout、main/HEAD 顺序父 SHA、相同 Git tree、每项 QA 64+54 与 reviewing 127 实际调用、原安全 ZIP/245 命令证明。所有 RED、setup/infra 错误和失效封存尝试均保留；不为 GREEN 修改任何保护规则。
