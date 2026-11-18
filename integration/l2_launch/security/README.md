# R1-A 零外网安全采集候选

基线 `89a5115e3b8c4ab782bc140d3d278ffc83e7cc7a`；Issue148 / Owner主控146。
唯一候选终态：`R1A_OFFLINE_SECURITY_CANDIDATE_LIVE_GATE_PENDING`。
真实目标连接、真实客户资料、模型调用、对外报告、部署均未获授权。

## 可运行实物

Python3.11/3.13，复用原 `requirements-ra1a.lock`：

```sh
python -B -m pytest -q integration/l2_launch/security/offline_cases.py tests/collection/test_security.py tests/collection/test_pipeline.py tests/evidence
python -B -m integration.l2_launch.security.demo local-demo
python -B -m integration.l2_launch.security.lab --label local-kernel --base vrae-ra1a-lab:ci
```

标签必须唯一；输出只在本目录 `.runtime/<label>`。最后一条可复用本机已有原依赖镜像，不修改它；没有该镜像时可用专用CI里的固定Python digest构建。构建阶段仅安装可信依赖，未运行目标采集代码。**测试阶段固定Docker `--network none`，不是任何真实公网目标。** 宿主机不运行隔离socket用例。

`demo` 生成12种站型/拒绝例、原pack+base64 blobs、UNKNOWN边界和拒绝包，并实际调用原EvidencePack.load重载。`lab` 用唯一UUID所有权标签建立只读容器，无host网络、映射端口、主机Docker socket、客户URL或PG卷。父进程先检查NetworkMode=none/只读挂载；root只设定lo别名及防火墙，随后永久drop所有capability，以UID65532和no-new-privs运行。IPv4/IPv6默认DROP，只放行同一无外网namespace内的虚拟HTTP/TLS/DNS。绕过应用检查的直接socket探针也不能连接模拟API/元数据监听器。

原始日志包含防火墙、地址/路由、DNS查询、SNI、HTTP请求行和bait计数；JUnit、receipt及源文件SHA可复核。容器临时文件在退出前由同一无权限进程导出。失败不会转绿；只删除本次UUID且标签复核一致的容器/镜像，无global prune，不枚举或触碰Owner #145的Docker/PG/工作树。旧匿名卷不动。

这是独立Worker的安全适配候选及隔离探针，尚未接入生产API/队列，不替换原Worker/30秒租约/签名权威。隔离namespace的模拟API地址不代表已验证真实部署的API网段；后者仍需G2部署证明。

## ADR-R1A-001：来源授权兼容性，等待Owner/G0裁决

**现状源码**：`domain/policy.py::authorize_source`认识L2深度许可，但`collection/policy.py::SourceAccess.__init__`明确只接受L0/L1；`canonical_url`拒绝query、percent-path、非默认端口等。`Budget/Collector`保留L0最多5页、其他已获准模式最多8页。PinnedTransport已有固定numeric IP socket、TLS hostname/certificate、前后peer核对、GET/HEAD及无代理/Cookie/重试。DNSResolver显式A+AAAA、缓存关闭、全量特殊IP否决。

**本PR决定**：全部原文件原样保留。`FencedAccess`只增加更窄的HTTPS origin、exact path、有效时间、原SourcePolicy SHA和tenant/request/run/policy pins。类型由可信worker配置持有，不是HTTP DTO，也不是C2 #147未冻结合同。HTML、模型或用户不能通过链接、表单或环境变量增加权限。公开工厂只接受无网络fallback的录制Resolver/Transport；真实PinnedTransport仅允许lo-only、无capability的隔离实验。真实入口`capture_live`始终抛`LIVE_CAPTURE_DISABLED`，即使传approved/secret或环境开关也不启用。

**连接前检查**：原SafeFetcher逐跳解析后，新ConnectionFence再次用同一个可信解析器完整解析A+AAAA，比较整个地址集合；即使是不同公共IP的合法轮换也保守拒绝。然后由原PinnedTransport连接选定numeric IP，不做隐藏DNS，原TLS/peer和发送前权限核对继续生效。第二次解析之后DNS再变化不会改变已固定socket目的地；不宣称能连续观察DNS。限时包含两次查询，仍受原Budget约束。

**未解决且禁止绕过**：真正L2授权引用的验证方、站点控制/合法权限证明、当前撤销权威、许可期限、资料/截图版权、留存删除和模型外传地区/目的必须在G0/G2另审。只把`('L0','L1')`加上L2，或把L2请求改写成L1，均不是可接受实现。当前拒绝真实L2；没有提出或实施任何受保护文件diff。若后续需要修改，先按Issue148给Owner exact diff、威胁和负例。

