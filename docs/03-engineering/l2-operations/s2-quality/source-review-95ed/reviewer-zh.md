# 首批来源候选人工核对包（未审阅）

仅离线合成来源；不是正式报告、人类Gold或权限许可。
已实际运行：离线来源构造、EvidencePack验证、C1受限s2p及独立重放、原字节核对。
未运行：真实Worker任务、浏览器、Controlled审核、Brief和整机P2。
s2p不是原rx或Guard事实。PASS只指受限来源条件；工程适用性、证书真伪与主体资格未验证。
两位真实独立审核人、第三人冲突裁决和Owner签名均由Owner另行安排；所有栏位空白。
原0/26、新旧32单元与本包不合并计分；本包人审0，有效精度/召回率/严重事实虚构均未评估。

## 应用路径能否到达本次采集的产品 / batch1_source
- 来源候选结果：PASS；原因：CAPTURED_APPLICATION_TO_PRODUCT_PATH
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/applications/water / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-e13ba8d69f7ab901efabb3b68a1ef99ab9963ac6019cca5838975492383fe35e，版本 s2-projection-1.1.0
- 包 / 规则版本：ep-881ef64b5e261ea24ec0476b9aebc37269ac2e189e349c4446042c88a65048db / s2-static-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

原文：&lt;a href=&quot;/products/p40&quot;&gt;泵 P40&lt;/a&gt;
定位：https://example.org/applications/water / /pages/1/evidence / bytes 12:47
原内容SHA256：94c6d544a1383809a99acb479505b7d1d9736a6e0b281f67958124842d49e7e4

原文：&lt;html&gt;&lt;body&gt;&lt;p&gt;P40 rated flow 12 m3/h&lt;/p&gt;&lt;a href=&quot;/products/v25&quot;&gt;V25 details&lt;/a&gt;&lt;/body&gt;&lt;/html&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 0:94
原内容SHA256：14a48e058a6486885da4a19b490f938278aa6ef5b3151a710767768e3897d570

## 产品页原文与静态站内链接，不评排名 / batch1_source
- 来源候选结果：PASS；原因：SOURCE_TEXT_AND_HTTP_ANCHOR_PRESENT
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/products/p40 / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-e13ba8d69f7ab901efabb3b68a1ef99ab9963ac6019cca5838975492383fe35e，版本 s2-projection-1.1.0
- 包 / 规则版本：ep-881ef64b5e261ea24ec0476b9aebc37269ac2e189e349c4446042c88a65048db / s2-static-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

原文：P40 rated flow 12 m3/h
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 15:37
原内容SHA256：14a48e058a6486885da4a19b490f938278aa6ef5b3151a710767768e3897d570

原文：&lt;a href=&quot;/products/v25&quot;&gt;V25 details&lt;/a&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 41:80
原内容SHA256：14a48e058a6486885da4a19b490f938278aa6ef5b3151a710767768e3897d570

## 本次记录的 HTTP 响应，不评实时可用性 / batch1_source
- 来源候选结果：PASS；原因：RETAINED_HTTP_200_RESPONSE
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/ / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-e13ba8d69f7ab901efabb3b68a1ef99ab9963ac6019cca5838975492383fe35e，版本 s2-projection-1.1.0
- 包 / 规则版本：ep-881ef64b5e261ea24ec0476b9aebc37269ac2e189e349c4446042c88a65048db / s2-static-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

原文：&lt;html&gt;&lt;body&gt;&lt;a href=&quot;/applications/water&quot;&gt;Water&lt;/a&gt;&lt;/body&gt;&lt;/html&gt;
定位：https://example.org/ / /pages/0/evidence / bytes 0:65
原内容SHA256：ff7a2528958e568b730f97a8cfa46c7eece36a44f166341c9e2aad01295ad8d3

## 应用路径能否到达本次采集的产品 / batch1_no_raw
- 来源候选结果：UNKNOWN；原因：RETAINED_OBSERVED_HTTP_REQUIRED
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/applications/water / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-a613911c2739e1676e09d60f215198b19fd113240aef5d6290db30b4b050a4df，版本 s2-projection-1.1.0
- 包 / 规则版本：ep-f0adb9986b9e0f258a3e674df985fbc240b18a9b77f676150cbad64324a1125c / s2-static-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

