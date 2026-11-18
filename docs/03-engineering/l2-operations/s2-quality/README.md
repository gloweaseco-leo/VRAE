# S2-C3 P0｜离线质量基准与真人 Gold 接收

执行 [Issue120](https://github.com/gloweaseco-leo/VRAE/issues/120) 与 [S2 总控117](https://github.com/gloweaseco-leo/VRAE/issues/117)，accepted main：`84276325befdcf858852a1ec791e8b0695a515eb`。

这是独立质量工具 P0，不是完整 S2 EXIT。原 S0 PR112 已合并，整机启动器、Worker、SSR、Guard、审核和 Brief 权威均沿用，不在此包重做。C1/C2 候选代码未导入。

## 操作入口

使用仓库锁定测试依赖的原生 Python3.11 或3.13：

```powershell
python integration/l2_ops/s2_quality_cli.py evaluate
python integration/l2_ops/s2_quality_cli.py packet --output integration/l2_ops/.private/new-reviewer-packet
python integration/l2_ops/s2_quality_cli.py verify-export --output integration/l2_ops/.private/new-reviewer-packet
python integration/l2_ops/s2_quality_cli.py assess
python integration/l2_ops/s2_quality_cli.py legacy
```

默认评估只读；仅显式 `packet --output` 导出。输出已有内容若被人改动则拒绝覆盖。包内含原始 EvidencePack 对象、来源与哈希、原生生产者 pin/观察、具体定位、候选理由及两名独立审核人的空白字段。原26项另放 `original-26/`，由未修改的原工具生成。新 S2 单元与旧26项拥有独立 packet/unit refs，不混作同一个 Gold 集合。

审阅者先核对原文、URL、字节位置/原生定位、时刻、适用范围和未捕获项；然后分别提供有界裁决、理由、真实身份与带时区时间、证据引用及严重事实虚构检查。意见冲突须交第三名独立人员裁决，最后由 Owner 在带外核验并签署确切 review set 与 row 哈希。工具不生成签署、身份、日期或审批许可。

```powershell
python integration/l2_ops/s2_quality_cli.py assess --packet <s2-packet.json> --review <actual-review.json> --approval <external-owner-attestation.json> --signature <external-signature> --allowed-signers <outside-repository-anchor> --anchor-sha256 <owner-held-sha256> --owner-identity <owner-held-identity>
python integration/l2_ops/s2_quality_cli.py dedupe --review <input-a.json> --review <input-b.json>
```

签名核验直接复用原 `human_gold.verified_owner_rows` / `OwnerTrust`；仍是原 `vrae-human-gold` namespace 与原 Owner attestation purpose。信任锚必须由 Owner 带外配置、位于仓库外，不能取自 review JSON。新模板即使填满姓名/日期，也不产生签名权威。去重只是内容诊断：相同输入只计一次；冲突单元排除，不能最后写入覆盖，更不会自动变 Gold。

## 覆盖与来源真实性

六个离线通用站点夹具覆盖五类：静态、合成 CMS HTML、SPA shell、多 SKU（完整及访问阻断两种）、英/德/中文 HTML 与未捕获语言角色。CMS 只代表保存的 HTML 结构，不声称运行了真实 CMS。SPA 没有浏览器证据时保持 UNKNOWN。

这些夹具实际经过原 Collector → EvidencePack → 原规则执行/独立重放 → FindingPackage。本 P0 明确只评估已验收的 DISC-01、DISC-02、CTA-02 路径规则；不把新十条候选或浏览器布局计作已实现。

九个工业场景实际执行原 C1 diagnose + full verify：工况标量冲突、型号重名、单位换算、PDF 未解析、证书旧/新日期声明、RFQ 缺买方资料、工程适配未知及电机比较不适用。IND 六规则单列，不抵扣通用16条。

每个单元标记 Rule×Site×Source×CaptureTime×ApplicableScope，并绑定 tenant/run/pack、生产者/版本/定位及来源内容哈希。采集时间是合成归档窗口；未访问 URL 没有原生观察，也没有被伪称为已捕获证据。页面角色与分母由夹具预先声明；未选中、未观察、仅元数据、访问受阻与正文已捕获分别呈现。工业角色固定为原八页范围，不是新的生产限额。

报告通过实际原生输入独立重算；改 packet、即使重算外层哈希，也不能替代可信源重放。为控制重复材料，工业 sidecar 保存原始 pack/objects、原生诊断/Guard refs 与完整观察；明确为投影，完整诊断仍由原 C1 全量重放验证，未把投影冒充原诊断序列化。

## 买家能复核的例子

- 已捕获的 CMS Contact 路径返回404：只支持“该链接目标返回404”，不能推导“企业收不到询盘”。
- P40 来源声明10bar、选型场景要求18bar：只支持本情景的标量冲突，工程适配仍 UNKNOWN，需供应商核对工况/曲线。
- PDF 未解析不能说明网站缺规格；证书声明日期不能证明真伪/资质；RFQ 缺目的地不能当作已发送或失败的询盘。
- 多 SKU 阻断场景中，原采集器遇403停止，另一 SKU 保留未观察分母；完整场景另行保存两条真实捕获路径。

实际 `reviewer.md` 按规则/站型呈现上述原生观察、来源和范围，原始哈希与 JSON 可继续核查。

## 统计与结论

合成一致性与人类 Gold 指标分开。输出 TP/FP/FN/TN、precision/recall、弃判、unknown、blocked、适用性与证据覆盖分母，按站型、行业、买家任务、规则版本、来源类型和模型模式分层。UNKNOWN/BLOCKED/NOT_APPLICABLE 不进入 TN，也不被强算成二元 FN。

合成计数只是候选一致性；不能拿其 precision=1.0 宣称真实质量100%或达成90%门槛。原26项仍0/26 pending。没有有效人类 Gold 时，人类指标及严重事实虚构数量为 `null`，状态 `S2_QUALITY_NOT_EVALUABLE`。合法接收到带外 Owner 签名的独立人审也只提供有分母的暂定计算，最终质量 PASS 仍由 Owner 决定。

## 原生验收与后段接口

```powershell
python integration/l2_ops/s2_quality_verify.py --label <new-label> --python311 <native311.exe> --python313 <native313.exe>
```

验收器要求已提交候选，核对冻结原代码/pack blob、真实解释器、旧 Gold 回归、全量工业兼容、新安全反例、实际包导出/独立重放/只读导入，并记录同 SHA 的 JUnit、日志、哈希与耗时。P0 不启动 PG/浏览器，无需另造服务。新增专用 CI 只针对本工具路径，原 CI 不变。

后段仅在 C1/C2 经 Owner 合并后，正常同步 accepted main，接入唯一 `execute/verify_execution(S2)` 及只读 adapter，再做原 PG16/独立 Worker/唯一 SSR 五维真实新任务与重启验收。C1 候选接口见 [Issue118](https://github.com/gloweaseco-leo/VRAE/issues/118#issuecomment-6950561852)；这里只据公开契约准备，没有复制候选源码。缺浏览器字段/未知分母继续明确 UNKNOWN 或受限能力，不把旧 P40 报告充作 S2 全链。

模型调用0；外部网站0；正式人审/ShareGrant/商业E2/E3/生产部署均未授权。普通 P0 成功仅是 `C3_P0_ENGINEERING_READY_GOLD_PENDING`，不是 `S2_ENGINEERING_PASS_GOLD_PENDING` 或 `S2_FULL_QUALITY_PASS`。
