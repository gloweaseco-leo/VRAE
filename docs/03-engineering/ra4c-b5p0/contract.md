# B5-P0 接线契约

## 身份与当前权限

1. B2 验证实际 Ed25519 TEST_ONLY JWT、issuer/audience、nonce、有效期；B5A 发 opaque session cookie。JWT 不进入 DOM、localStorage 或证据包。
2. 可信 provisioning 为同一 issuer、合成 subject、实际 Reviewer DB role 和完整 Locator 建立 B5A assignment 与独立 B3 witness。B3 subject 明确定义为 `TEST_ONLY_` 加上述四项规范字节的 SHA-256；不把自然人或客户端字段提升为主体。审计只导出 mapping 指纹，不导出 witness capability。
3. 私有 bridge profile 持有精确 task→mapping→witness 链接。B5A profile 或 bridge 任一字节改变或不可用，全部现有 session、challenge、action 立即失效，重启并重新签名登录后才能继续。服务器不通过 HTTP 接受可信配置。
4. 每次预览、保存和读取回执都重新验证当前 session、anchor、assignment、角色及 Locator。B3 lookup 必须真实返回原生 `P0002` 才可将“缺少 probe key”解释为有效 witness；单独的 `UNKNOWN_COMMIT` 不能证明权限或数据库可用。B3 原有 SQL 同时校验实际 role、tenant、Locator、epoch、anchor 和 witness expiry。
5. 事务持有实际 psycopg 连接。B3 candidate 返回时，在驱动真正 COMMIT 之前再次核对实际 receipt 的 subject/role/target；候选不匹配会抛异常并实际回滚。B5A 当前身份在同一个受控 COMMIT 入口重查，B3 deferrable SQL 检查继续有效。只使用低权限 Reviewer，无 SET ROLE、APP/superuser 或业务表原始读写。

私有 provisioning 是可信控制面；运行时不能直接读取 B3 witness 表。不存在把 missing-key 响应解析为 witness subject 的虚构接口。subject 的独立来源是 provisioning 的确定性绑定，而真实写入返回的 subject 在 COMMIT 前与其比较。

已验收的 witness 行本身不可变。开发负例尝试 UPDATE expiry 时，原有 `immutable()` 保护实际返回 `55000 / RA4A_IMMUTABLE_METADATA`；没有关闭 trigger 或放宽 grants。正式过期用例通过 provisioning INSERT 一个已经过期、其余绑定精确一致的独立 witness，再验证预览与保存都被拒绝。这一开发 RED 和修正后的原生结果均保留。

## 原始数据与 proposal

B5A 原有 `ReviewerReader` 经真实 `load_target` 取得 SQL 原始 TARGET/manifest/DRAFT/HTML/SOURCE/Guard 等字节，逐对象检查 digest、length 和可信 descriptor pins，再使用已验收 NativeVerifier 与 ReviewTargetBridge。新适配器从这份 request snapshot 构造 B3 ByteGraph，不调用 fixture 重生成或 fallback。manifest 仅按 B5A 已证明相等的 canonical descriptors 还原，并再次比对 pin。

表单只接受原有 proposal 的本地候选判断、原因、逐 Claim disposition、完整 section ACK 和原有 guard pins，再加服务端生成的 `_ticket`/`_csrf`。role、DSN、issuer、subject、epoch、witness、idempotency key 等附加字段均拒绝。B5A `preview.validate` 先校验同一份 snapshot。随后释放 B5A reader 事务，避免其 tenant lock 与 B3 独立连接自锁；B3 在自己的事务中再次从 PG 读取和验证全部原始字节。

## 一次点击、并发和恢复

ticket 绑定 sid 摘要、session generation、mapping scope、CSRF 摘要、expiry；首次 POST 消耗 B5A 原有一次性 action nonce，并检查 Origin/Host。服务端 key 是 scope、generation、ticket、规范 proposal 摘要的 HMAC；浏览器不提供 key。相同 ticket 的相同 body 可在当前身份验证后读取原结果，修改 body 则冲突。实际 CAS 和 intent/Claims/sections/audit/outbox 原子性由已验收 B3 SQL 提供。

SQLite 只保存私有恢复元数据：原始规范 command/key、scope、generation 和已核实 receipt 摘要。发送 SQL 前持久保存原 key。它不存业务 intent，也不替代 PG。已有 attempt 无论是否收到响应，都只能使用原 key 做新授权查询，不能重发新 key。进程重启后旧 session 不再有效，需重新签名登录；查询未找到或不可确认时保持 `B5P0_UNKNOWN_COMMIT`，不会把网络失败报告为成功。

返回回执先由已验收 Receipt 校验，再检查 subject/actor/target、原始 SOURCE/HTML/manifest 哈希、规范 command digest、原始 key 与既有 receipt hash。页面只显示脱敏投影、稳定原始 receipt SHA 和 mapping 指纹。HTTP 错误使用固定代码，不反射原始 SQL、凭据、cookie、JWT 或表单字节。

真实物理 COMMIT 仍可能跨越时钟有效期。适配器校验受控 COMMIT 入口，B3 在 COMMIT 后再开启事务验证权限，页面显示前再次检查当前身份；任何无法确认的响应不能被描述为“已批准”或承诺回滚，恢复时查询持久 PG 真相。

## 已实现与禁止的接口

| 接口/依赖 | 状态 | 权限与输出 |
|---|---|---|
| B2 signed login / B5A opaque session | 已验收实现，复用 | 仅合成 TEST_ONLY identity |
| B5A actual Reviewer load / 原文 / proposal preview | 已验收实现，复用 | 不变的原始证据及候选校验 |
| 新 rehearsal GET/POST 与 receipt GET | 本 PR 新增接线 | 非生效 intent 与脱敏回执 |
| B3 IntentService / submit_test / get_receipt | 已验收实现，复用 | 低权限 PG16 原子事务 |
| B4 durable task API/Worker | 尚未验收，未使用 | 不宣称已存在 |
| `/v1/review`、正式 approve/send/share | 禁止 | DENY，零业务副作用 |
| 真实人员审批、ShareGrant、外部客户发布 | 未授权 | 不能由本演练记录推导 |

## 实际交互验收

Chrome 在 1280、375、320px 分别走 404 和 200 签名登录、原始页面、逐项输入、保存与授权读取，共 12 张 form/receipt 截图。使用真实指针与键盘提交；验证中文字体实际 raster 与方框不同、页面无横向溢出、控件触点至少 44px、非审批文字可见、无页面脚本、无外部请求、同一案例跨尺寸回执 SHA 相等。安全回归独立使用真实 HTTP/PG 进行撤权、失效、CSRF/Origin/Host、并发、断网与进程重启、数据库关闭、revision race 和 COMMIT 入口失效测试。
