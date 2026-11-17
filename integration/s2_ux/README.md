# S2-C2 P0 · 原浏览器证据解析

基线 `84276325befdcf858852a1ec791e8b0695a515eb`；任务 Issue119 / 总控 Issue117。

这个子包实际实现 `vrae.rules.s2_ux.project_browser(pack, *, held: BrowserPins)`：
服务端独立 held pack/tenant/run/policy/version、选择的原 source_refs 及本任务观察时间窗；
完整重放原 EvidencePack，读取原 BrowserObservation DOM 的原 bytes/ev/page/src 引用。
输出不可变规范 bytes；只有可回定位的文本/标签候选和明确 UNKNOWN/ACCESS_BLOCKED。
它不是新 evaluator，不授予来源权限，不写 Fact 库，不创建报告或审核决定。
原签名当前任务权限仍须由调用方持有；SHA 和时间窗自身不证明签名来源。

## 明确的能力边界

| 规则 | 当前能读取 | 仍不能据此判定 |
| --- | --- | --- |
| INFO-03 | 原有界文本中的中文/占位候选及原 JSON pointer，HUMAN_REVIEW_REQUIRED | 英文质量、买家流失、专业术语正确性、图片正文、整页语言完整性 |
| CTA-01 | A/BUTTON 的原文本及宽高非零记录 | href、实际可见/可点击、真实提交与邮件送达 |
| CTA-03 | 原390px/1280px观察是否存在、缺失与阻断 | 遮挡、横向溢出、完整可用性/WCAG |
| TECH-02 | 原 H1/H2/IMG 标签候选 | alt/src、对应资源的实际加载、排名/Lighthouse/无障碍效果 |

这些是 P0 的解析能力，不计四规则已支持。没有浏览器观察不能 PASS；
空元素表/128上限不能推出页面缺少 CTA/标题；扩展或异常 DOM 字段不产生新测量权威。
未访问视口计 NOT_VISITED；当前仅统计选择的 URL×视口，不能替代 C1 受信 scope_manifest 的角色/站点分母。
NOT_APPLICABLE 需要后续 C1 受信适用性契约，本解析器不从缺资料自行设不适用。

## 可运行验证

```sh
python -B -m pytest -q integration/s2_ux/test_projection.py tests/evidence tests/rules
node integration/s2_ux/browser.mjs unique-label
```

真实 Chrome 从 CDP 只读加载同一合成 HTML，所有其他请求拒绝，禁 DNS/代理直连；不发送 RFQ。
在1280/390/375/320四宽度记录原 DOM_SCRIPT、实际截图及额外诊断测量。
clean/hidden/covered/overflow/multilingual/blocked 六情景证明：非零宽高不能代替可见性/命中、
原 DOM 不保存 href/alt/几何，且未授权子请求被拒。
**额外测量只在隔离 fixture 中用于复核方案，不塞进 BrowserObservation/EvidencePack，不冒充原生来源。**
375/320目前只是离线回归，原生产 BrowserObservation 的授权视口仍是1280/390。
单元合成 DOM/PNG 明确不是真浏览器证明；真实截图也不替代原任务签名/版本权威。

所有运行写入唯一 `.runtime/<label>/`；失败目录保留，不重用 label。
专属 Chrome 进程退出回执保留；无 PG/Worker/容器资源，浏览器 profile 留作本地故障依据而不上传。
CI 上传真实 DOM/截图/协议/退出记录及原生 JUnit，不上传浏览器 profile。

## 后续依赖

C1 Issue118 的 S2 adapter 签名、版本、受信 scope_manifest、独立 verify 重算及富 DOM 的最小合法入口
尚须 Owner 验收合并。未合并前不编辑 execution.py、不复制 Draft、不改变采集/SourcePolicy/pack/Guard。
P1 在此入口可用后接四规则与原唯一签名 SSR 五维审阅；P2 再做同源 PG/Controlled/Chrome 回归。
本子包不声称 S2整机/质量PASS，Gold仍0/26，模型调用0，无真实站点/外发/正式人审。
