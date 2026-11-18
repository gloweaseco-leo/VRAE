# 两张采购来源卡连接到原五维 SSR

授权：[Owner CODE GO](https://github.com/gloweaseco-leo/VRAE/pull/131#issuecomment-6968258081)。
从 accepted main `4a227f1b58afc97d8af1778a066f37b80ff0f399` 开独立小分支；
复用已合并 PR130 的 `S2BuyerTaskCandidate / verify_candidate` 及 PR131 的原签名工作台。
没有复制未合并 Draft，也不扩展 PR127 的 D0 工具链。

## 用户看到的连接

仅连接同一来源声明型号 P40 的两张卡：INFO-02 参数/版本与 TRUST-02 证明声明。
393px 首屏直接回答“看到什么／采购帮助（待确认）／还不知道／向企业索取什么”。
两卡分别放在原 UNDERSTAND / TRUST 维度，相同 observation 的原通用行不重复展示；
其它型号、其它来源行和五维结构保留。

卡片呈现 C1 已重放的资料版本/声明工况或证明类型/日期关系，以及原有
`HYPOTHESIS_REVIEW_REQUIRED` 文案、未核验边界、下一步索取清单。
没有用自编文案替换 DTO 内的假设，也不把日期比较说成证明有效。
来源详情页同时显示该卡上下文和原 UTF-8 字节、URL/时间；HTML 仅作转义文字。
缺材料、访问受阻或配置不适用时不造引用，不升级为 FAIL。

## 原授权链和独立 pins

受信 server fixture 从原 NativeSource 的当前 pack、固定 profile、P40 snapshot
配置一次选择，生成不可变 BuyerCandidatePins / ObservationPin；HTTP 不接受这些 pins、
model、版本、角色或用户上传 DTO。选择来自已重放 projection，不能从前端 candidate
反推可信任务。两卡共享同一个受信 subject snapshot，证明来源仍保留自己的引用页。

原 Application 的 Host/Origin 检查、Directory.require、DeepConsole.current、
Ledger.read/access、租户/定向授权/撤权/过期及渲染后版本/hash 重验原样继续。
主页面与 `/source-tasks/buyer-cite/0|1` 均先重验原报告/pack/scope，再调用原
`verify_candidate` 重算候选；自重哈希不能引入不同文案、状态、来源或选择。
profile、industry/reporting/rule/source 版本与 snapshot pins 均由原 C1 API 验证。

所有卡仍为 `READ_ONLY_REVIEW_CANDIDATE`，`native_fact_admission=NONE`。
原报告 payload/hash、Finding/blueprint 审核项和 Controlled 决定的结构不变；
查看卡片不写原账本。回原审核提交仍是原表单、原版本和原责任人接口。
本连接仍只限已验收 CONTROLLED + OFFLINE_SYNTHETIC 组件，不替代 M1/Worker 的权威。

## 验证

```sh
python -m pytest -q integration/s2_buyer_workbench \
  integration/l2/test_l2.py integration/l2/test_codex1.py \
  tests/s2_contract/p1_industrial_cases.py tests/s2_contract/buyer_candidate_cases.py
python -B -m integration.s2_buyer_workbench.lab buyer-cards-unique-label
```

真实 Chrome 本地首轮：29项检查、10张实图。主视口393与1280，以及375/320回归
均实际验证四类信息在首屏、两卡只读身份、44px操作目标与中文glyph；实际点击两卡
来源、原蓝图和原审核，原决定提交后同一报告hash保持。跨租户/未领取授权继续拒绝。
源代码在 live run 前后比对 hash，私钥仅在HTTP子进程外，cookie/私钥/配置不公开。
本地实物为提交前预检；新HEAD双minor自然CI的 source.json 是本轮正式源码记录。

原生新增用例覆盖自重哈希文案伪造、tenant/run/pack/snapshot/profile/version替换、
同包跨型号拼接、来源详情权限、撤权、渲染中真实版本变化、原报告/hash/审核项不增，
并显示原 C1 UNKNOWN / NOT_APPLICABLE / ACCESS_BLOCKED 状态。原 C1 37项候选负例
加入现有本分包显式CI命令；原测试默认库存和所有旧门禁不删除、不放宽。

本地组合152/152通过；补强版本竞态单例1/1通过，确认账本真实追加到v2且旧渲染
被拒绝。正式CI回执额外记录服务端独立held pins、原report version ID/content hash，
用于核对snapshot/profile/version绑定；这些回执自身不授予读取或审核权限。

## 保留边界

“来源”是已验收的 P40 合成资料包中的实际保留字节，未抓真实第三方站点。
工程适配、证书真伪和有效性保持 UNKNOWN。没有伪审核项、Guard事实晋升、RFQ、
付费模型、外发、正式人审或生产部署；Gold仍0/26，不宣称S2 EXIT或10规则完成。
PR124旧40/42仍HOLD；PR127不合并不扩展，历史Chrome根因UNKNOWN。
下一批 DOM/UX 候选须按具体 SourcePolicy 许可另行推进。