缺少可引用原文字节：保持不可评估，不制造ev-ref。
## 产品页原文与静态站内链接，不评排名 / batch1_no_raw
- 来源候选结果：UNKNOWN；原因：RETAINED_OBSERVED_HTTP_REQUIRED
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/applications/water / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-a613911c2739e1676e09d60f215198b19fd113240aef5d6290db30b4b050a4df，版本 s2-projection-1.1.0
- 包 / 规则版本：ep-f0adb9986b9e0f258a3e674df985fbc240b18a9b77f676150cbad64324a1125c / s2-static-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

缺少可引用原文字节：保持不可评估，不制造ev-ref。
## 本次记录的 HTTP 响应，不评实时可用性 / batch1_no_raw
- 来源候选结果：UNKNOWN；原因：RETAINED_OBSERVED_HTTP_REQUIRED
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/applications/water / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-a613911c2739e1676e09d60f215198b19fd113240aef5d6290db30b4b050a4df，版本 s2-projection-1.1.0
- 包 / 规则版本：ep-f0adb9986b9e0f258a3e674df985fbc240b18a9b77f676150cbad64324a1125c / s2-static-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

缺少可引用原文字节：保持不可评估，不制造ev-ref。
## 来源声明的参数、单位、版本与工况 / batch2_source
- 来源候选结果：PASS；原因：CONFIGURED_SOURCE_FIELDS_UNITS_REVISION_CONDITIONS
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/products/p40 / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-99044df110effc53e7e4fd9016b20461afa27156ff03d1f8c9fda17de35189f8，版本 s2-projection-1.2.0
- 包 / 规则版本：ep-9c0f11d3d53b8cd19f668a52878ef58fd73044fba337db9d5742cc3333f961f5 / s2-industrial-context-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

原文：&lt;th&gt;Record type&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 107:127
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;Product&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 127:143
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Product family&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 153:176
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;pump&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 176:189
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Model&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 199:213
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;P40&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 213:225
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Rated flow&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 235:254
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;12 m3/h&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 254:270
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Rated head&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 280:299
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;30 m&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 299:312
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Motor power&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 322:342
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;2.2 kW&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 342:357
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Supply voltage&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 367:390
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;400 V&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 390:404
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Supply frequency&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 414:439
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;50 Hz&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 439:453
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Maximum working pressure&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 463:496
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;10 bar&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 496:511
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Maximum fluid temperature&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 521:555
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;80 degC&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 555:571
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Permitted medium&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 581:606
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;Water&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 606:620
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Data revision&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 630:652
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;R1&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 652:663
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Specification conditions&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 672:705
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;Water at 20 degC; source-listed nominal values&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 705:760
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

## 型号相关证明的展示，不验证真伪或资格 / batch2_source
- 来源候选结果：PASS；原因：SOURCE_PROOF_DISPLAY_CONTEXT_ONLY
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/products/p40 / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-99044df110effc53e7e4fd9016b20461afa27156ff03d1f8c9fda17de35189f8，版本 s2-projection-1.2.0
- 包 / 规则版本：ep-9c0f11d3d53b8cd19f668a52878ef58fd73044fba337db9d5742cc3333f961f5 / s2-industrial-context-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

原文：&lt;th&gt;Model&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 199:213
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;P40&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 213:225
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Product family&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 153:176
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;pump&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 176:189
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Record type&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 107:127
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;td&gt;Product&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 127:143
原内容SHA256：f990867563a7c696e06a0558362cb7a70096cffc9f5a47e9e8c60e628c4aec04

原文：&lt;th&gt;Record type&lt;/th&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 127:147
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;td&gt;Supplier proof&lt;/td&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 147:170
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;th&gt;Applicable models&lt;/th&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 180:206
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;td&gt;P40, V25&lt;/td&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 206:223
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;th&gt;Proof type&lt;/th&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 475:494
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;td&gt;certificate&lt;/td&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 494:514
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;th&gt;Certificate issuer&lt;/th&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 233:260
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;td&gt;Synthetic Fixture Assessment Office - not a real certification body&lt;/td&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 260:336
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;th&gt;Certificate reference&lt;/th&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 346:376
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;td&gt;DEMO-NOT-A-CERT-001&lt;/td&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 376:404
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;th&gt;Certificate valid until&lt;/th&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 414:446
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

