# RA-1A 实现与验收（2026-11-10 America/New_York）

## 结论与基线

本地工程验收 **PASS / LOCAL_ENGINEERING_VERIFIED**；GitHub 首次 PR CI 实际运行并通过，
不再将本次运行标为 CI_INFRA_BLOCKED。A0–A4 已实现并在合成环境验收，
总体 **PASS（RA-1A 合成环境范围）**，可交 Owner 审核；未授权生产采集或 RA-1B。
未发现仍未解决的本轮 P0/P1；结论仅覆盖下面明确测试的边界，不是生产 SSRF 认证。

实际同步的 main：`deaa8fd9834684e784fc7d388952f01f5fa4980d`，与指定基线一致。
分支 `feat/ra1a-safe-http-collection`，本记录随实现提交；精确文件哈希见证据目录。
执行依据 [Issue #2](https://github.com/gloweaseco-leo/VRAE/issues/2)。
RA-0 保留；未修改既有顶层 JSON Schema，新增六份 collection 契约。

| 工作包 | 实际交付 | 本地结果 |
|---|---|---|
| A0 | 独立实现、依赖锁定、六个输出/输入契约、来源记录 | PASS |
| A1 | 全 A/AAAA 校验、数值 IP 绑定、域名 SNI/证书验证、内核默认拒绝实验 | PASS |
| A2 | 手动逐跳审查、流式限额、墙钟期限、取消/撤销、同域租约 | PASS |
| A3 | 保守 robots、页面角色抽样、PageSnapshot/Evidence/Manifest | PASS |
| A4 | 全量 RA-0 回归、负例修复、真实 DNS/TCP/TLS/防火墙实验 | PASS |

## 实现及信任边界

`vrae/collection` 分离 policy、resolver、http_transport、fetcher、redirects、limits、
robots、discovery、manifest、contracts、errors。外部 Worker 未来调用
`Collector(SafeFetcher(resolver, transport)).capture(run_id, access)`；目前没有服务。
`SourceAccess` 接收 AuditRequest、可信政策读取函数、条款引用；读取函数必须由宿主
提供真实身份/授权凭据验证后的、非阻塞政策快照。调用方传入对象不证明身份。
每次检查重新读取政策并冻结指纹，撤销、到期、未经重新授权的变更均拒绝。

只接受 L0/L1；不自动扩大域名或路径。`/robots.txt` 本身也必须在政策允许路径内。
原始网页默认不保存，摘要也不包含抓取文本；仅保留受控元数据和原始字节哈希。
可信调用方显式设置 `retain_raw_html=True` 才在内存对象包保存有大小限制的 HTML，
不应对外暴露此开关；生产持久化、加密、留存期限和访问控制尚未实现。

成功仅为 FETCHED。ACCESS_BLOCKED/UNKNOWN 不生成 Evidence/Finding，未检查角色
列为未核实；没有页面的存在性诊断，没有 AI 语义支持验证（属于 RA-3）。
Manifest 校验覆盖租户、AuditRun、SourcePolicy、快照与证据关系、内容哈希、最终跳转、
字节数、时间和对象引用。Schema 通过仅表示结构有效；必须调用 bundle.verify，
重新签算 manifest 哈希也不能绕过关系校验。哈希不是来源签名，也不验证自然语言事实。

## 安全验收矩阵

| 边界 | 实际证明 | 限制 |
|---|---|---|
| URL/权限 | 非 HTTP(S)、凭据、查询、编码/点路径、端口、跨域、撤销负例 | 查询 URL、非 ASCII 路径暂保守拒绝 |
| DNS/IP | 全 A/AAAA；混合公私、mapped IPv6、特殊转换范围拒绝；重绑定实测 | 正常公网 IPv6 连接未测；实验 IPv6 全拒绝 |
| 连接绑定 | 实际 UDP DNS、数值地址 TCP、连接前后 peer 检查；无客户端二次解析 | 仅连接首个安全 IP，无重试/回退 |
| TLS | 隔离自签 CA 的正确域名成功；未知 CA/错域名零 HTTP；SNI 记录 | 未访问真实公网证书站点；cafile 为可信部署配置 |
| 重定向 | 每跳重查政策/DNS；302 私网、跨域、降级、编码、循环/超限拒绝 | Collector 同时拒绝协议升级，避免复用异源 robots |
| 网络层 | Docker network none；iptables/ip6tables 默认 DROP；直接 socket 探测五个诱饵均零命中 | 仅实验命名空间证明，尚未配置生产网络 |
| robots/403 | 拒绝、404、未知指令、编码路径、crawl-delay、WAF/403/MIME 测试 | 保守 robots 子集；合并适用拒绝规则，不提供完整 RFC 优先级兼容 |
| 配额/取消 | 无长度/分块/慢头/慢流、超长、最大跳数、总字节、取消、撤销真实及单元测试 | 异步检查约 50ms；同步解析有 128KiB 上限，非硬实时系统 |
| 页面发现 | 五种虚构站点，角色优先、循环去重、256 链接/128KiB 解析上限 | 只解析静态锚点，不执行 JS；角色为启发式 |
| 隐私/证据 | 默认不存原文；原文可选、哈希与关系双校验；篡改负例 | 没有生产对象存储或跨进程事务 |

初始硬上限：L0 5 页、L1 8 页；HTML 1,500,000 字节；5 跳；单请求10秒、任务120秒；
单域并发1、默认请求间隔1秒；最多64次 HTTP（含 robots/跳转）、总响应体12,065,536字节。
限制可收紧；测试使用更短时间/更小字节。进程内租约不等于分布式限流，部署 Worker 前
需租户/域名级外部调度。无自动重试、代理、Cookie、登录、POST、下载、解压缩或浏览器。

## 可复核命令与结果

在独立 venv 中安装 `python -m pip install -e '.[dev]' -c requirements-ra1a.lock`，
再执行 `python scripts/verify_ra1a.py <证据目录>`。脚本逐条运行：

```sh
python -m compileall -q vrae
python -m ruff check vrae tests --select E4,E7,E9,F
python -m mypy vrae
python -m pytest -q
python -m pip check
```

| 环境 | pytest | compileall / Ruff / mypy / pip check |
|---|---|---|
| Windows 独立 CPython 3.11.15 | 369 PASS，0 FAIL，24 SKIP | 全部退出0 |
| Windows 独立 CPython 3.13.13 | 369 PASS，0 FAIL，24 SKIP | 全部退出0 |
| Linux Docker CPython 3.11.17，隔离网络 | 393 PASS，0 FAIL，0 SKIP | 全部退出0 |

24 个宿主跳过项均为需要内核隔离的真实连接测试，已在容器执行，不算宿主通过。
原始272项保留，新增121项（含24项连接测试）。两组不是独立人数相加。
工具版本：pytest9.2.0、jsonschema4.26.0、Ruff0.17.4、mypy1.20.2，类型检查25源文件。
完整命令、退出码、时间、版本、依赖清单、源码哈希见
[3.11](ra1a-evidence/acceptance-311/summary.json)、
[3.13](ra1a-evidence/acceptance-313/summary.json)、
[隔离完整日志](ra1a-evidence/lab-acceptance.log)、
[容器配置](ra1a-evidence/container-inspect.json)、
[镜像源文件](ra1a-evidence/image-source.json)。文本日志仅统一 UTF-8/行尾空白，未删除错误。

```sh
docker build -f infra/ra1a/Dockerfile -t vrae-ra1a-lab:local .
docker run --rm --network none --cap-add NET_ADMIN --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m --memory 512m --cpus 1 --pids-limit 128 \
  --security-opt no-new-privileges vrae-ra1a-lab:local
```

启动时只允许 lo 接口。在该命名空间内把看似公网的 IP 配置为本地别名，绝无公网路由。
只放行虚构 DNS 服务器53及虚构网站80/443，其余出站默认拒绝。root 仅设置规则，
随后降为 UID65532、capabilities=0、NoNewPrivs=1；应用无法改防火墙。
记录真实请求、DNS 查询、SNI、诱饵命中数；直接 socket 绕过应用也不能连接
127.0.0.1、169.254.169.254、10.77.0.2、未授权公网别名和 ::1。
固定基础镜像 digest 见 Dockerfile；依赖版本固定但非带哈希的软件供应链锁，apt 仓库随时间更新。

## 先失败后修复记录与独立审计

- red-a1：最初 collection 模块不存在，收集失败（exit2），不是断言成功。
- red-special-ranges：3个特殊地址负例失败，补充转换/保留范围拒绝。
- red-robots-encoding：编码 robots 路径拒绝负例失败，增加保守拒绝。
- red-http-status：非法状态码负例失败，传输输出结构验证转为明确错误。
- red-manifest-metadata：4个重新封装篡改负例失败，补齐跨对象一致性。
- 原网络导入扫描禁止所有 socket，在授权引入采集模块后精确允许
  `vrae/collection/http_transport.py` 的 socket 导入；其他禁用导入和 domain 纯函数要求保留。
  first-full/lab-first 的历史失败保留，后续完整回归通过。

独立安全审计为实现后的第二轮威胁路径审查及新增负例，不冒称外部第三方认证。
重点审查二次 DNS、跨源 robots、框架自动代理、流式截止、政策变更和重新封装证据。
未调用 L2M 代码。未增加网站生成、CRM、AI Agent、模型调用、API/Worker 或数据库。

## CI、网络访问与成本

保留原 CI 门禁，新增隔离连接任务；PR 触发一次，不空提交或反复重跑。
[Issue #3](https://github.com/gloweaseco-leo/VRAE/issues/3) 记录历史计费阻断。本次
[run 42952833840](https://github.com/gloweaseco-leo/VRAE/actions/runs/42952833840)
三个作业已实际执行并成功：3.13 job130300918366、3.11 job130300918710、
隔离 job130300918592。常规矩阵各369通过/24跳过，隔离393通过/0跳过。
运行于 2026-11-11 03:27 UTC，完整时间与步骤见
[hosted-ci.json](ra1a-evidence/hosted-ci.json) 和 [完整日志](ra1a-evidence/hosted-ci.log)。
测试对象为实现提交 `81f48d9028b1050e6d1ed06f4c495b07550041c7` 的 PR 合并引用。
此后提交仅补充文档与证据，最新 HEAD 的 CI 状态继续在 Draft PR 记录。
未修改 Billing、不推断账户付款已解决，也未关闭历史 Issue #3。

网络访问仅 GitHub 仓库/Issue、官方依赖文档、Python 包和镜像构建依赖下载。
测试网站请求全部在隔离 lo 命名空间；真实第三方网站0、模型调用0、付费模型费用0，
未购买服务。开发机、带宽、电力和既有账户费用未获取账单，金额 UNKNOWN，不能记0。

## RA-1B 建议（未执行）

先由 Owner 审阅本 PR；生产/真实站点实验需要单独域名、路径、时段、页数和条款授权。
RA-1B 单独 PR：Chromium 与 Python 控制 Worker 分容器/用户/文件系统，浏览器无密钥，
默认无外网，唯一出口为经审查的代理；代理再次验证 DNS/IP/域名/逐跳和连接绑定，
限制所有子资源与 WebSocket/Service Worker，禁止 POST、下载、文件协议、内网和 metadata。
不可只依靠 Playwright route 拦截来证明网络隔离。
先补合成恶意子资源、重定向、DNS 变化、弹窗、下载、表单、存储和进程逃逸边界测试，
再考虑授权站点实验。必须提供进程外任务终止、资源配额、跨进程域名租约、证据关联及
原文留存控制。无本轮新增服务采购要求；浏览器托管/出站代理费用先测量后由 Owner 决策。
本轮停在 Draft PR；不进入 RA-1B、不合并 main、不部署。
