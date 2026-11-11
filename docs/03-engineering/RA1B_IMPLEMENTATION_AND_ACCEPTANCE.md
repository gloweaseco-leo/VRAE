# RA-1B Chromium / Worker 合成隔离验收

执行依据：Issue #5，2026-11-11。起始 main 已重新 fetch，
`8bc460764dedb6a87c2e7806b2d3b382875596de` 与 Owner 指定值一致，
与已验收 RA-1A 分支内容相同。原 RA-0、RA-1A 代码和验收证据保留。
本阶段对应 V1.1 总计划 RA-1D 浏览器工作包；不进入 RA-2。

## 状态

本地完整回归已通过；托管 CI 待 PR 首次运行核验，不提前宣称 CI PASS。实现分支
`feat/ra1b-browser-worker-isolation`，只提交独立 Draft PR，不合并或部署。

| 包 | 交付 |
|---|---|
| B0 | [冻结拓扑](RA1B_TOPOLOGY.md)，Unix IPC 控制与资源 Broker，无 CONNECT |
| B1 | 非 root Chromium、独立容器/PID/网络/文件系统，真实 Sandbox 与配额探针 |
| B2 | 复用 RA-1A SourceAccess/SafeFetcher/robots/Budget，默认拒绝资源类型和写方法 |
| B3 | 私有版本化 BrowserObservation，桌面/移动 DOM、PNG 与资源哈希关系 |
| B4 | 真实 Chromium 合成攻击、撤销、崩溃、SIGKILL、文件及进程清理 |
| B5 | 两版 Python 全回归，保留原 HTTP 隔离任务，新增真实浏览器 CI |

本地结果（2026-11-11 UTC）：

| 环境 | 通过/失败/跳过 | 质量命令 |
|---|---|---|
| Windows Python3.11.15 | 425 / 0 / 25 | compileall、Ruff、mypy、pip check 全 exit0 |
| Windows Python3.13.13 | 425 / 0 / 25 | 同上，全 exit0 |
| Linux 原 HTTP 隔离 Python3.11.17 | 449 / 0 / 1 | 同上，全 exit0 |
| 独立真实 Chromium + Worker | 16场景达到预期 | 15次 pytest 各1通过；Worker强杀场景预期exit137并清理 |

保留原422项，新增27项普通测试及1个以16种场景独立运行的真实浏览器测试函数。
宿主25跳过=原24项HTTP网络测试+1项浏览器实验，分别在正确的隔离环境执行。
Linux HTTP环境只跳过浏览器专用函数，不能计为浏览器通过。
pytest9.2.0/jsonschema4.26.0/Ruff0.17.4/mypy1.20.2，类型检查30源文件。
精确命令、退出码、源码哈希、环境和全部原始失败/通过日志见
[证据索引](ra1b-evidence/README.md)。原始日志统一UTF-8与行尾空白，错误内容未删除；
为方便代码审阅，实验子目录完整压缩归档，索引保留每个成员的SHA-256。

## 已实现边界

`vrae/browser/{broker,cdp,controller,observation}.py` 是模块化单体的基础设施模块，
没有新增公共 API、数据库或独立微服务产品。Python Worker 和 Chromium 分容器运行，
UID 分别65532/10001，无生产秘密。每个任务创建独立容器、临时 Profile 和 IPC 卷。
控制通道为 Unix socket ↔ CDP debugging pipe；没有 TCP 调试端口或透明 HTTPS 隧道。
共享 IPC 为1MB tmpfs（单独实测 ENOSPC），不共享原始证据或凭据目录。

浏览器容器 `network none`，只有 lo；capabilities 全清空、NoNewPrivs、只读 root。
外层 seccomp 默认拒绝，只允许 AF_UNIX 和 AF_NETLINK，IPv4、IPv6、packet socket
及旧 socketcall 无放行规则，TCP/UDP 在创建 socket 时即 EPERM。网络接口存在性和
真实系统调用失败独立于浏览器路由；没有只靠 Fetch 拦截宣称网络隔离。
Netlink 用于系统状态查询，外层无 NET_ADMIN，不能建立新的出站接口。

