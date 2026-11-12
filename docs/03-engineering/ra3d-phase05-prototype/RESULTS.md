# Phase 0.5 实测与证据

验收对象仅为本目录的离线合成 UI。没有运行/认领 Phase 0 的 A01–A48 或 PR #48 的独立 RA3C QA；它们不因本轮浏览器通过而改变状态。

最终冻结浏览器运行：[browser-2026-11-12T08-23-38-421Z/results.json](evidence/browser-2026-11-12T08-23-38-421Z/results.json)。真实 Chromium 156.0.8078.4，Node 24.13.0 + CDP，直接加载本地文件；**126 PASS / 0 FAIL / 0 ERROR / 0 SKIP**，21 张原始 PNG。每条断言带当前 UI 反馈、焦点和内存轨迹，另存原始 CDP 命令与网络事件；六份当时输入的精确字节保存在该次 `input-files/`，哈希列入 results 与 manifest。

| 覆盖 | 实际检查 | 结果 |
| --- | --- | --- |
| 1280 / 375 / 320 px × 四场景 | DOM lang、viewport/scrollWidth、顶部可见私有提示、最小字体、控件高度 | 12 组布局通过；提示最小 12px，scrollWidth 不超过 viewport，主要按钮/标签触控区域至少 44px |
| 原文 | 点击 quote、source/href/时间/响应/字节定位、完整惰性攻击片段、返回焦点 | 三宽度实际点击；没有图片/iframe/攻击标记执行 |
| 键盘 | 返回后 Tab 到事实勾选、Space 切换、可见焦点、拒绝场景选择 | 三宽度实际 CDP 键盘事件；outline >=3px |
| 正向前提 | 初始禁用、七项核对、二次确认、取消焦点、最终模拟结果 | 保留 NOT APPROVED；无真实 APPROVE/分享标志 |
| 退回/拒绝 | 无理由阻断、有理由二次确认、恶意备注以文本呈现、本轮关闭 | 不覆盖来源，不保留可继续正向操作 |
| 0 问题 | 独立 200 捕获/引用、native=null、范围核对、正确摘要 id 的确认 | 没有批准/退回报告入口，仅内部范围模拟 |
| 版本 | 版本、HTML、引用、摘要、页脚、布局、来源、租户变化 | 旧勾选/正向结果失效；来源/引用/HTML 不可自行重绑定 |
| 确认期间变化 | 通过原有模拟变化按钮派发背景版本事件，再确认 | 阻断旧操作，未形成结果。此项使用 DOM click 触发“后台变化”，其余常规操作采用鼠标/键盘事件 |
| 缺证/拒绝 | 来源缺失；跨租户/未分配/Guard REJECTED 固定视图 | 正向禁用；拒绝 DOM 无任务 id、quote、hash 或原文入口 |
| 刷新/外发/外联 | Page.reload、无 share/export/send 控件、原型源码禁止存储与网络 API | 刷新清空内存；页面外部请求 0，运行时异常 0 |

截图导航（实际 PNG，未重绘）：

| 场景 | 桌面 1280 | 手机 375 | 窄屏 320 |
| --- | --- | --- | --- |
| 初始核对 | [1280](evidence/browser-2026-11-12T08-23-38-421Z/contact-1280.png) | [375](evidence/browser-2026-11-12T08-23-38-421Z/contact-375.png) | [320](evidence/browser-2026-11-12T08-23-38-421Z/contact-320.png) |
| 原文已打开 | [1280](evidence/browser-2026-11-12T08-23-38-421Z/evidence-1280.png) | [375](evidence/browser-2026-11-12T08-23-38-421Z/evidence-375.png) | [320](evidence/browser-2026-11-12T08-23-38-421Z/evidence-320.png) |
| 正向仅模拟 | [1280](evidence/browser-2026-11-12T08-23-38-421Z/positive-simulation-1280.png) | [375](evidence/browser-2026-11-12T08-23-38-421Z/positive-simulation-375.png) | [320](evidence/browser-2026-11-12T08-23-38-421Z/positive-simulation-320.png) |
| 退回修改 | [1280](evidence/browser-2026-11-12T08-23-38-421Z/changes-1280.png) | [375](evidence/browser-2026-11-12T08-23-38-421Z/changes-375.png) | [320](evidence/browser-2026-11-12T08-23-38-421Z/changes-320.png) |
| 零问题 | [1280](evidence/browser-2026-11-12T08-23-38-421Z/coverage-1280.png) | [375](evidence/browser-2026-11-12T08-23-38-421Z/coverage-375.png) | [320](evidence/browser-2026-11-12T08-23-38-421Z/coverage-320.png) |
| 旧结果失效 | [1280](evidence/browser-2026-11-12T08-23-38-421Z/stale-1280.png) | [375](evidence/browser-2026-11-12T08-23-38-421Z/stale-375.png) | [320](evidence/browser-2026-11-12T08-23-38-421Z/stale-320.png) |
| 拒绝视图 | [1280](evidence/browser-2026-11-12T08-23-38-421Z/denied-1280.png) | [375](evidence/browser-2026-11-12T08-23-38-421Z/denied-375.png) | [320](evidence/browser-2026-11-12T08-23-38-421Z/denied-320.png) |

