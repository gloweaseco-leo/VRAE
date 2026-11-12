# 实测与原始记录

最终新鲜 Chromium 156、1280/375/320、404/200：**293 PASS /0 FAIL /0 ERROR /0 SKIP**，其中原固定 170 项全部通过，新增摘要/渐进展开/键盘/回查/无副作用 123 项。没有把失败改成 PASS。页面外部请求 0，Runtime 异常 0；无启用的发送/分享/导出。

- [真实旧版基线：170 PASS](evidence/baseline-browser-2026-11-12T10-47-34-682Z/results.json)，30 张实拍含 6 张首屏。三份 UI 输入与 accepted main 原始 Git bytes 逐字节匹配。
- [最终新版：293 PASS](evidence/reviewer-browser-2026-11-12T10-57-30-395Z/results.json)，42 张实拍：旧套件完整来源/iframe/模拟结果图、6 张新摘要首屏、6 张展开技术证据视图。每份原始 results/断言、CDP 命令、网络事件、stderr、输入快照和 executed-suite.mjs 均保留。

原 170 套件未覆盖或替换：从 accepted main 的原 Git blob 取得，完整原始文件保存在 reference/。`prepare-suite.mjs` 记录有限适配，反向逐项还原必须与原 Git bytes 完全一致。新旧运行的原 170 ID 集完全相同且逐项 PASS；附加 123 使用独立 P1- 前缀。为了操控真实折叠后的控件，兼容 click 先用鼠标点击祖先 summary；滚动后等待两帧再测原目标坐标。没有改为强制 DOM 点击、没有绕过 disabled 或放宽预期。新增 Enter 使用完整 code/virtualKey/text 事件。

新增检查包括首屏采购任务/事实辅助/证据按钮、12px 可见私有提示、精确 native 候选文字、原始 URL/HTTP/时间、0 问题限制/native null、UNKNOWN、技术区默认关闭、浏览器实际不可见的 SHA、全量原生引用可展开、真实证据点击与返回摘要焦点、Enter 激活、3px 焦点环、44px 控件、未自动勾选/正向仍阻断、native dossier JSON 不变和刷新重置。

| 原始运行 | 实际结果 | 处理与解释 |
| --- | --- | --- |
| [旧版 10:42](evidence/baseline-browser-2026-11-12T10-42-09-107Z/results.json) | 0 PASS /1 ERROR | 沙箱 CDP attach timeout；未计通过，经批准在沙箱外仅本地文件/封锁外网运行 |
| [旧版 10:45](evidence/baseline-browser-2026-11-12T10-45-15-156Z/results.json) | 165 PASS /1 ERROR | 320px 最后确认的鼠标事件后无结果，原断言执行报 null；保留，驱动增加布局稳定等待，不改旧界面或预期 |
| 旧版 10:47 | 170 PASS | 相同原版字节完整通过，首屏保留 |
| [新版 10:50](evidence/reviewer-browser-2026-11-12T10-50-37-683Z/results.json) | 173 PASS /1 FAIL /1 ERROR | 新增检查用矩形数量推断折叠可见性不可靠；改为 checkVisibility + 两层 closed 状态，原 FAIL 保留 |
| [新版 10:51](evidence/reviewer-browser-2026-11-12T10-51-59-014Z/results.json) | 178 PASS /1 FAIL /1 ERROR | 真正的摘要返回焦点问题：capture microtask 先于旧目标处理，最终焦点落旧入口；改为 bubble 阶段完成返回 |
| [新版 10:53](evidence/reviewer-browser-2026-11-12T10-53-34-757Z/results.json) | 182 PASS /1 FAIL /1 ERROR | 新增 Enter 驱动没有产生打开事件；补齐 Enter 的 code/virtualKey/text 后真实激活通过，未改按钮的原生语义 |
| [新版 10:55](evidence/reviewer-browser-2026-11-12T10-55-37-384Z/results.json) | 183 PASS /1 FAIL /1 ERROR | 鼠标返回的 programmatic focus 未显示 :focus-visible 环；摘要按钮新增显式 :focus 环，返回位置可见 |
| 新版 10:57 | 293 PASS | 当前冻结 UI 全通过；后续仅交付文档与 manifest |

上述 FAIL 后执行停止产生的 ERROR 也保留，不以去重计数美化结果。中途运行未到原套件最后两个全局检查时，不称其为 170 PASS。最终完整运行才给出原 170 + 新增 123 的结论。

原生安全/数据保护：本轮不运行 exporter 或改写 native 产物。封存验证所有 1990 个未授权修改的原 main 文件 blob/mode 保留，另外三份仅允许 UI 变动；原生 404 HTML SHA 6170722c97015cf113c3d7898c5cc342bf7cfea0113038bd07a48fdfd55d808c、200 SHA 4d815b29563341930c8a7a2b75f3aad416f04b3dc08683b7902c6f286d5e28a5 均不变。原 `syncPositive` 七项/原生确认门禁函数文本完全一致，Phase0.5 状态机与全部 Guard/held pins 不变。没有补造 200 Guard claim。

原始 stderr 包括 Chromium 本机启动诊断，原 CRLF 不裁剪；Runtime 异常为 0 只指页面观测。测试控制的 loopback CDP 不是应用 API。没有实际网站/模型、认证/DB、真实审批或客户外发。CI 只属于未改生产主干的回归，最终四项原始日志、测试 merge parents/tree 和精确 SHA 在 Draft PR 回填。Phase0 A01–A48 仍 NOT_RUN，QA PR48 不修改，Human Gold 0/26。
