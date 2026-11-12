# RA-4C0 验收矩阵

没有真实模型、真实采集、真实用户或人工审批。Python fixture 的 opaque context 仅为测试接线，非身份凭证。原生 404/200 报告、Guard、字节及引用按独立固定 pins 回放，不能由被测输入重置预期。

下列为独立业务边界；参数化变体不替代独立边界覆盖。具体函数与 58 个收集节点见 `tests/operator_console/test_console.py` 及原始 pytest/JUnit。

| 边界 | 输入/动作 | 必须结果 |
|---|---|---|
| 无可信调用者 | None / 空字典 | UNAUTHORIZED |
| 伪装身份 | 自报 tenant / OWNER 字典 | UNAUTHORIZED，无 repository 查询 |
| 跨租户 | 有效 fixture context 的 tenant 不一致 | UNAUTHORIZED |
| 跨 owner | 同租户不同 owner_scope | UNAUTHORIZED |
| 未分配任务 | 存在或不存在的未分配 ID | 同一拒绝；lookup spy 不可被调用 |
| 假生产接线 | source_kind=PRODUCTION / 无 TEST_ONLY 开关 | UNAUTHORIZED |
| 非法原生状态 | APPROVED / SHARED / BOGUS | INVALID_DTO |
| 阶段伪装 | 阻断原生状态配 REVIEW_REQUIRED 展示 | INVALID_DTO |
| URL 注入 | https URL / 协议相对地址 / 文件路径 | 拒绝；无网络访问 |
| 有界搜索 | >80 字符 | INVALID_INPUT |
| Unicode 控制 | bidi 控制 / 孤立 surrogate | 拒绝，不改布局 |
| 合同字段缺陷 | 非法 DTO/source/owner/stage | 拒绝，不降级到可信默认值 |
| 旧版本核对上下文 | version 1 链接面对 version 2 | STALE_VERSION；即使改参数 2，也与原生 v1 不匹配而拒绝 |
| 哈希替换 | 任务 HTML hash 与独立 held 不同 | SOURCE_INTEGRITY |
| 跨证据替换 | 404 任务引用 200 source case | 拒绝 |
| 引文篡改 | 改原生 source quote | SOURCE_INTEGRITY |
| HTML 字节篡改 | 改保留 source blob | SOURCE_INTEGRITY |
| Guard 篡改/遗漏 | 改 guard_ref / 移除 guard_inputs | SOURCE_INTEGRITY |
| 原生 metadata/package 篡改 | 版本/包引用变化 | SOURCE_INTEGRITY |
| 最终渲染替换 | render 实际返回字节被替换 | SOURCE_INTEGRITY |
| 非法 pin envelope | 多字段、布尔 issue_count、坏 SHA、空 ref | INVALID_DTO |
| 来源不就绪 | 403/WAF/robots/UNKNOWN/无效 Guard/失败 | 无报告；不能据此判断网站缺陷 |
| HTML 注入 | 标题与搜索含 script/img/onerror | HTML escape；无脚本、外链或执行 |
| 可变 DTO 别名 | 修改输入及解析后的 dict | 不修改 frozen payload |
| 写操作/下载 | POST approve、DELETE、share、download | 固定拒绝，无副作用；匿名同样拒绝 |
| 畸形路由/查询 | 重复参数、路径穿越、负索引、缺版本 | 固定拒绝，无原始保护数据 |
| 预览启动边界 | 缺任一开关 / 0.0.0.0 | 不启动 |

正常业务验证包括：8 类阶段和 11 项任务、分配内过滤/搜索、404 一条问题与三条 HUMAN_REVIEW_REQUIRED、200 零问题且没有捏造 CTA binding、原始 UTF-8 区间及 SHA、来源/时间/ref 一致。

## 真实浏览器

`browser-test.mjs` 当前 75 项断言（不是 75 个人工测试），分别在 1280、375、320 实际执行：

- 任务池 → 404 详情 → 只读报告 → 原始证据 → 展开完整字节 → 返回报告/详情/任务池。
- 相同 200 路径；核对零问题、CTA 无 Guard 的真实边界与原生来源。
- 403 与 UNKNOWN 中性状态，均无报告入口。
- 键盘 Tab 的真实焦点和 outline、主要交互 44px、隐私提示 ≥12px、折叠/展开均无横向溢出。
- 真实 GET 筛选、搜索注入与旧版本请求；HTTP 无 fixture、跨 Origin、POST 写操作、任意 URL 参数的拒绝。
- 原始 CDP requests/responses/commands 与 Chrome 版本、所有截图 SHA；页面零外部请求、零脚本异常。

保留第一次沙箱 Chromium 启动失败，以及首次完整浏览器末尾 URL 参数分类失败；修复路由而不放宽预期。保留全部中间通过记录；普通合并 `225ded57...` 后最终绑定功能 HEAD 与全部应用源文件哈希的目录为 `evidence/browser-2026-11-12T14-03-00-298Z`，75/75 通过，包含真实选择阶段、输入中文并点击筛选提交。

新 main 上的双 Python 补充回归各为 62 passed：58 项应用边界与 4 项既有 `tests/reviewing/test_strict_metadata.py` P1 原用例。该测试文件、reviewing 源码和冻结 QA 均未修改；UI 不对接其审核 API。两份原生 404/200 回放也分别复验，原生 ref/HTML 哈希未变。

## 原有验收不变

双 Python 原有默认全量、V2 64 主例 + 54 拒绝项实际收集、历史 V1 显式重放保持原有 53 RED、19 条历史命令（伪 Gold exit 1）和 8 个封存原生报告均保留。Gold 仍 0/26。

四项 GitHub CI 必须逐项读取真实结论与 checkout/merge parents；不能把启动、排队、未收集或前一 SHA 的通过称为最终通过。原 HTTP 镜像缺源码的失败已保留；Owner 唯一 COPY 例外及最小修复见 CI-SCOPE-EXCEPTION.md。没有跳过新增测试、修改预期或把 RED 标成 GREEN。