原始失败和中间运行全部保留：

| 运行 | 原始结果 | 处理 |
| --- | --- | --- |
| [07:15:30](evidence/browser-2026-11-12T07-15-30-428Z/results.json) | 0 PASS / 1 ERROR，沙箱 CDP attach 超时 | 未计通过；经批准沙箱外运行本地离线 Chromium |
| [08:17:19](evidence/browser-2026-11-12T08-17-19-716Z/results.json) | 33 PASS / 1 ERROR，键盘选择 guard 得到 foreign | 真正的焦点丢失：拒绝选择重绘后恢复焦点，再完整重测 |
| [08:18:07](evidence/browser-2026-11-12T08-18-07-207Z/results.json) | 108 PASS / 0 ERROR | 当时范围通过；后续增加完整性变化不可自证重绑定与确认期间变化检查 |
| [08:20:02](evidence/browser-2026-11-12T08-20-02-866Z/results.json) | 120 PASS / 1 ERROR，关闭 target 后汇总仍用旧 CDP session | 修正测试脚本 session 生命周期；不放宽 UI 断言 |
| [08:22:18](evidence/browser-2026-11-12T08-22-18-402Z/results.json) | 123 PASS / 0 ERROR | 增加 200 独立捕获后通过；再校正确认框摘要 id 并补断言 |
| 最终 08:23:38 | 126 PASS / 0 ERROR | 当前应用六份输入 hash 均匹配此运行；后续只整理交付证据 |

另有一次 PowerShell `node -e` 字符串引号错误，退出 1，未写入文件；随后使用结构化 patch 完成修改。以上 ERROR 保持原样，没有改名 PASS、删除记录或增加 skip。没有出现独立 ASSERTION_FAILED 类型 FAIL；真实产品焦点缺陷由选择器断言异常记录为 ERROR。

网络观测限于被测页面的 Network.requestWillBeSent，不声称测量操作系统所有后台流量。Chromium 禁止背景更新/扩展、黑洞代理与 DNS；页面另有 CSP 和 CDP blocklist。CDP loopback 连接只用于测试控制，没有应用 API 或服务端。本地 profile 是隔离测试浏览器的运行数据，被排除出交付；原型没有 local/sessionStorage、cookie、IndexedDB 或 Service Worker。

[seal-evidence.mjs](seal-evidence.mjs) 逐一验证合成来源 SHA/quote 字节、全部截图 SHA、最终应用输入与浏览器固定值一致、JavaScript 语法。最初保护开工 main 的 1416 个文件；Owner 合并 PR #47 后，普通 merge 最新已验收 `61b88eb31d1dec668e7e05495b88fe2d8a5b25fe`，扩展为 **1611 个 main 原始文件 mode/type/blob 全保留**。没有扩大原型权限或修改被测六份输入。manifest 自身排除以避免循环哈希。[audit-delivery.mjs](audit-delivery.mjs) 在最终提交后只读核对 clean-tree、全部清单文件的 Git 原始字节、代码 SHA 与最终 head 输入一致。最终 PR 精确 head 与实际 audit 输出在 PR 描述中记录；不在自指文件中伪造最终提交 SHA。

GitHub CI 若触发，仅为未修改的 main/doc 回归；它不能认证 126 项独立本地 UI 结果，不能将 Phase 0 的未来 48 项标为已执行，更不能证明真实人审、事务、跨租户安全或客户可用性。实际 CI 链接、状态和精确 head 以 Draft PR 描述为准。