原文：&lt;td&gt;2025-12-31&lt;/td&gt;
定位：https://example.org/products/proof / /pages/5/evidence / bytes 446:465
原内容SHA256：690d1fe61ba220d7644fbe8106d64dc9cfd901d909c2356d2dceac8e15c0e13a

## 同一声明标识下的主体与联系原文对照 / batch2_source
- 来源候选结果：PASS；原因：SOURCE_DECLARED_STRINGS_MATCH
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/about / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-99044df110effc53e7e4fd9016b20461afa27156ff03d1f8c9fda17de35189f8，版本 s2-projection-1.2.0
- 包 / 规则版本：ep-9c0f11d3d53b8cd19f668a52878ef58fd73044fba337db9d5742cc3333f961f5 / s2-industrial-context-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

原文：&lt;th&gt;Record type&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 58:78
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;Supplier identity&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 78:104
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Identifier namespace&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 165:194
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;source-declared-registration&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 194:231
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Entity identifier&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 113:139
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;DEMO-001&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 139:156
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Company name&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 240:261
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;Demo Meridian&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 261:283
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Postal address&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 292:315
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;10 Demo Road&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 315:336
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Contact email&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 345:367
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;buyer@example.org&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 367:393
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Contact telephone&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 402:428
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;+1-555-0100&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 428:448
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Record type&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 58:78
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;Supplier identity&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 78:104
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Identifier namespace&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 165:194
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;source-declared-registration&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 194:231
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Entity identifier&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 113:139
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;DEMO-001&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 139:156
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Company name&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 240:261
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;Demo Meridian&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 261:283
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Postal address&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 292:315
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;10 Demo Road&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 315:336
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Contact email&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 345:367
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;buyer@example.org&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 367:393
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Contact telephone&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 402:428
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;+1-555-0100&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 428:448
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

## 同一声明标识下的主体与联系原文对照 / batch2_literal_conflict
- 来源候选结果：UNKNOWN；原因：CITED_LITERAL_CONFLICT_CANDIDATE
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/about / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-c2462cd15baf802542b15f15bd2b3fee2d3b26800c5c9fb65f8559db5a757be8，版本 s2-projection-1.2.0
- 包 / 规则版本：ep-334e462e0b4633c2a0ab3138d99446bd91d47def10de53ab4fb2ac6cc168daa7 / s2-industrial-context-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

原文：&lt;th&gt;Record type&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 58:78
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;Supplier identity&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 78:104
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Identifier namespace&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 165:194
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;source-declared-registration&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 194:231
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Entity identifier&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 113:139
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;DEMO-001&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 139:156
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Company name&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 240:261
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;Demo Meridian&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 261:283
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Postal address&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 292:315
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;10 Demo Road&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 315:336
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Contact email&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 345:367
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;buyer@example.org&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 367:393
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Contact telephone&lt;/th&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 402:428
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;td&gt;+1-555-0100&lt;/td&gt;
定位：https://example.org/about / /pages/3/evidence / bytes 428:448
原内容SHA256：57d267ed8d2def0a4d754f1cd8c7e5fb7163c3c617eab79722f1bc5d081bf2a1

原文：&lt;th&gt;Record type&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 58:78
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;td&gt;Supplier identity&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 78:104
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;th&gt;Identifier namespace&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 165:194
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;td&gt;source-declared-registration&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 194:231
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;th&gt;Entity identifier&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 113:139
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;td&gt;DEMO-001&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 139:156
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;th&gt;Company name&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 240:261
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;td&gt;Demo Meridian&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 261:283
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;th&gt;Postal address&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 292:315
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;td&gt;20 Other Demo Road&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 315:342
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;th&gt;Contact email&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 351:373
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;td&gt;buyer@example.org&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 373:399
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;th&gt;Contact telephone&lt;/th&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 408:434
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

