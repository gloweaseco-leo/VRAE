# 本地合成 Beta：M1 真实生成与 M3 操作入口

已验收基线：`85f6fe854cc2058672c136b52e4ce35588d9357f`（含已验收 PR104/105）。
本入口只使用已合并代码；M2 动态审核、审核回执与 A4 导出仍待 Owner 合并后接入。

在仓库根目录使用已配置 psycopg、cryptography、pytest 的 Python 3.11/3.13
环境，并启动 Docker Desktop。需要 Node、Chrome 和已验收的本地
`vrae-ra4b-p1:311` / `:313` 运行镜像；PG16 使用既有锁定镜像。

```powershell
python scripts/beta_internal.py app doctor
python scripts/beta_internal.py app start --run synthetic-m3-001 --minor 3.11
python scripts/beta_internal.py app status --run synthetic-m3-001
```

等待 `M1_READY_M2_UI_PENDING`。一次启动会建立独立 PG16、低权限 APP/API、
真实 M1 Worker，以及唯一的既有 SSR。Worker 使用原 claim 顺序与租约，
通过真实 Collector、六规则、Finding、DISC Guard、ReportDraft 与 M1 事务持久化。
输入只取已验收的 404/200 合成来源；RecordedTransport 不请求真实网站。
启动时不会预造新任务或报告。

```powershell
python scripts/beta_internal.py app submit --run synthetic-m3-001 --source 404
python scripts/beta_internal.py app submit --run synthetic-m3-001 --source 200
```

保存各次实际 APP202 返回的 `request_id`、`run_id` 和 `job_id`。
下面以返回的实际 job_id 替换 `<job_id>`：

```powershell
python scripts/beta_internal.py app task --run synthetic-m3-001 --job <job_id>
python scripts/beta_internal.py app report --run synthetic-m3-001 --job <job_id> --wait 90
```

`task` 显示原 API 状态；Worker DONE 本身不代表报告可读取。
`report` 必须经已验收的 SignedGeneratedReader 完成 EdDSA、nonce、当前任务分配、
租户及完整重放校验，才返回实际 locator 和私有 HTML 路径。任务、来源、报告 run_id
与版本必须一致。404 有一个问题；200 无问题，保留完整 17 项事实及原 3/14 编辑选择。
所有输出仍为 `TEST_ONLY_GENERATED_NOT_APPROVED`。

此命令的签名器是本机 TEST_ONLY 操作夹具，不能作为 Web 用户认证接口。
可以在本机浏览器打开返回的私有 HTML 路径检查诊断内容；该文件不是 M2 审核页，
不得据此声称已有人工审核、签名保存、A4 导出或对外分享。
`status` 的 `legacy_ssr_url` 指向既有 sealed 夹具页，与新任务报告无关联。

待队列空闲后可执行实际 PG 重启并再次读取相同两个任务：

```powershell
python scripts/beta_internal.py app restart-pg --run synthetic-m3-001
python scripts/beta_internal.py app report --run synthetic-m3-001 --job <job_id>
python scripts/beta_internal.py app stop --run synthetic-m3-001
python scripts/beta_internal.py app status --run synthetic-m3-001
```

重启不重跑迁移、不重灌报告，重新核对所属容器的 loopback 端口并重启低权限进程。
有待执行/租用任务时拒绝重启。停止后等待 `CLOSED`；`STOP_REQUESTED` 不是清理证据。
每个 run 名称只使用一次；启动中也可停止。自动生命周期上限保持原有范围。

私有凭据、原始日志、报告、浏览器截图与进程观测留在
`integration/beta_review/codex3/.private/`；不要上传整个目录。
没有修改原认证、权限、SQL/RLS、Worker、租约或 HTTP/CDP 门限。
历史 RED、dump 和旧 A1/MAX3 继续保留且不重启。

## M2 接口约束

M2 合并后只接入已验收的 `SignedGeneratedReader` 和真实任务 locator：
`tenant_id / request_id / run_id / job_id / report_id / report_version / source_sha256 /
report_sha256 / html_sha256 / finish_event / authority`。
SSR 必须使用其自身签名会话与当前授权；不得调用本机 `m3_results` 签名夹具来替代
用户认证。SSR 只获得固定 Reviewer 连接，不获得 APP/Worker/admin 凭据。
M1 读取数据库是 `vrae_ra4a_p1`。原 ReportVersion content_hash 与完整 ReportDraft
report_sha256 含义不同，必须保留 `native_report_version` 的原语义，包括 200 中性值。

同一代码 SHA 的完整 L0→L1、审核保存、A4、重启回读验收在 M2 合并后完成；
当前 M1 操作与浏览器诊断验证不冒充整机 FINAL PASS。


## PR105 TaskClient 适配

任务提交与动态状态现在通过已合并的 `TaskClient.create/status`，不再从 C3 重新拼 HTTP。
真实 TaskHandle（tenant/source/request/run/job/event）只保存在服务端；输入引用的
`status.report_version` 不作为生成报告版本。最终版本与 SHA 仍取签名 M1 读取的 locator。

消费侧在现有隔离运行容器内使用 UID10003，只有 `/tmp/m3-consumer/config.json`：
`bearer / tenant_id / source_refs`，目录0700、文件0600。APP、Worker 和管理配置不向它开放。
该 profile 每次原生进程启动重建；不写到 host 的公开目录、日志或浏览器。
API bearer 只是应用服务身份；Reviewer 身份仍独立经受控签名会话与当前分配校验。

UID10002 事件调度器仅启动正式 `python -m vrae.application.ra4b_p2.m1.runtime --config ...`，
不复制 claim/build/commit，不指定 job、不并行运行旧 Worker。原租约、SQL与安全预算不变。
TaskClient 固定127.0.0.1:8765，因此消费进程必须与现有 API 共享 loopback namespace。
当前 Windows legacy SSR 不会获得该 profile，也不假装能够提交新任务。
待 M2 合并后，按其正式 provisioning hook 在该网络条件下启动唯一 M2 SSR，替换旧启动调用。

新增聚焦入口（不重跑已验收 M1 全套或旧 A1）：
`python -m pytest -q integration/beta_review/codex3/taskclient_cases.py`。
需设置唯一 `M3_RUN`、`M3_MINOR=3.11/3.13`，以及既有私有证据环境。
覆盖无数据库配置的身份、实际 PENDING→DONE、错误任务/来源及幂等冲突拒绝、
正式 Worker CLI 实际提交，以及重启后重新配置身份并读取相同任务原字节。
