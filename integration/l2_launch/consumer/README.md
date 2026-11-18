# G1-C2：实际HTTP消费者客户端

Owner [#155](https://github.com/gloweaseco-leo/VRAE/issues/155)，统一G1 [#153](https://github.com/gloweaseco-leo/VRAE/issues/153)。基线 `7fdeeed0f427ce3b94677ab2a480eae1556e85ca`。**G1_HTTP_PENDING**：本分支没有服务端、数据库、Worker或mock运行入口，不启动C3/UAT资源。C3为唯一服务实现者；原 `contracts/l2_launch/**`、39例、原V1、Guard全部保持不变。

`client.py` 使用标准库HTTPConnection向C3明确提供的 `http://127.0.0.1:<owned-port>` 发实际请求。没有默认端口、DNS、代理、重定向跟随或公网回退；拒绝非loopback连接和真实目标网址输入。固定服务凭据仅从服务端环境读取，不使用原APP bearer，也不输出给浏览器。`--manifest` 缺失时不发请求，逐项BLOCKED并退出2；任何缺失断言/证据不会当PASS。

## 运行

在仓库根目录，使用原 `requirements-ra4b-p1.lock` 环境，无新增依赖：

```powershell
New-Item -ItemType Directory -Force integration/l2_launch/consumer/.runtime | Out-Null
python -X utf8 -m pytest -q tests/l2_launch_http/consumer_cases.py tests/l2_launch/consumer_cases.py --basetemp=integration/l2_launch/consumer/.runtime/pytest-311 --junitxml=integration/l2_launch/consumer/.runtime/selftest-311.xml
python -X utf8 -m integration.l2_launch.consumer.client --output integration/l2_launch/consumer/.runtime/http-pending.json
```

第二条CLI在C3尚未交付时**预期退出2**，输出 `G1_HTTP_PENDING` 和23个BLOCKED；不能给它套成功退出或把自测JUnit签作真实HTTP验收。输出文件采用独占创建，保留旧RED，不覆盖旧记录。3.13用相同命令与独立basetemp/JUnit。

实际C3服务到达后，仅在其提供owned资源/权限的前提下运行：

```powershell
# 凭据由C3的私有运行环境注入，不在命令、JSON或文档中粘贴。
python -X utf8 -m integration.l2_launch.consumer.client --manifest <C3私有manifest.json> --output integration/l2_launch/consumer/.runtime/http-<C3精确SHA>-<本次编号>.json
```

退出码：0=本客户端全部HTTP合同断言通过但仍待Owner；1=存在FAIL；2=至少一项BLOCKED。永不输出Owner唯一G1综合PASS结论。C3尚未提供服务时无实际HTTP消费日志，只有明确的pending记录。

## C3提供的私有运行输入（客户端配置，非新业务合同）

manifest必需键：`scope="C3_OWNED_OFFLINE_SYNTHETIC_G1"`、`server_sha`（40位精确SHA）、`owned_run_id`、`base_url`（唯一授权端口）、`profile="vf-vrae-r0.1-vfb.1"`、`bindings`。`source_header`默认 `X-VRAE-Source-SHA`，可指定C3已有的等价响应头名；每次HTTP响应必须与manifest SHA相符，否则BLOCKED/FAIL。该头加C3运行记录是来源关联，不是独立二进制远程证明。

`bindings`按 `client.RULES` 的23个固定case ID配置。每项为 `{method,path,body,credential,cookie,headers}`：

- path为C3实际相对路径，不由C2假设新路由。原六资源的路径语义不变；return/session/test-fixture控制路径由C3提供。body是该场景完整的私有合成JSON。
- credential只允许 `service`、`wrong_tenant`、`owner_fixture`、`none`、`invalid`。分别使用 `G1_C2_SERVICE_TOKEN` / `G1_C2_OTHER_TENANT_TOKEN` / `G1_C2_OWNER_FIXTURE_TOKEN`；return凭证为 `G1_C2_RETURN_TOKEN`。所有值由C3固定服务端注入，禁止填原APP bearer或客户信息。
- body/path/header中 `${audit_ref}`、`${run_id}`来自实际202，`${csrf}`来自实际exchange响应头，`${return_token}`来自私有环境。只保存在进程内，不写cookie/凭据状态文件。`cookie="none"`用于裸ref负例，其余默认只回送本连接流程已验证的私有会话。
- headers只允许Accept、Content-Type、Origin、X-CSRF-Token。默认严格profile媒体类型见[接线表](../../../docs/03-engineering/l2-launch-g1-c2/VF-B-WIRING.md)。故意缺省、错媒体类型、CSRF缺失/无效要由binding明确表达；客户端先检查负例前提，防止用错身份制造无意义403。
- 创建、重复、断线重试、重启后请求使用同一个合法VFSubmit与同key，变体只在保持同key时改变有效意图。只断开读取ACK一次，再发原请求；不做隐式POST重试或自动换key。
- `create/after_restart` 的 `pg_receipt={path,sha256}` 指向C3独立验收工具生成的原始PG提交/回读JSON。必需同server_sha/owned_run_id/audit_ref/run_id、committed=true、job_count=1；after_restart还需server_restarted/pg_restarted=true。没有证据，202也只BLOCKED。**这是C3提供的证据关联，不是C2独立连PG验证。Owner仍须核对原始事务/重启记录。**
- `preview` 的 `original_bundle={path,sha256}` 是C3这条实际新任务的原ReportVersion/Findings/当前版号/源命令/基础获准投影；另给 `view_sha256`（冻结canonical JSON digest）。不能用G0旧示例冒充新任务。客户端检查同run/原提交、原fact/content hash/current version，复用原 `validate_free_view` 检查多事实/反证/分母/引用，精确view hash含译文。
- `expired_session/withdrawn_session`还需 `access_receipt={path,sha256}`，含同server_sha/owned_run_id/audit_ref、state=EXPIRED或WITHDRAWN、当前会话Cookie的session_sha256及先前客户端实际200的baseline_response_sha256；没有先前允许的同会话/同资源响应或状态转换证据，该拒绝不能算通过。`stale_report`需针对C3提供的旧版/过时grant场景真实拒绝403或409，不改原ErrorCode。
- C3负责在对应真实阶段提供各binding及准备/过期/撤回/重启证据。不同阶段可输出独立manifest/结果，未提供的case继续BLOCKED；不得合并不同任务的绿项声称同任务通过，也不得为了凑齐报告伪造阶段。若需要新的fixture控制请求或原始证据字段映射，按C3首个Draft精确SHA做最小客户端兼容，而非修改后端或冻结合同。

## 证据与边界

结果只保留case ID、PASS/FAIL/BLOCKED、固定断言ID、HTTP状态、响应原始字节SHA256与结构脱敏后的请求/响应。所有字符串值及未知字段名均掩码；URL、原文、联系人、Authorization、Set-Cookie、CSRF和return材料不进入普通日志。失败可按case+私有manifest+source SHA定位精确请求，原件仍由C3在其owned私有证据目录保管，不上传令牌或原件正文。

Python服务端模拟客户端显式回送Cookie仅验证真实HTTP服务端会话/CSRF拒绝及Set-Cookie属性；**不模拟浏览器的Secure-cookie存储行为**，不能代签Chrome/公众页面验收。PG/Worker/Collector/无外网/清理、真人Gold、真实ShareGrant/VF收据、付费模型与云部署均不是本客户端的PASS权威。

`tests/l2_launch_http/consumer_cases.py` 是显式运行的HARNESS_SELFTEST_ONLY，fake connections不打开端口，socket/DNS被禁止。首轮自测临时目录父目录遗漏为29 PASS/8 setup ERROR，原XML保留在忽略的 `.runtime/development-red-311.xml`；补目录后复验，不抹去RED。未新增或更改旧工作流，不触Owner UAT。