实际 Chromium 156.0.8078.79 内部诊断：Layer 1 Sandbox=Namespace，PID namespaces=Yes，
Network namespaces=Yes，Seccomp-BPF sandbox=Yes。未使用 no-sandbox、privileged、
host network/IPC 或 seccomp-unconfined。容器 profile 允许创建用户命名空间及 chroot，
供 Chromium 在自身用户命名空间内建立沙箱；外层仍无 capabilities。
专用前置诊断使用 allow-chrome-scheme-url 读取 chrome://sandbox，该参数**不在网页执行
容器参数中**。实际任务还会通过 CDP 重新读取沙箱诊断；不把父进程 Seccomp=2 当作浏览器证明。

Worker 在隔离 lo 命名空间中访问虚构 DNS/TLS 服务器；iptables/ip6tables 默认 DROP，
只有已指定的虚构 DNS53、网站80/443可访问。所有站点地址是该命名空间内的本地别名。
浏览器和 Worker 没有公网路由；资源请求由 Broker 以已验证数值 IP 建连，并验证域名 SNI
和证书。浏览器自身没有建立 TLS 网络连接，TLS 真实性检查由 Broker 执行。

## 资源政策与证据语义

- L0 拒绝浏览器；L1 最多3个明确批准且去重的 URL，各1280×720桌面和390×844移动视口。
- 只允许 GET/HEAD；Document、Script、Stylesheet、Image、Font、Fetch/XHR 有明确 MIME 集合。
  Other 默认拒绝；CDN 不自动放行。本版跨域资源全部拒绝，单独 CDN 授权适配尚未开放。
- 每次资源读取复用 RA-1A 授权指纹/撤销/到期、DNS全结果/IP绑定、逐跳、robots与字节/时间预算。
  HTTP重定向仍逐跳受检，但主文档跳转保守拒绝呈现，避免把最终字节渲染在错误原 URL 下。
- CSP 限制表单、iframe、worker、object、跨源连接及弹窗；CDP拦截只作辅助。
  即使 JS/WebSocket/WebRTC/ServiceWorker 绕过路由，外层 socket 系统调用仍被内核拒绝。
- 默认禁止下载，不自动接受文件选择或向页面提供宿主文件；无 Cookie/认证头转发。
- 512MB内存、1 CPU、256 PID、256MB任务tmpfs、1MB IPC tmpfs；实验 Worker 总预算18秒，
  外部监督命令40秒硬截止，失败时强制删除本任务容器和卷。预算是门禁，不是生产 SLA。
  Chromium 主进程退出时 agent 结束容器 PID1，内核终止其 PID 命名空间中的其他进程。

DOM 摘要最多128个目标元素、每项160字、总64KB；只记录有限基础几何可见性，
不等于完整可访问性或视觉正确性判断。截图仅固定视口PNG、最大2MB，不做全页无限截图。
绑定 tenant/run/policy/version/approved URL/时间/视口/renderer/资源追踪及内容哈希。
Artifacts 在返回对象包中默认私有，仅内存，不自动上传。测试 CI 上传的仅为**合成**日志。
OBSERVED 必须具有 DOM/截图和成功主文档资源，且无已记录错误；否则 UNKNOWN/ACCESS_BLOCKED。
例如 favicon 被识别为 Other 时会被拒绝，保留已有 DOM/截图但状态为 ACCESS_BLOCKED。
禁止把这个保守兼容性限制藏成“完整观察成功”，也不能把它判为网站业务缺陷。

观察为有界时间窗口（DOMContentLoaded 后约400ms，再等待已开始的有界资源任务），
不是整个网站未来行为的证明。截图、DOM、URL 路径都可能含 PII；不是匿名化输出。
没有脱敏导出、生产对象存储、真实身份系统或签名来源认证。普通 SHA-256 只校验一致性，
不能证明远端自然语言事实。无 Finding、报告、人审审批或商务事件生成。

## 实验与失败修复

原始失败保留，不删除失败断言、不关闭保护：

1. Chromium 包的 HTTP 下载连接失败；改用同一 Debian 官方 HTTPS 仓库、有限重试后成功。
2. 两次镜像导出同名冲突导致旧镜像缺探针；改为串行构建，不作为源码安全 PASS。
3. 真实 socket 探针发现初始 seccomp 规则未拒绝套接字；立即停止浏览器执行，改为
   仅允许 AF_UNIX/AF_NETLINK 的明确条件规则。相同探针复验 IPv4/IPv6 TCP/UDP 均 EPERM。
4. Chromium 建立 sandbox 时 chroot 被外层 seccomp 拒绝；增加单一 syscall 许可，
   不增加外层 capabilities；诊断确认其内部 Namespace/PID/Network/Seccomp 全开启。
