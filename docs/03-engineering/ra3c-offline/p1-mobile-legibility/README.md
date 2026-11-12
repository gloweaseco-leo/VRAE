# RA3C P1｜手机私有提示字号最小修复

授权：[Owner 指定的独立 QA P1](https://github.com/gloweaseco-leo/VRAE/pull/47#issuecomment-6815824618)。
原 PR #47 / branch `codex2/ra3c-private-l1-report` / worktree `ra3c` 内修复，保持 Draft。
无真实模型/网站/客户报告、审批、分享、部署或 RA3D 生产代码。

## 实际变化

生产 CSS 仅将 mobile `.private-bar` 的 `font-size:11px` 改为 **12px**；
renderer 从 `ra3c-html-1.0.1` 升为 **1.0.2**。桌面和打印布局未重新设计。
source/Guard、`editorial.PROPOSALS`、C3/native schema、问题上限、NOT_RUN 处理均未放宽。
Caller pins 只更新 renderer 版本与由此派生的 rd-ref/HTML 摘要；原始来源/Guard 容器
SHA-256 仍为 `3189a276ffabfa307f9e0c478208941b3868bd27895f0281928c0d96000bb26b`。
完整内容/asset hash 自动变化；原生版本 id 包含 pins，因此 native hash 的衍生变化也保持原算法。
固定合成回放的输入 metadata/version 保持原值，新软件/制品由 renderer 1.0.2、rd-ref、HTML/asset
hash 与新 native report_version_id 区分。本轮没有持久客户报告或已批准版本的迁移/复用；
真实版本审批工作流仍属于尚未授权实施的 RA3D。

## 新版可查看产物

- [404 HTML](preview/contact-404.html)、[375px 截图](ui/contact-404-375.png)、[320px 截图](ui/contact-404-320.png)、[1280px 截图](ui/contact-404-1280.png)、[A4](ui/contact-404-A4.pdf)。
- [200 零问题](preview/contact-200.html)、[375px](ui/contact-200-375.png)、[320px](ui/contact-200-320.png)。
- [浏览器实测](ui/browser-acceptance.json)：六组合成样本 × 1280/375/320，18 个视图、108 次实际内部证据点击、0 外部请求/异常；屏幕提示最小计算字号均 >=12px、首屏可见、不横向溢出；六份 A4 单页断言保持。
- [原始 375px 11px RED](prior-renderer-red/banner-red-404-375.json)、[真实失败截图](prior-renderer-red/banner-red-404-375.png)。同一 >=12px 断言在原 HTML 上失败，没有改测试门槛。
- [新版 pins 变更记录](pin-update.json)、[旧 caller pins 原样快照](previous-caller-pins.json)。

复现（原锁定依赖的 Python 环境；Windows 进程使用 PYTHONUTF8=1）：

```text
python scripts/verify_ra3c.py --security-preview
node docs/03-engineering/ra3c-offline/p1-mobile-legibility/inspect-ui.mjs
```

托管沙箱内 Chromium CDP attach/create 超时的尝试不算通过；获准本机运行后才取得上述真实结果。
页面只能打开本地合成文件，原文转义，资源/CSP/网络保护及禁用控件保留。

## 旧 SHA 与重放兼容性

原 exact SHA **`6a7a3d3aa5f4341059b04567157f7fc58d6bf6d2`** 保留为普通合并祖先，
没有 rebase/force-push。原 `../preview`、`../ui`、原 CI/ZIP/JUnit/归档索引等记录原样保留。
本目录另存新预览/截图/记录，绝不将旧结果标成新代码生成。

**当前 loader 严格只接受当前 renderer pin，1.0.2 不能直接加载 1.0.1 草稿。**
新增回归用例显式检查旧 HTML 的原 hash 正确，但新 loader 按 REPORT_PIN_VERSION 拒绝。
旧报告可用原 SHA 的原引擎及原 caller pins 独立重放；不通过改 old pins 为新版本冒充兼容。
`previous_engine_replay.py` 在隔离的原 Git 源码快照里调用原公共 build/load 验证脚本，
分别记录两版 Python 的模块实际路径、源码摘要及八个旧 report refs。
原始输入哈希与字节来源见 [原引擎快照清单](previous-engine-source.json)。
本轮不增加多版本引擎注册或迁移功能。

## main 集成与后续记录

已正常 `git fetch origin main` 和 `git merge --no-edit origin/main`，无冲突：
merge commit `5acbb23f6e8a4e3a02144cf7cf7a076b48552c9e`，父提交为旧功能 SHA +
最新已验收 main `60dbe1e1acfc84ad0849e84f3abe3712ad8ebccd`（含已验收 Phase0 文档）。
未修改 Codex-1 QA 或 Phase0 设计文件，没有 RA3D 生产实现。

双 Python 全仓/历史重放已完成，见 [实际结果](RESULTS.md)、[源码与结果证明](source-and-results-proof.json)、
[原始字节归档索引](archive-index.json)。最后四项 hosted CI 和最终精确 SHA 以 PR #47 最终交付段为准。
报告回归实际 71 项，
不把 Codex-1 的 64 项独立 QA 输入边界差异算作产品通过或擅自修正其 oracle。
工程/视觉候选仍须 Owner 与独立 QA 在新 exact SHA 上验收，保持 private/NOT_APPROVED/不可分享。

封存中发现默认 Git archive 采用了 Windows CRLF 导出；报告 refs 虽全部相同，源码字节严格
比对仍拒绝。旧导出及两次运行记录在 `prior-export-crlf/` 保留；最终使用显式
`core.autocrlf=false/core.eol=lf` 导出，214 个文件分别匹配原 Git blob 后再执行两版旧引擎重放。
未放宽哈希断言。`archive-index.json` 指原始工作字节 ZIP；Git 文本换行规范化与这些原字节
分别核验，不能混用 JSON 容器摘要和规范化报告/HTML 摘要。
