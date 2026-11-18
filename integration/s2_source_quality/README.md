# INFO-03 / TECH-02 来源候选

从 accepted main `d38fd7263ea0d8ce357de54ef22cda90cdb86b9b` 独立增量。
复用原 EvidencePack、SourcePolicy、IndustryPack 和 `s2-projection-1.2.0`，新增可选只读候选；原投影字节、六条启用规则、Guard 和 S3/S5 接口均不变。

## 运行与复核

Python 3.13，安装仓库 `requirements-ra4b-p1.lock` 后运行：

```sh
python -B -m pytest -q tests/s2_contract/source_quality_cases.py integration/s2_source_quality/view_cases.py
python -B -m integration.s2_source_quality.demo local-demo
```

演示只用合成的 `example.org` 已保存输入和原 Collector 的内存 transport；没有对这些 URL 发网络请求。真实 HTTP 只访问原 B5B server 的随机 loopback 端口，经原 nonce、CSRF、签名身份和 HttpOnly session 读取。输出在本目录 `.runtime/local-demo`，重复运行须使用新标签。

每个场景输出 pack、原 parent、候选 JSON、业务 HTML 和总览 `summary.json`。`*-pack.json` 包含 document 和 objects_base64；demo 实际解码、调用原 EvidencePack.load 重载并重新校验候选与每条原文字节，而非仅保存 manifest 哈希。候选的 URL、采集角色、采集时间、source/snapshot/evidence refs、SHA256、UTF-8 起止位置和 quote 可逐字复核。HTML 是离线业务预览；签名 HTTP 的页面与原文链接另由 demo 真实请求验证。没有把合成来源说成客户实站，也没有把 fixture 验证算作准确率。

## 能得到什么

| 业务样例 | 可核对来源 | UNKNOWN / 人工边界 | 采购影响假设与 Rebuild 候选 |
| --- | --- | --- | --- |
| 静态产品页 | P40/R1、原文 `Do not assume NPSH or PN10 suitability without engineer review.`、abbr title | 缩写正确性、英文可理解性、否定句不能反转 | 核对工况与术语展开，工程责任人确认后组织英文参数说明 |
| CMS | 原文 OEM/VFD 与 generator 声明 | 不因 CMS 或缩写直接判 FAIL | 统一资料模板与术语表 |
| SPA | 已保存 shell、script src | 没有新增渲染；正文/JS 资源 UNKNOWN | 先补获准的正文来源，再决定静态技术资料入口 |
| 多 SKU | 同页 P40/P80 来源线索 | 不混写成已确认单型号；model/revision 不伪绑定 | 型号、版次、参数和资料建立明确关系 |
| 多语种 | 英文/中文原文与语言声明 | 切换语言不等于低质量，需目标买家语义复核 | 人工确认中英文对应和术语一致性 |
| 图片/标题 | 缺 alt、空 alt、h1→h3；同次已记录 URL HTTP404 | 空 alt 不自动证明装饰图；HTTP404 不证明浏览器坏图 | 逐图确认用途，再写 alt；按实际内容修订标题层级 |
| 缺资料/拒绝/未留存 | 404、403、无原文字节的元数据 | UNKNOWN / ACCESS_BLOCKED，不补造缺陷 | 明确需补的获准来源与责任人 |
| 无 img / 重复属性 / 恶意原文 | literal img 子集不适用、歧义 HTML、原文转义 | CSS/SVG/canvas/JS 图片未知；歧义整页 UNKNOWN；原文不执行指令 | 复核来源后再作改造决定 |

图片响应查找只匹配同来源、同采集窗口、已捕获的同源 URL。图片 MIME、200、404 都不能证明正文、图片解码或实际加载；未捕获资源继续 UNKNOWN。原 Collector 不跟随 `.png` 链接；样例使用无扩展名的响应地址，且保持 max_pages=8，未扩大采集策略。

原 NativeSource 对非正文响应引用存在既有适配限制；404/图片 MIME 保留在独立候选样例，签名页面的同 pack 示例使用原链支持的 HTTP200 HTML 响应，并仍标注图像解码 UNKNOWN。本轮没有修补或绕过原报告权威，也没有声称完成 APP202/Worker 链。

## 接口与约束

调用 `evaluate_source_quality(pack, parent, held=SourceQualityPins(...))`。服务端独立固定 parent ref/version、IndustryPins、tenant/run/policy、1–8 个 snapshot/URL/role/time 和可选已证实 model/revision、采集时间窗口；`verify_source_quality(..., expected_quality_ref=...)` 重算并逐字节比较，重哈希不使跨来源伪造合法。

完整字节最多 128KiB、原 StaticHTML 子集 node512/depth64、最多128个标签与每规则128项；不支持的 HTML/浏览器 v1 字段不做推断。只有选中页面分母，列出未选中数量，全站分母 null。Gold=0、precision=null、NOT_EVALUABLE。没有 WCAG、SEO 排名、全站得分或16/16承诺。

`QualityWorkbench` 是原 Workbench 的可选 reader，使用同一个 DeepConsole/Directory/Ledger，挂在同一报告的 `/source-quality`；原签名权限和当前版本在渲染前后校验。没有新建身份/报告服务。默认 S5 安装方式不变；启用须显式组合该 reader，因此不阻断 Codex3。

业务界面保留原五维导航，仅 UNDERSTAND 与 SEARCH_TECHNICAL 增加这些来源线索。每条候选分开呈现来源、采购影响**假设**、客户待核实事项、Rebuild action/owner/acceptance/service fit；价格和工期 UNKNOWN。所有结果私有、不分享、不晋升原事实。

回退：不安装可选 reader，停止调用新模块即可；没有迁移、外部写入或持久化新事实。