5. Chromium156诊断字段更名；按真实诊断表读取 Layer 1 Sandbox=Namespace，保留全部硬断言。
6. 旧 CDP 诊断页事件误终止当前事件泵；限定事件 session 后通过真实只读双视口渲染。
7. 重新封装的观察包缺成功 Document 仍可伪称 OBSERVED；负例1失败/12通过后补齐关系校验。
8. 慢启动下测试的撤销监视提前结束，强制5秒延迟负例确实失败；监视改为整个任务期限，
   必须证明动作发生且得到 POLICY_REVOKED。早期名为 revocation 的取消实验不冒充真实撤销。
9. 浏览器崩溃的 CDP 超时未结构化；修复错误转换及 agent 主进程退出监督，再验 crash/SIGKILL。

合成场景含：readonly、writes、private、resources、channels、escape、storage、redirect、
redirect_private、rebinding、infinite、memory、revocation、crash、sigkill、worker_kill。
正常及攻击脚本使用触发标记；关键写入和旁路通道分别有尝试标记。服务端保留真实请求行，
诱饵连接和实际内存写入计数。不是仅验证“路由回调被调用”。Cookie/localStorage/IndexedDB
跨独立 BrowserContext 检查，跨任务再创建全新容器/Profile。没有真实第三方企业内容。

原始网络门禁的 positive control 只证明未加定制 profile 的合成探针能创建 socket，
不运行无 Sandbox Chromium，也不连接公网；随后相同 syscall 在受限 profile 下被拒绝。
kernel probe 同时实测只读 root、256MB tmpfs；每次 agent 实测1MB IPC配额。
Supervisor保存容器配置、浏览器真实argv、内部沙箱表、Broker/服务端日志、退出码、
结束状态、删除结果。删除后 docker inspect 返回1表示对象不存在，是**预期清理证据**；
worker_kill 的137是故意 SIGKILL 的预期结果，不计作普通 pytest 成功。

## 复现

```sh
python -m pip install -e '.[dev]' -c requirements-ra1a.lock
python scripts/verify_ra1a.py /tmp/python-gates
docker build -f infra/ra1b/Dockerfile -t vrae-ra1b-browser:local .
docker build -f infra/ra1b/Worker.Dockerfile -t vrae-ra1b-worker:local .
python scripts/verify_ra1b.py /tmp/browser-gates
```

正常 Python 回归分别报告；浏览器测试在宿主跳过，不能算通过。
保留原 `isolated-http` CI，新增 `isolated-browser` CI。任一 Runner 不支持本门禁即失败，
没有保护关闭或 skip-on-failure fallback。最终结果、代码 SHA 与 run/job 在验收后补充。

## 依赖、审计与剩余门禁

无新增 Python 运行依赖或大型框架；直接使用 Chromium CDP 的小型受限 IPC 适配器。
Debian Chromium版本构建后明确检查156.0.8078.79-1~deb12u1，基础 Python镜像digest固定。
apt索引/间接依赖不是完整不可变供应链锁；生产需要补丁更新与镜像审计流程。
未复制 L2M；没有模型费用、采购服务、生产数据、真实站点流量或对外发送。
本地机器及既有 CI 账单未知，不记为0；官方依赖/文档/GitHub访问不属于站点采集。

seccomp 原始来源为 Microsoft Playwright v1.56.1 的 utils/docker/seccomp_profile.json，
附上上游 Apache-2.0 LICENSE。变更仅用于默认拒绝浏览器网络socket和支持自身namespace chroot；
不是引入 Playwright 运行依赖。参考官方
[Docker sandbox说明](https://playwright.dev/docs/docker)、
[Chromium Linux sandbox](https://chromium.googlesource.com/chromium/src/+/master/docs/linux/sandboxing.md)、
[Chrome内部页诊断参数](https://developer.chrome.com/docs/automation-and-testing/headless-cli)。

生产仍须独立验收：身份与许可凭据、私有对象存储/留存/脱敏、部署网络、分布式配额、
supervisor本身失效后的持久任务回收、软件供应链及内核补丁。没有生产安全认证结论。
RA-1A原有路径隐私、保守robots、未验证公网IPv6和哈希不等于来源证明的限制继续有效。
不进入 RA-2；由 Owner/首席架构师审核 Draft PR。
