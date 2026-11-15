# M1 服务端消费契约

入口为 Owner 已验收 main `08a999d8b7061af925f1f35cfcc55193a3c73b35`。
M1 FINAL PASS 直接复用。本补丁只提供 M2/M3 可复用的 HTTP 调用与任务关联适配；
不替代 Codex2 的单一 SSR、逐 Claim 审核/回执或 Codex3 的启动器。

```python
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient

client = TaskClient(AppEndpoint(
    bearer=private_api_bearer,
    tenant_id="tenant-test",
    source_refs=frozenset({"accepted-404", "accepted-200"}),
))
task = client.create("accepted-404", idempotency_key=server_held_key)
state = client.status(task)
result = client.read(task, signed_generated_reader, signed_bearer,
                     nonce=server_held_nonce)
```

`AppEndpoint` 只接受 API bearer、租户、固定来源白名单；没有 DB host/user/password/config。
受控启动器单独向 SSR 私有进程交付该配置，浏览器不持有 API bearer。
APP 自身继续独占原数据库配置，HTTP 固定为 `127.0.0.1:8765`；客户端不接受 URL/重定向。
API bearer 是应用服务身份，不是 Reviewer 身份。SSR 自身还需沿用受控签名会话与 CSRF 边界。

`create` 调用原 APP POST，仅在真实 COMMIT 后的 HTTP202 返回 request/run/job/event。
调用方在服务端保存 TaskHandle 及来源关联；重复相同 key/source 返回同一回执，冲突拒绝。
`status` 通过原 GET 读取，逐项检查 request/run/job/source_ref；错误映射拒绝。
`TEST_ONLY_DONE` 只是读取前提，不足以证明存在新报告。

`read` 通过原 M1 SignedGeneratedReader，核对返回 locator 的 tenant/request/run/job。
服务端通过受控路由建立 JobAssignment(issuer,subject,Reviewer role,tenant,job,expiry)，
并提供真实低权限 Reviewer 连接工厂、TrustAnchor 和 nonce；请求不提供 DB 身份。
JobAssignment 和 TaskHandle 都不授予数据库权限，M1 仍要求 Worker 提交时生成的当前分配、
当前来源授权、epoch 和报告关联。尚未生成、未分配或已撤权时保持拒绝。
签名令牌一次性使用，成功读取后需新的挑战/令牌，不能缓存旧报告代替当前授权读取。

结果版本和 SHA 取自 `result.locator`；`status.report_version` 是输入引用元数据，
不能当生成报告版本。`report_sha256` 是整份报告字节 SHA，和原生报告 `content_hash` 不同。
source/report/html、三个 SHA、原生 finish_event 和展示遗漏说明沿用 [M1](M1.md)。
返回仍为 NOT_APPROVED/不可分享；读取成功不证明 B3 写入/审核回执已适配。
不得把新报告冒充旧 sealed fixture 图。如 M2 的原持久回执要求受保护写入，
由 Codex2 报告该精确依赖供 Owner 裁决，其余 UI/读取集成继续。

Worker 必须使用 `python -m vrae.application.ra4b_p2.m1.runtime --config <private-worker-config>`；
同一 M1 lane 不并行运行旧 Worker。只安装 M1 的 `db/ra4b_p2/m1/001_runtime.sql`，
不 glob 历史提案。没有迁移、旧权限、Guard、领域契约或真实网站变更。

聚焦验证命令：

```text
python -m integration.ra4b_p2.m1.consumer_lab 311 <unique-label>
python -m integration.ra4b_p2.m1.consumer_lab 313 <unique-label>
python -m integration.ra4b_p2.m1.consumer_publish <unique-label>
```

只执行两个新增消费用例（404/200），复用原隔离 PG16/API/独立低权限 Worker 配置，
不执行 M1 验收测试或重启验收。每例包含真实 HTTP202、PENDING/DONE、签名读取、
字节哈希/版本、幂等、错误 job/source 映射、令牌重放与 peer 拒绝。
原始 XML、源码 SHA 清单和四个自有资源清理回执保留；公开前扫描私有凭据和 JWT。
本结果仅代表后端消费端口可用，M2/M3 浏览器整机闭环仍由各自 Owner 合并后验收。
