# C2 原生工业生产适配器 v1 / C3 接口

基线：Owner已验收main `11efc13f708a5821c64b96d4a85764447b28ddab`。仅C2报告与审核模块；不是C3 APP202/Worker接线，也不单独声称整机E2E。

## 输入与保证

`vrae.l2.native.NativeTask` 的所有字段由受信服务端独立持有：tenant_id、request_id、run_id、job_id、event_id、source_ref、native_pack_ref、industry_ref、diagnosis_ref、source_bundle_sha256、source_access_mode、created_at。created_at为持久的首次报告创建时间，重启不能重新取当前时间覆盖它。source_access_mode是原C3来源模式三选一，不能从浏览器推断。

在C3原签名低权限Reader当前任务上下文中获取实际Worker的EvidencePack和C1 BuyerDiagnosis，然后构建：

```python
from vrae.l2.native import NativeTask, NativeSource, current_report
source = NativeSource(worker_pack, c1_diagnosis, held=held_native_task)
view = source.read()  # 现有 DeepReport；不是授权对象
```

构造时冻结全部输入，完整验证EvidencePack字节/来源图，并调用已合入C1原生`verify(data, pack, expected_result_ref=held.diagnosis_ref, expected_pack_ref=held.native_pack_ref, expected_industry_ref=held.industry_ref)`。并非schema/inspect_export或客户端自算哈希。构造成功后只复用已经验证的不可变bytes/pack；重启重建Source会重新完整重放。不能把可变诊断dict或可替换对象文件留在校验外面。

新报告合同`vrae.l2.native-deep-result.v1`；生产者保证`vrae.l2.native-producer-guarantee.v1` / `C1_NATIVE_EVIDENCE_GUARD_REPLAYED_C2_BUSINESS_PROJECTION_V1` / `c2-l2-native-1.0.0`。原OfflineSource保证及其validate保持独立且不接受原生任意JSON。source.expected绑定完整服务端任务、pack文档、全部原对象SHA/长度、行业引用及完整诊断SHA。新报告完整字节SHA另绑定采购解释、优先级、蓝图和所有引用。

证据保留所有原pack对象/evidence引用、路径和SHA，以及所有C1 source_facts的原字节片段/引用。`source.object_bytes(blob_ref)`只供持有原签名权威的服务端读取，不是浏览器下载授权。不存在新网络请求、来源授权、任务分配、APP状态或Worker回执。job等字段不能从独立example/export补造。

## 现有SSR与审核

`Ledger(private_sqlite, source, existing_directory)`及原DeepConsole继续使用。原生Source仅支持CONTROLLED目录；逐项审核覆盖全部原生评估和蓝图，不改变原V1 Finding/ReportVersion/ReviewDecision/ShareGrant。原生Finding保留C1原始finding/observation/evidence ID和kind，不用中文展示文案替换原事实。完整display hash覆盖业务解释及蓝图；native ReportVersion content_hash是不同的原生报告哈希。

修订只改蓝图建议并追加版本；原事实、原生保证、任务来源、优先级等不能随修订变动。错版本、撤销、租户及当前身份继续走原账本。受控决定不是正式真人批准，无真实客户外发或生产授权。

## C3 CurrentL2 精确映射

```python
# C3伪代码：original_reader始终保持原签名/任务/期限/撤销/当前版本权威。
with original_reader.current() as task_authority:
    with current_report(c2_ledger, c2_signed_sid, actual_report_id) as c2:
        # 校验c2.pins与原任务全部相同，然后由C3装配已有CurrentL2。
        current = CurrentL2(c2.pins, c2.payload, c2.review, c2.blueprint,
            authority_expires_at=min(task_authority.expires_at, c2.authority_expires_at))
        # original_reader和current_report两个上下文都必须保持到Brief实际COMMIT。
```

`current_report`从实际持久账本读取当前报告与当前决定，不接受客户端receipt DTO；持有原目录锁和SQLite事务直到调用方退出，并再次核对现行签名期限。C3还必须保留原APP/Worker任务权威直到Brief COMMIT。它不修改原授权TTL，也不把review会话当成任务授权。

- `pins`：精确等于C3既有PIN_FIELDS+HASH_FIELDS。report_ref是实际ReportVersion ID，report_version是十进制字符串，report_sha256是完整DeepReport.payload字节SHA（即display_hash）。industry_pack_sha256是原IndustryPack规范字节SHA。payload_sha256是完整原C1 BuyerDiagnosis规范字节SHA，保留C3既有1MB上限。pack/diagnosis引用不是APP或报告回执。
- `payload`：完整、已原生重放的C1 BuyerDiagnosis，保留其tenant/run/pack/diagnosis、19项评估（具体数量随真实输入变化）、source_facts、原Guard、UNKNOWN和采购链，不替换为覆盖preview。
- `review`：receipt_ref是实际保存的decision_id；receipt_sha256是完整持久回执规范bytes SHA；report_version/report_sha256与当前版本完全相同。APPROVE/REJECT/REQUEST_CHANGES只映射为APPROVE_INTERNAL/REJECT_INTERNAL/REVISE_INTERNAL。
- `blueprint`：`l2-native-blueprint-v1`，版本/完整report SHA、原pack/diagnosis引用、原生发现/全部事实引用、页面、改法、资料/责任/依赖/复验与标准候选/定制边界。每项的source_fact_refs是原cf引用，evidence_refs是原ev引用，observation_ids是原obs引用；evidence_ids是本C2证据查看集合的键（包含cf字节片段），不能混称原Evidence对象ID。
- `report_bytes`是实际完整报告原件；`report_content_hash`为原V1 ReportVersion hash，不能替代report_sha256。
- `authority_expires_at`仅是实际C2当前签名审核会话的原期限，C3必须与原任务所有期限取最小值，不是新授权。

DTO构造器、哈希或本模块context都不能替代C3原签名Reader。C3负责唯一SSR实际装配和同一新APP202→Worker→原生诊断→本报告/审核→Brief的E2E；本PR不复制`vrae/l2_ops/**`或APP/Worker实现。

## 业务语义

标量冲突不是网站故障，也不是工程不适配。实际测试数据为两项压力标量冲突，另两条逐型号证明日期比较共用一份资料；不合计成四个网站故障。数量从本次原生数据计算，不写死。日期是来源声明，不是否定真实供应商资质。缺交付目的地是买方待补，不是网站缺陷。保留已有路径，资料组织/技术复核/询价上下文建议必须对应本次引用；没有有据页面问题不附会改站任务。共享证明材料形成一份工作包，逐型号原生评估仍全部保留。NONE/UNKNOWN不变成FAIL；工程、资质、投递及经营结果仍需各自责任人确认。
