# 给VEYFRONT Agent的最小交接（G0待审）

Owner补充的VF PR36 / VF-B六项行为，逐项对应[一页consumer compatibility matrix](VF-B-COMPATIBILITY.md)。客户接口优先消费其中的独立VF-B envelope；本页原字段表是基础内部合同，不可直接暴露完整AuditRun/内部tenant/audit_id，也不能把旧单槽results强行填入多事实数据。双方候选并存，需Owner冻结版本。

只读核查：[当前leads源码](https://github.com/gloweaseco-leo/VEYFRONT/blob/348ba4a6a9e885431e769e008dd4b7c157405104/app/api/leads/route.ts)。UTF-8源码SHA256 `31aa3ff9cd016e1019e39b1ceb2c6e33649fe3bef4bdb1e4e4a785ac47cfa2d7`。本PR未写VF仓库、未请求该API、未触发Blob或邮件。

## 最小字段/信任方向

| 方向 | 最小输入/输出 | 谁提供权威 |
| --- | --- | --- |
| VF → VRAE提交 | 原AuditRequest全部必填字段，signed permission ref、consent版本/hash；header Idempotency-Key与body相同 | tenant由BFF服务身份绑定；audit_id/request_id/source_reference一次生成并保存；许可机构而非浏览器签名 |
| VRAE → VF接收 | 原Accepted.CREATED子对象、同audit_id、run_id、durably_recorded、queue_state、diagnosis_complete=false | 实际任务与outbox提交；不以201咨询回执代替202任务接收 |
| VRAE → VF状态 | 原AuditRun、展示状态、progress_percent=null、当前access_state | 原真实服务阶段；没有实时服务时只NOT_AVAILABLE |
| VRAE → VF结果 | PublicPreviewView或ApprovedL2ReportView、A/B中英、source/citation与UNKNOWN/分母 | 当前授权/版号、真实ReviewDecision、Owner批准的投影与grant |
| VF → VRAE咨询关联 | opaque咨询/同意ref、tenant/audit/current report version、持久幂等意图 | 联系资料仍在VF，VRAE不保存姓名/邮件/电话号码/需求正文 |
| VF → VRAE存储收据 | event_id、tenant/audit/handoff/report_version、request_sha256、opaque vf_receipt_ref、storage_receipt_sha256、stored_at、STORED及受信签名 | VF post-commit/readback适配器；签名key不能来自浏览器 |
| VF人员 → VRAE资格确认 | 独立event、询盘证据ref、人员ref、confirmed_at和独立确认签名 | 真正商业人员，不是VF自动接单服务 |

服务凭据、请求持有者/recipient token与签名key分离。所有关键字段跨tenant/run/audit/版号不一致都拒绝；当前grant和current-version读取必须是受信server-side resolver，不能让浏览器提供latest_version或授权布尔值。

## 必要交互信息（不规定页面/框架）

- 提交前：说明邀请/授权范围、未扫描全站、许可与隐私文本版本、当前服务可用性；未获准时禁发扫描请求。网址输入并非站点控制验证。
- 202后：显示持久引用与实际阶段，接收不等于完成；队列待派发不能显示已开始采证。轮询按服务端限流/Retry-After、有界退避，不能高频盲重试。
- DRAFT/REVIEW_REQUIRED：显示审核待办，不能有客户下载入口。仅PublicPreviewView名字不代表允许匿名；当前只能指定获准收方。
- UNKNOWN/BLOCKED：说明“缺少观察/访问受限”，不写“网站缺陷”“询盘损失”或虚构覆盖率；未测提交/送达/转化保持UNKNOWN。
- 重复点击：复用同一请求envelope和幂等key；同key不同body409需核对，不能自动换key制造第二任务。
- 403：停止读私有对象并引导重新认证/向Owner核对授权；不能轮询刷403。409：旧版/冲突需取得当前允许引用，不能自动覆盖。429：遵守retry_after_seconds。503/NOT_AVAILABLE：保留真实状态，不构造静态报告冒充实时。
- 只有availability允许且明确retryable=true的依赖失败才有界重试。G0未获准的NOT_AVAILABLE不因时间经过自动开放，也不发扫描重试；503存储失败示例与此配置关闭状态不同。
- 撤回：立即关闭结果与下载；旧token/缓存/迟到回执不得恢复。删除与邮件退订流程不同，须分开呈现事实。
- 主动咨询：可以进入VF已有咨询流程；保存成功201只陈述“咨询已保存”。没有签名storage receipt时VRAE仍WAITING_ACK，不声称对方已联系、客户批准或E2/E3。

## 当前VF与候选的具体缺口

现有leads POST只接受first-party浏览器同源，GET405，保存私有JSON成功才201；没有供VRAE回读的受信签名receipt、跨仓幂等key、可靠重放或人工资格确认端口。不得从VRAE伪造Origin调用它作为“服务集成”；不得拿邮件成功、跳转URL、用户点击或任意 `{ok:true,reference}` 作为ACK。

需要VF Agent提出**服务侧**持久幂等、存储后签名、最小receipt回读/回调与人工确认适配；Owner决定身份、接口、地区/留存和G0版本。存储已成功但确认消息丢失时，VRAE保留WAITING_ACK，同意图去VF对账并取同一receipt，不能盲目二次创建lead。相同event重放幂等，不同body冲突；撤回后的event明确拒绝。

另核对同commit的 [lib/url.ts](https://github.com/gloweaseco-leo/VEYFRONT/blob/348ba4a6a9e885431e769e008dd4b7c157405104/lib/url.ts)：它可为缺scheme的输入补https，没有显式拒绝query/fragment、百分号路径或URL凭据；返回normalized时不保留query/fragment/凭据，但leads route并不使用normalized来保存website。该行为适用于咨询网址校验，不是扫描许可。VRAE原syntax_host/canonical_url更严格；独立扫描目标必须按原规则确认并签许可，不能复制私有lead原网址或静默删query后改变用户授权目标。500字VF咨询字段与2048字V1 URL上限的差异也不要求修改VF页面。

双方差异统一汇总[ADR待裁决表](ADR-001.md)，不在任何一方网页/后端暗改对方约定。R0仅候选；待Owner G0冻结后才能按最终接口实际合并集成。
