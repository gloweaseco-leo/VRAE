# VEYFRONT 私有 L1 一页报告 · RA-3C

> **P1 更新入口**：[手机提示 12px 修复及最新产物](p1-mobile-legibility/README.md)。
> 本文件下方原截图/预览/验收记录对应保留的 `6a7a3d3…` / renderer 1.0.1，未覆盖为新版。
> 当前 `verify_ra3c.py` 默认输出到 P1 专属目录；新版浏览器检查使用该目录下 `inspect-ui.mjs`。

本目录是 **合成工业网站的内部审阅样本**，不是客户报告。所有页面均为
`private=true / NOT_APPROVED / shareable=false`。无真实网站、模型调用、客户外发、部署、审批或 ShareGrant。

## 先看实际报告

- [404：一个可回查的联系路径问题](preview/contact-404.html)
- [410：独立捕获，一个问题](preview/contact-410.html)
- [200：零问题检查范围摘要](preview/contact-200.html)
- [403：受限范围摘要](preview/contact-403.html)
- [500](preview/contact-500.html)、[robots](preview/contact-robots.html)、
  [未保留正文](preview/contact-unretained.html)、[WAF](preview/contact-waf.html)：均不编造缺陷。
- [同一捕获四个不同目标，仅列三个](preview/contact-multi.html)
- [原始页面含 script/img/onclick 的安全样本](preview/contact-xss.html)
- [桌面截图](ui/contact-404-1280.png)、[手机截图](ui/contact-404-375.png)、
  [手机证据回查](ui/evidence-404-375.png)、[真实浏览器记录](ui/browser-acceptance.json)。

下载/本地打开 HTML 即可审阅，不需要服务端或互联网。GitHub 文件视图显示源码；请使用本地文件，
不要上传到在线 HTML 预览服务。页内“原始证据”链接打开隐藏的纯文本证据面板，
包含原始 URL、quote、UTF-8 字节区间、捕获时间、HTTP、Observation、Evidence、Binding、Guard、
EvidencePack、RuleExecution、FindingPackage 及 native bridge；返回链接回到报告。
证据 URL 是文字，不是外部可点击链接。

## 可重复运行

在仓库根目录、已按原有锁文件配置的 Python 环境中执行：

Windows 中文系统请设置 `PYTHONUTF8=1`；原有全仓源码扫描使用默认文本编码，
否则会用 GBK 读取新增中文 UTF-8 源码。此项只配置进程编码，不改测试或证据预期。
本目录 `regress.py` 为子进程显式设置该变量。

```text
python scripts/verify_ra3c.py
python scripts/verify_ra3c.py --security-preview
python -m pytest -q tests/reporting
node docs/03-engineering/ra3c-offline/inspect-ui.mjs
```

最后一条使用本机已缓存 Chromium，无 npm 包或浏览器下载。脚本中的默认 Windows Chrome 路径可通过
`RA3C_CHROMIUM` 环境变量覆盖（参见脚本）。Chromium 只打开本目录 file 页面，阻断外网，
无外部字体、图片、脚本；检查 1280/375 布局、内部证据导航、恶意内容不执行及 A4 单页打印。
浏览器验收和工程 CI 是两组真实记录，不把本机截图称为 GitHub 浏览器安全 CI。

## 数据与信任边界

见 [REPORT_CONTRACT.md](REPORT_CONTRACT.md)、[业务审阅备忘](REVIEW_MEMO.md)、
[测试矩阵](TEST_MATRIX.md)。`tests/reporting/fixtures/sources.json` 保留原始合成证据和 Guard 输入，
独立 `caller-pins.json` 保留调用方持有的 refs、版本、scope、metadata SHA 和预期输出哈希。
200/404/410 原始 pack/package 直接复用已验收 RA3B 固定捕获；其余合成样本只经原有
Fake Collector、RA2 执行器/C3 和 RA3B 公共验证器产生。没有真实 provider 或通用语义判断器。

RA3C 仅支持当前已验收能力能够证明的 CTA-02 静态 href→404/410。
其他规则失败不擅自转换为缺陷；它们计入 `unsupported_rule_findings` 并明确提示。
静态页面角色和字面引文不能核验企业、证书、产品规格真实性、表单送达或商业效果。
Human Gold 仍为 **0/26 / QUALITY_GATE_NOT_EVALUABLE**，不是准确率或客户就绪度证明。

## 版本与失败记录

`preview/` 是当前输出；各 `preview-initial` / `preview-print-red*` 是发布前布局版本留档，
不会用于当前预期。原始 source/Guard 输入从首次封存起 SHA-256 始终为
`3189a276ffabfa307f9e0c478208941b3868bd27895f0281928c0d96000bb26b`。
`initial-render-baseline.json` 和 `print-red*-baseline.json` 保存每次旧输出 pin 和变更原因；
只更新本轮新渲染器的输出摘要，未改变事实、来源、Guard、问题数量或一页打印断言。
`ui/print-red-*.pdf/json` 保留实际两页失败及几何诊断，不将过去 RED 重写为 PASS。

初次测试有一处测试构造器参数错误（EvidencePack 对象映射应转换为 tuple），修正该新增测试后通过；
原有测试和预期未改。初次沙箱浏览器 attach 超时，经获准本机运行后完成真实 Chromium 验证。

## 工作范围与后续

独立工作树 `ra3c`，分支 `codex2/ra3c-private-l1-report`；由已验收
`1d9d08ec3b99fc10ff7ea181d210250841ee39a3` 建立。Owner FINAL PASS 后的 QA44
main `2429be6dc5d7dcb48221ab179f063b93ce4b1956` 已通过正常 `git merge --no-edit origin/main`
集成（当时尚无功能提交，因此 fast-forward），完整保留 QA44 原文件。
所有新增内容限定 Issue #45 四个授权路径；工程/产品/合同/旧版本/安全/Gold/CI/依赖均保留。
独立 Draft PR 提交后停止，等待 Owner 功能、业务和 UI 独立验收。

最终本地验证见 [LOCAL_RESULTS.md](LOCAL_RESULTS.md)，完整原始记录及 JUnit、逐文件
摘要分别见 `archive-index.json`、`artifact-index.json`。开发期 RED 与编码处理见
[DEVELOPMENT_RECORD.md](DEVELOPMENT_RECORD.md)。最终精确 HEAD 与四项新 hosted CI
记录以 [Draft PR #47](https://github.com/gloweaseco-leo/VRAE/pull/47) 的封存交付段为准。

字节核验：`artifact-index.json` 记录 Windows 原始工作文件字节，对应
`current-artifacts-raw.zip` 内的精确条目。`source-fixtures-raw.zip` 保留首次封存的
source/Guard JSON 容器及最终 caller pins 的精确原始字节；上述 `3189…26b` 为该
Windows JSON 容器 SHA。Git 的文本换行规范化可能改变仓库显示的 JSON 容器字节，
不改变解码后的原始对象字节、Guard/pack refs、报告规范化清单或 HTML 字节哈希。
需逐字节核验时使用 ZIP 内条目和 archive-index.json；Git blob/mode 证明另列，
不会把换行规范化误报为证据或内容篡改。
