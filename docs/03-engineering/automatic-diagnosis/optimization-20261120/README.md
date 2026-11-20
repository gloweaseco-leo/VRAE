# PR176 真实失败后的最小修复

本轮修复采集预算内的重复授权开销、合法 head 标签解析及失败结果表达。
保留原五维任务、最多四页、24秒任务/8秒请求、robots、SSRF、同源/动作路径、隔离及费用控制。
没有部署、重采客户网站、付费模型调用、修改 VF 或操作共享模型账本。
这是修复与离线验证，不是新一轮真实业务验收。

## 采集预算与页面选择

原 `inventory` 对每条 href 调用 `CurrentAccess.check`，每次执行当前 PG 来源读取、签名验证及两次 policy 读取。
同一份含154条有效产品链接和4条拒绝链接的签名测试页面，原路径158次当前授权检查、470次 PG 读取；
修复后2次当前授权检查、7次 PG 读取，候选清单逐项相同。
该计数对照证明重复查询的放大，不宣称已经分解原真实任务24秒的全部耗时。

新 `inventory_scope` 仅在同步、无网络的候选解析中使用本地 policy 副本，并在批次前后检查原当前授权。
撤权、签名密钥撤销、到期、包络变化会使整个批次失败。所有实际请求、重定向、DNS重绑定与连接前检查维持原路径。
精确路径授权继续逐条检查。没有跨网络等待的授权缓存。

现有选页已优先覆盖未覆盖的角色；不改顺序或128个规则解析 anchor 的上限。
PG 串联用例增加两页154链接目录，在原生产24秒/四页/1秒间隔限额下采集首页、目录、产品、联系页，
并由产品正文形成原 INFO-01 Guard 事实。网站和模型在该用例中均为明确的测试替身。

采集日志增加不含网址/正文的 `FETCH_WITH_FENCES`、`LOCAL_INVENTORY` 耗时，Worker 汇总当前 PG 授权读取次数和时间。
这些统计有包含关系，不应将授权时间与采集阶段时间相加当成总耗时。

## 新旧解析与历史保留

新增明确选择的补丁链：`l2-industrial-1.0.1` → `ra2b6-1.0.1` → `ra2c3-1.0.1`。
仅新 authorized-target 工件默认选择补丁；旧工件按自身记录的诊断版本重放。
旧 API 默认及旧生产版本仍保留，未知版本、交叉版本配对和版本换标拒绝。

补丁仅修正合法 `<meta .../>`、`<link .../>` 被 HTMLParser 合成结束回调后误判的问题。
缺失 canonical、跨站 canonical、重复属性、重复标签、显式错误结束标签、base 和不支持的结构仍保持 UNKNOWN。
Guard 的事实类别、引用核对、模型输入限制和候选审核标准不变；只增加严格匹配的补丁版本对。

原历史金样及 `preserved-history.json` 的哈希不改。
三个新增补丁分支的源码，其原始 Git 字节保存在 `tests/interpretation/fixtures/accepted-source/<原SHA256>.py`，
历史验证明确校验这些原源码快照，并继续重放当前旧版本路径的原工件、FindingPackage 与 Guard 金样。
新增差分用例直接加载原源码，对照旧执行结果、head信号及 FindingPackage；不是宣称当前源码文件字节没有变化。

[真实保留工件回放](retained-replay.json) 证明21份原工件均可原版本重放。
原失败工件的首页解析问题从 `UNSUPPORTED_HEAD_END` 变成空，title/description 恢复为 OBSERVED；
canonical 仍缺失、产品正文仍未采集，所以旧证据的合格模型事实仍为0。
不改写旧报告或旧回执，也不把这个回放标记为 AI 成功。

## 模型状态及 VF 消费

现有结果接口和外层 `state` 保持兼容，增加以下字段；完整字段说明同步在现有 OpenAPI：

| 字段 | 含义 |
| --- | --- |
| `capture_summary.candidate_urls` | 已发现候选网址，包含未访问候选 |
| `page_records` / `fetched_pages` | 页面记录数 / 成功采集页数；记录不保证已派发 HTTP |
| `unvisited_candidates` | 尚无页面记录的候选数，不计网站缺陷 |
| `http_requests_including_robots` | 原请求预算计数，包含 robots，不能作为网页成功数 |
| `timeout_page_records` | TIMEOUT 页面记录数，不能据此声称远端响应超时 |
| `analysis_outcome` | PENDING、NOT_RUN、COMPLETED、INSUFFICIENT_EVIDENCE、NOT_DISPATCHED、PROVIDER_FAILED、VALIDATION_REJECTED、UNAVAILABLE |
| `model.failure_stage` | INPUT、CONTEXT、PREFLIGHT、PROVIDER、VALIDATION、CURRENT_AUTHORITY、ACCOUNTING 等后台安全阶段码 |
| `model.provider_attempts` / `cost_status` | 原操作派发及费用状态；旧未知字段继续未知 |

空证据目录使用 `INSUFFICIENT_GUARDED_EVIDENCE`，超量目录仍使用 `LOCAL_CATALOG_BOUND`。
有模型配置的前置失败，先只读检查同一持久账本中的原操作；确认无预留/派发才报告0次和未发生费用。
同一操作曾调用、已产生用量或账本不可用时，不抹除用量或把未知费用变成零。
供应商失败、输出校验拒绝、当前授权丢失、费用账本异常分别记录；不自动重试。

只有原真实供应商用量、REAL_PROVIDER、Guard候选和工件绑定全部成立，仍才可返回 `DIAGNOSED`。
协议替身不产生客户 AI 结论。VF 可用新增字段解释覆盖不足和处理状态；客户仍只提交网址并勾选一次授权。

## 验证与剩余验收

复现完整隔离回归：`python -B scripts/verify_automatic_diagnosis.py`。
脚本只创建唯一标签测试资源，不挂载运行服务、私有输入或共享模型账本；完整测试统计见本目录验证记录。
必要时可用 `--checks history types lint` 复查历史版本、类型和 lint。

尚未证明修复后对原真实站点的新采集可以产生足够事实并完成 Qwen。
原两页字节无法补出未采集的产品正文；需要 Owner 另行批准新任务复验。
若新证据仍不足，应依据新阶段日志判断采集和证据适配原因，不放宽 Guard 或将 UNKNOWN 改成网站缺陷。
