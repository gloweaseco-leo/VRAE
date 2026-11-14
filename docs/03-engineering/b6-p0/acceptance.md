# B6-P0 本地门禁与首轮交接

本记录属于 `B6_P0_PRIVATE_DELIVERY_PREFLIGHT_CODE_GO`。入口基线为 `ae2505f74f7a81d7a563c05d1a811aaa526c2839`，分支 `codex2/b6p0-private-handoff-preflight-testonly`。不代表完整 B6、自然人审批或真实客户交付已验收。

## 已验收主线同步

Owner 已验收并普通合并 B4-P1 PR83 后，B6 分支普通快进到 `447005b2951f43e8d8643632d663de268f278329`，未复制未合并的 PR89。B6 依赖的已验收读取/签名/原生验证接口及 20 个新源码/Schema/CI 文件字节不变。本地实验仍只应用 0001–0003，不调用 B4 API/Worker 或 0004。

在组合树上重新执行 `sync-311-01`、`sync-313-01`：两者均为原生 104/104、0 skips，61 个实际 PG 场景、62 条实际清理记录，业务/目录指纹保持不变。静态检查覆盖合并后 82 个库文件。当前主线加两个 B6 jobs 预期共 20，最终以实际 jobs 为准。

## 已执行的入口探针

专属真实 PG16 实验使用原始迁移 0001–0003 和实际 `p2b1_test_a_reviewer`。已验收 B2 验证真实 Ed25519 合成 token/单次 challenge，B5A 读取 SQL 原始 TARGET/manifest/DRAFT/HTML/SOURCE/Guard 并执行 NativeVerifier。没有 fixture fallback、APP/superuser 读取、SET ROLE 或新增 SQL 表。

404 入口得到 1 项 L1 草稿发现，原始 SOURCE SHA 为 `3931962da536faa57f975b751ebdeff8141737feed5d15a3aeee52bd50e5e01a`；200 入口为 0 发现和 PRIVATE_COVERAGE_ONLY，SOURCE SHA 为 `f679bb4bf463e788775b2e2c163e0b424187fab6098e8df9a0e66c00e780c614`。两者私有候选和密封 HTML 均在当前会话下重新读取 PG、逐字节比对通过，数据库指纹前后相等。原始探针及私有输出留在忽略目录。

## 最终本地结果

实际最终冻结轮已完成。以下均为真实原生结果；Hosted 尚未运行，不代表 Owner FINAL PASS。

| 环境 | 原生用例 | 真实 PG 场景 | 纯合同/拒绝门 | 实际清理 | 脱敏预览 |
|---|---:|---:|---:|---:|---:|
| Python 3.11.15 | 104/104，0 skips | 61 | 43 | 62 | 2 |
| Python 3.13.13 | 104/104，0 skips | 61 | 43 | 62 | 2 |

两版最终执行均保持 20 个新源码/Schema/CI 文件字节不变；各自 12 个原始证据文件及清单已逐字节核对。每轮实际 SQLSTATE 包含 `42501`，每个产品操作前后的业务/目录/角色指纹相等。原件见 `evidence/sync-311-01/`、`evidence/sync-313-01/`。Ruff、mypy 及三份 Draft 2020-12 Schema 通过；具体当前库文件数量与原始输出见 `evidence/static-checks.json`。

404/200 实际脱敏 HTML 均以离线 Chromium 输出核对为 1 页；对应输入 HTML 与两版本最终候选的私有 HTML 完全一致。仅公布 HTML/页数/指纹，PDF 原件保留私有目录；见 `evidence/preview-layout.json`。

相关既有 v1/domain/reporting/reviewing/identity/operator-console/B3/B6 回归：3.11 原生 824/824；3.13 并行轮保留为 823/824 RED，唯一失败为旧 HTTP 404 预览 GET 的 30 秒 TimeoutError。相同源码、相同 30 秒阈值下，原失败用例随后串行 1/1 通过（20.18 秒）；没有修改旧代码、阈值、权限或跳过项，也不把它改写为新一轮 824/824。原生 XML 保持私有，SHA 与精确结果见 `evidence/accepted-regression-summary.json`。

较早开发轮 104/104 为其当时冻结源码的真实结果，保留于 `evidence/dev-311-01/`；原入口主线上的双版本完整冻结结果保留于 `evidence/final-311-01/`、`evidence/final-313-01/`。若主线同步，则最终提交依据只使用当前同步后重新执行的上述双版本。