GET本身不保证网站无副作用：未来每个获准路径还需责任人确认是只读资源；不能把所有GET、用户自述所有权或公开可见当法律许可。新适配没有登录、POST、Cookie jar、表单提交、浏览器执行、代理、网络miss fallback或真实启用secret。退款/注销等危险GET路径不能因为语法有效而默认获准。

## 当前真实站型适用性

| 站型/输入 | 此候选支持 | UNKNOWN或拒绝边界 |
| --- | --- | --- |
| 静态HTML | 获准exact path的HTTP原文、时间、hash | 业务语义/真实性/全站分母未知 |
| CMS服务端HTML | 同上，保留原字节 | CMS名称不等于质量；未捕获路由未知 |
| SPA/JS | 仅shell/script标签所在原文 | 不执行JS、不补造正文、CDP egress尚待真实部署证明 |
| 多SKU | 保留混合型号原文 | 不自动归并型号/版次、不补工程适配判断 |
| 多语言 | 保留UTF-8原文 | 翻译/可理解性需人工；非ASCII编码URL拒绝 |
| query旧站 | 可以保留无query入口 | `?id=...`、token、分页query均拒绝；不解码拼接 |
| percent-path旧站 | 可以保留其他合规入口 | `%20`等全部沿原canonical规则拒绝，中文slug可能无法采集 |
| 重定向 | 同origin、同scheme、exact path内，原最多5跳 | 异host/降级/越权path/环/危险port拒绝 |
| robots/403/429/WAF | 原元数据与ACCESS_BLOCKED | 不创建有罪Finding，不绕过、不重试刷通过 |
| 超时/证书/无法复用资料 | 原错误及UNKNOWN | 不伪造页面或诊断成功 |
| 图片/SVG/canvas/附件 | 仅已获准HTML字节 | 不新增图片/PDF资产、OCR、截图、加载/渲染证据 |
| HTTP-only/多域/CDN | 本候选主动更窄为单HTTPS origin | 其他源拒绝；不能修改policy换绿 |

站型样例都是录制合成输入，不是实站覆盖率或Gold。没有全站分母、16/16、REAL_CAPTURE_PASS、真实质量PASS或生产就绪声明。费用UNKNOWN；测试字节数/耗时可以计量，但没有真实基础设施账单、真实目标或模型费率，不填真实成本0。

## 对抗表与复现入口

| 威胁 | 实际检查/现有用例 |
| --- | --- |
| DNS重绑定（每跳及连接前） | 新offline_cases/isolated_cases；原test_isolated重定向重绑定 |
| 私网literal、metadata、mapped/NAT64/transition IPv6 | 原test_security + 新完整A/AAAA否决；原真实DNS隔离例 |
| API/metadata绕过应用直连 | 新isolated_cases的4个监听器/直接socket，0 accept；原5个内核直连例 |
| 异host/降级/危险port/越权路径/多域/环 | 新8类redirect、loop；原重定向/TLS协议例 |
| 伪peer与证书失配 | 新录制peer反例、新真实错误hostname；原不受信CA、SNI及peer例 |
| 代理/Cookie/登录/POST/表单 | 原真实请求头检查、新恶意代理环境；新不扩展资产/表单；方法否决沿原SafeFetcher |
| 429/robots/403/WAF/超时 | 新录制拒绝包，原Collector不生成Finding |
| 错tenant/request/run/policy、过期、撤权 | 新独立pins/时间/SHA与原逐请求重载SourcePolicy反例 |
| L2伪装/浏览器提供权限/live开关 | 原SourceAccess拒绝真L2；LIVE入口永远拒绝；无HTTP权限入口 |

原默认测试清单保持不变，专项`*_cases.py`显式运行。新双版本CI不删旧门禁；各次真实RED、原始stdout/JUnit/receipt均保留，修复只解决普通开发bug，不放宽策略。

## R1真实目标申请卡

见`release-card.json`，它是Owner审查模板，**不是可执行SourcePolicy、批准、secret或C2合同**。没有批准参数/凭据/部署egress证明，且本批仍没有live实现，所以不能运行真实目标。
至少另审：目标域/hosts/精确只读paths、方法/5或8页/限速/墙钟/字节、robots和terms、合法许可/控制权验证/版权与截图权、真实DNS+HTTP/CDP egress部署证明、隔离API/PG/metadata deny、地区/日志/留存删除、当前撤权/取消、失败清理与安全回滚。任何缺项保持PENDING；Owner逐目标G2 GO后还需要经审代码桥接，不能直接填卡开网。
