# G1-S1 独立零外网安全负例包

基线 `7fdeeed0f427ce3b94677ab2a480eae1556e85ca`，Owner Issue154 / 总装 Issue153。
仅新增攻击数据、consumer负例、确定性回放和证据工具；原R1-A/R1-B/G0/Collector/Guard及C3服务均不改。

## 复现

Python3.11/3.13，原 `requirements-ra4b-p1.lock`：

```sh
python -B -m pytest -q integration/l2_launch/g1_security/security_cases.py
python -B -m integration.l2_launch.g1_security.replay --label local-replay
python -B -m integration.l2_launch.g1_security.kernel_replay --label local-kernel --base vrae-ra1a-lab:ci
```

标签必须唯一。输出为本目录`.runtime`；原kernel工具还保留自己的原始runtime，包装器只复制证据、不改原源文件、不另写网络组件或清理逻辑。只使用当前分支副本及原工具生成的唯一UUID资源；禁止指向Owner个人UAT或其他人的运行标签。无global prune，不创建云资源。

## 结果分层，不能拼接成G1通过

| 层 | 实际做了什么 | 可声明的范围 |
| --- | --- | --- |
| source_matrix.json，45例 | 真正调用原OfflineWorker.capture、SourceAccess、SafeFetcher/Collector及RecordedResolver/Transport，保存原EvidencePack并重载 | 原采集器在录制输入上的观察/拒绝，非HTTP服务或PG作业 |
| contract_cases.py，23例 | 调用已冻结G0函数、公开合成密钥与fixture SQLite，独立签名冲突/篡改/撤权负例 | FUNCTION_NOT_HTTP；不是业务PG、正式人审/ShareGrant或服务接纳 |
| 原R1-A kernel probe | 复用原32个真实DNS/TLS/内核案例；模拟API/metadata绕过0 accept | 原隔离组件复验，不能证明尚未运行的G1服务也具备同样egress |
| http_matrix.json，24门禁 | 每项输出BLOCKED_PENDING_G1_IMPL和所需实物 | 实际G1 HTTP、PG、Worker、Cookie/CSRF、日志及清理尚未验证，不能改成PASS |

76项pytest包括45个来源、23个契约函数、8个回放/边界检查。矩阵的24个HTTP BLOCKED不会因为pytest绿而变为HTTP PASS；“未提供服务时应保留BLOCKED”的单元断言只测试账本诚实性。

## 来源与权限否决

两条正常工业输入实际形成HOME/CATALOG/PRODUCT角色，分别为静态和CMS来源；不是拼接旧S5 bundle或冒称原Worker已签名提交。每例独立request/run/policy ID，固定公开的合成时钟，真实source_audit_mode仍L1。OFFLINE_SYNTHETIC仅描述测试入口模式，不将L2改写为L1。

负例覆盖私网/环回/metadata、IPv4简写/整数、IPv6 literal/mapped/NAT64/6to4、完整A+AAAA混合、连接前重绑定/公共集合变化、跨host/降级/越权路径/环、伪peer、TLS注入故障、原始403/429/robots/WAF/超时、缺许可、tenant/request/run/policy/time/method越权及审计模式修改。注入TLS_FAILED不冒称真实证书负例；真实证书失配由原kernel实验单独记录。

拒绝码和FETCHED/ACCESS_BLOCKED/UNKNOWN来自实际原输出，拒绝不得产生保留正文或Finding。无raw bytes时明确downstream_evidence=UNKNOWN。计数区分snapshot_records和含robots/跳转的requests，全站分母null。恶意原文保留但不能改变权限或触发外链/POST；不执行JS，不扩展资产，不判工程适配或语言质量。

source/contract回放用网络tripwire：它不返回伪HTTP响应，任何意外socket/DNS连接直接FAIL；原RecordedTransport不提供网络fallback。全部源结果与pack原文再跑一次必须逐字节一致，matrix保留确定性摘要。`capture_live`始终拒绝，真实客户/目标公网、模型及正式外发均0。

## HTTP独立检验清单与C3衔接

当前accepted base只有PrivateAdapter callable、ResumeProposal和G0 fixture，不是VF-B HTTP服务。因此服务身份、版本协商、邀请/租户/同意、幂等409、裸ref、未发布/旧hash、Cookie过期/撤回/CSRF、反证丢失/修改、4 priority、密钥回滚、503/死信、日志泄漏、PG先COMMIT后202、同一task来源/Worker租约、实际egress和清理逐项BLOCKED。

G0函数的key撤销否决不能替代真实认证key epoch/回滚验证；safe_log_record纯函数不能证明服务日志没泄漏；fixture返回set_cookie字段不是实际Set-Cookie。报告反证/优先项反例有有效输入正控制，不使用“所有请求都403”的假服务通过测试。

C3首个G1 HTTP Draft出现后，固定其精确HEAD只读读审，确认同任务来源、原PG/Worker/权限及network-none运行配置，再在独立owned标签上调用其真实loopback入口，记录实际请求/响应状态和脱敏HAR。记录真实Socket连接，不用mock/fixture journal替代服务。Cookie/token/CSRF/联系人/原文只在受控私有存储，公开HAR及日志仅固定安全字段、hash和响应码。阻断附源码行和最小复现回贴Issue153，由C3修；不改其分支。

此批终态仅 `G1_S1_INDEPENDENT_SECURITY_PARTIAL_HTTP_BLOCKED`，不能申请Owner的`G1_INTEGRATED_OFFLINE_HTTP_E2E_PASS_LIVE_GATES_PENDING`。真实目标访问、SourceAccess真正L2桥接、可信DNS/HTTP/CDP出口部署、来源使用/版权/留存许可、客户报告、真实Provider/费用及生产/云部署仍须独立G2 GO。