## 验收矩阵与证明边界

- 每个 PG 用例使用专属实际数据库，由单次实验的已验收 schema 模板克隆；产品只持低权限 Reviewer 会话和已验收读取接口。测试控制面的管理员/签名器只用于一次性装配或明确撤权负例。
- 源文件、JSON Schema、当前签名身份/assignment/policy、原始 SOURCE/HTML/Guard/manifest/target、引用区间、Claim hash、原生内容 hash 与密封 HTML 全部绑定。即使调用方重算出自洽摘要，仍需通过重新读取当前 PG 的字节比较。
- 404 的 1 个 Finding 保留原生事实支持的窄范围；200 的 0 Finding 不产生虚构 L1 或批准。候选上限为 3 项，不输出模型建议、排名、ROI 或 E2/E3。
- 覆盖跨 tenant/report/version/source-run/target/ref/issuer/subject/role、错误/失效 policy、过期/撤销 anchor、签名 token 过期/错配/多带 Owner 字段、token 重放、原文独立 pins 篡改、候选重算摘要、伪造零发现 L1、畸形/重复/超长 JSON，以及读取中途撤权。
- 每个交付负例实际尝试全部已定义 live 操作并重放，证明没有 grant/token/recipient/public URL/native decision/outbox；in-process sink 只记录有限 DENY。额外测试网络防线在真正 DNS 前拦截，产品调用上下文实际网络事件为零。真实 PG 连接只允许已验收的数字 loopback 设置；不包含 VF/邮件/HTTP 传输实现。
- 指纹覆盖实际数据库行、源对象、目录/SQL、角色和授权。撤权测试由可信控制面改变授权后记录新的产品基线，并单独保留此前指纹；产品调用本身前后无写入，不把该测试装配描述为产品业务变更。低角色原始 SELECT、DML 和角色提升必须得到实际 `42501`。
- 原始失败 XML/日志保持私有；公开只导出无 failure/skip 的原生 JUnit、限定状态/指纹、清理记录和两个脱敏单页预览。成功原始文件清单逐字节校验，扫描真实一次性密码、会话和 token。完整原始 Guard、BYTEA、联系人及登录凭据不进入 DTO 或公共证据。

## 开发 RED 原样保留

1. 首次入口运行在沙箱内无法创建 Docker 实验网络，亦无法完成 Docker inspect；这不是 SQL 权限或来源绑定失败。随后在已批准的 Docker 执行环境使用新实验标签继续，并核对专属资源清理。
2. 最初测试助手把已验收 `SessionStore.login` 的 opaque sid 字符串当作二元组解包，出现 `ValueError: too many values to unpack`。仅修正新测试助手；原有 B2/B5A 返回值和接口未改。失败运行保留，专属数据库与 PG 资源已清理；新标签入口探针完成 404/200 原始读取和往返验证。
3. 新库顶层直接导入应用适配器时，mypy 沿引用检查到已验收应用中的 15 项类型问题。新读取边界改为在实际 PG seam 延迟装载同一个已验收 SessionStore/ReviewerReader 类，并继续执行精确类型校验；未改旧模块或关闭原有检查。纯合同不加载可选应用运行时，mypy 对新的 80 个库源文件通过。

后续任何开发 RED 或源码变更轮将保留其原始状态，不混入最终冻结 PASS。

## 首轮 Hosted 交接规则

本地全部门禁通过后，核对 Owner 已验收 main；若前进，只普通 merge 已验收 main，并重跑受影响的本地验证。禁止复制未合并 PR83/PR89。允许一次显式路径提交/推送、一个 Draft PR、一次自然 CI；原有 workflows 不删改，实际 jobs 数随已验收 main 核对，不把 18 或 20 当成预设通过数。

首轮结束后，通过 PR 原始交接给出 HEAD/merge-ref/有序 parents/tree、实际 jobs/attempt、源/角色/目录指纹、原生 JUnit 和公共安全 artifact 哈希，然后 STOP。不补推、不 rerun、不自行合并或部署。完整 B6 issue 保持开放，真实人员审批/同意/法律依据/ShareGrant/收件人交付均需后续独立授权；Beta 仍 2/7，G1/G2/G3 NO-GO。