原文：&lt;td&gt;+1-555-0100&lt;/td&gt;
定位：https://example.org/contact / /pages/4/evidence / bytes 434:454
原内容SHA256：ac55dd772a138e933ed3263ff248b8b00ad0d6bfb03274194e169ff8a1818139

## 来源声明的参数、单位、版本与工况 / batch2_unsupported_unit
- 来源候选结果：UNKNOWN；原因：MODEL_OR_CONFIGURED_FIELDS_UNRESOLVED
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/products/p40 / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-6fd0447ee36a92c1d6b22df651b368685d8e0cee3ca94976e7affd6748230285，版本 s2-projection-1.2.0
- 包 / 规则版本：ep-5ef3ab4aa478d3ee95acccbce176a2424b54cebb5c25a8d0e8a67f741bd949c8 / s2-industrial-context-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

原文：&lt;th&gt;Record type&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 107:127
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;Product&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 127:143
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Product family&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 153:176
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;pump&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 176:189
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Model&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 199:213
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;P40&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 213:225
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Rated flow&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 235:254
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;12 m3/h&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 254:270
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Rated head&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 280:299
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;30 m&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 299:312
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Motor power&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 322:342
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;2.2 kW&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 342:357
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Supply voltage&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 367:390
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;400 V&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 390:404
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Supply frequency&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 414:439
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;50 Hz&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 439:453
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Maximum working pressure&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 463:496
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;10 psi&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 496:511
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Maximum fluid temperature&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 521:555
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;80 degC&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 555:571
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Permitted medium&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 581:606
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;Water&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 606:620
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Data revision&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 630:652
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;R1&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 652:663
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;th&gt;Specification conditions&lt;/th&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 672:705
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

原文：&lt;td&gt;Water 20 degC&lt;/td&gt;
定位：https://example.org/products/p40 / /pages/2/evidence / bytes 705:727
原内容SHA256：f46cbe9451864ae77f954d61645a331e9d6855cfc8d3981571c2e4decb3da1f5

## 来源声明的参数、单位、版本与工况 / batch2_no_pins
- 来源候选结果：UNKNOWN；原因：INDEPENDENT_INDUSTRY_PINS_REQUIRED
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/contact / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-e28353104beeb60614413179489b8d4fb2a8dfd1091504c632aa59f75b0c2b5e，版本 s2-projection-1.2.0
- 包 / 规则版本：ep-9c0f11d3d53b8cd19f668a52878ef58fd73044fba337db9d5742cc3333f961f5 / s2-industrial-context-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

缺少可引用原文字节：保持不可评估，不制造ev-ref。
## 型号相关证明的展示，不验证真伪或资格 / batch2_no_pins
- 来源候选结果：UNKNOWN；原因：INDEPENDENT_INDUSTRY_PINS_REQUIRED
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/contact / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-e28353104beeb60614413179489b8d4fb2a8dfd1091504c632aa59f75b0c2b5e，版本 s2-projection-1.2.0
- 包 / 规则版本：ep-9c0f11d3d53b8cd19f668a52878ef58fd73044fba337db9d5742cc3333f961f5 / s2-industrial-context-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

缺少可引用原文字节：保持不可评估，不制造ev-ref。
## 同一声明标识下的主体与联系原文对照 / batch2_no_pins
- 来源候选结果：UNKNOWN；原因：INDEPENDENT_INDUSTRY_PINS_REQUIRED
- 范围：仅本次合成采集与已声明角色；不是全站分母。
- URL / 采集时间：https://example.org/contact / 2026-11-10T12:00:00+00:00
- 来源投影：s2p-e28353104beeb60614413179489b8d4fb2a8dfd1091504c632aa59f75b0c2b5e，版本 s2-projection-1.2.0
- 包 / 规则版本：ep-9c0f11d3d53b8cd19f668a52878ef58fd73044fba337db9d5742cc3333f961f5 / s2-industrial-context-1.0.0
- 核对限制：缺数据不能判网站缺陷；冲突是人工待核，不是法律或资格结论。
- 审核人一：____；日期：____；意见与理由：____
- 审核人二：____；日期：____；意见与理由：____
- 冲突复核：____；Owner签署：____

缺少可引用原文字节：保持不可评估，不制造ev-ref。