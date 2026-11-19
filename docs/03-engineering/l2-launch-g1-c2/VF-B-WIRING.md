# VF-B一页接线表：G1-C2（给VEYFRONT PR36 Agent）

Owner [#155](https://github.com/gloweaseco-leo/VRAE/issues/155)。G0语义 `vf-vrae-r0.1-vfb.1` 已冻结，原V1六资源仍是语义权威；**当前G1_HTTP_PENDING**，无C3实际服务验收、无VF生产接线或客户报告授权。本轮VEYFRONT只读，不改PR36页面/框架/源码，不访问私有预览。VF-A单槽/READY/synthetic演示不构成真实诊断权威。

| 场景 / JSON | 服务端请求与验收 | VF可展示 / 不得展示 |
| --- | --- | --- |
| 内容协商 | 建议 `Accept: application/vnd.vrae.launch+json; profile="vf-vrae-r0.1-vfb.1"`；POST同Content-Type。C3实际接线须严格profile，未知406、错Content-Type415，无静默降级。原application/json仍原V1验证。服务身份只在受控VF后端，浏览器无原APP bearer。 | 不显示服务凭据、签名材料、原内ID或请求原件。具体HTTP媒体兼容待C3精确实现验证，不改已冻结语义。 |
| 提交 → 202：`vfb-submit` / `vfb-accepted-202` | 服务端验证邀请/逐目标许可与范围；诊断同意version/hash/accepted_at独立签名绑定。仅PG/outbox commit后202，稳定opaque audit_ref；同key同意图同ref，变体409，断线原意图重试，不造第二job。 | 显示“已接收”、实际初态与轮询间隔。run_id仅服务端关联；不能宣称采集完成、全站扫描或转化损失。公开任意URL仍关闭。 |
| 任务：`vfb-unpublished-status` / `vfb-draft-ready-not-completed` | 实际GET保留task/publication/access三个轴；原14枚举不改。DRAFT_READY/REVIEW_REQUIRED且UNPUBLISHED不得completed；partial须当前获准的真实部分投影。 | 实际阶段、限制、安全原因；进度百分比null。断线unavailable且保留咨询退路，不用sleep制造进度。 |
| 返回/读取：`vfb-server-only-return-grant` / `vfb-unpublished-report-denied` | audit_ref不是Bearer。受控一次性交换→HttpOnly/Secure/SameSite私有会话、CSRF；每次task/report/citation核tenant/源范围/当前review/version/view hash/grant/expiry/revocation。无权限统一403/no-store，无存在性泄漏。 | 失效/撤回关闭结果；提示重新获得受控访问。cookie、CSRF、报告grant不放URL、普通日志或通用分析。不能以撤销访问声称物理删除已下载副本。 |
| 受限报告：`vfb-five-task-multiple-facts` | 实际新任务原facts/current report+view hash和原许可对应。五维数组保留观察/反证/假设/建议/UNKNOWN，来源定位/时间，实际authorized/attempted/successful/unknown页分母，最多3个有据priority。事实、译文、版号变化必须重批。 | 有界获准投影；synthetic-only只在受控fixture验收中标明合成。不能压回每维一槽、补判AI候选为ISSUE、展示EvidencePack/模型/浏览器原文或静态假实时。全站分母未知。完整L2需另有人审/ShareGrant，当前真实发行关闭。 |
| 错误：`vfb-safe-error-403/409/429/503` | 403停止私有读取；409核对原意图/版号，不自动换key；429遵守服务端retry_after_seconds/Retry-After；503仅显式retryable才有界退避。响应均no-store。 | 安全错误与咨询退路。NOT_AVAILABLE不因时间经过变为开放；UNKNOWN不当0，不推断网站缺陷。 |
| 咨询：`vfb-independent-inquiry-consent` / `vfb-inquiry-waiting-ack` | 客户主动咨询且当前访问有效，独立咨询同意，最少opaque关联进入VF原私有lead主权；无真实VF存储签名receipt保持WAITING_ACK。已有lead 201不等同VRAE可核验receipt；诊断点击不创建lead。 | “咨询待确认/已由VF保存”仅在对应事实成立时陈述。合成ACK、邮件、点击不等同真实线索、E2/E3、报价或客户批准；不把Handoff内部原件直接转给浏览器。 |

上述场景JSON均复用 [G0原39例](../../../contracts/l2_launch/examples/)，**仅用于字段说明，不能作为C3实际任务或真人批准证据**。可执行客户端、23项断言、私有manifest与双Python命令见 [consumer README](../../../integration/l2_launch/consumer/README.md)。客户端无服务端、无CRM、无后台任务实现；PG证据由C3提供并待Owner独立核验。

交接待处理：C3首个G1 Draft精确SHA、owned loopback地址/生命周期、实际路由/服务身份与response source header、受控交换/CSRF返回方式、同任务PG/原facts/view/restart证据、逐阶段bindings。C2随后对其actual HTTP回归，提交逐项脱敏FAIL及精确断言，后端由C3修正；当前不得报G1通过。真实网络/客户/真人Gold/正式ShareGrant/付费Provider/云部署全部另需Owner GO。
