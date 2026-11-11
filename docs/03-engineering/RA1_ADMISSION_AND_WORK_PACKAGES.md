# RA-1 准入审查与实施建议（RA-0F 交付，未授权执行）

> 2026-11-10 更新：Owner 已通过 Issue #2 及开发指令授权 RA-1A 独立实现，明确不复制 L2M。下文保留 RA-0F 时点结论；当前交付见 [RA-1A 验收](RA1A_IMPLEMENTATION_AND_ACCEPTANCE.md)。RA-1B 仍未执行。

## 决策

RA-0 本地完整工程验证已有替代证据，可提交 Owner 审批；GitHub CI 因账户计费/额度
阻断，不能写成 PASS。**本轮 RA-1 执行 NO-GO**：没有 RA-1 开发授权，L2M 移植许可
尚未确认。建议在 Owner 接受 RA-0、确认代码使用权后，单独授权 RA-1A 合成环境开发。
RA-1B 必须等待 RA-1A 的实际网络隔离验收，不同时启动浏览器、AI、后台或数据库。

此处使用路线图的 PR 批次命名：RA-1A=只读 HTTP，RA-1B=浏览器隔离。
对应开发总计划中的 RA-1A/B/C 静态采集工作与 RA-1D 浏览器工作，不删减其门禁。

## 固定来源与许可

- 来源仓库：`https://github.com/gloweaseco-leo/Legacy2Modern-`。
- 本次实际检查的候选提交：`07923c5575df918e28eebc431faec986bbda0a1a`。
- 同时读到远程默认 HEAD `ee718a68c2d57942886b641d9795014cb0eb39ee`，与候选不同。
  不声称候选是最新，不把未审查的新提交混入移植。若换源 SHA，重新做差异与许可审查。
- `legacy2modern/url_fetch.py` blob：`9223c30455fff1904daf75e3243c0404682ca389`。
- `legacy2modern/discovery.py` blob：`1ad3122cc3a89d394dc41d9a8577162079120393`。
- 固定提交内容的 SHA-256、pyproject blob 与依赖元数据见
  [provenance](ra0f-evidence/l2m-provenance.json)。检查过这两个本地文件及 pyproject
  相对候选 HEAD 无差异；其他未提交改动未读取为移植输入，也未修改源仓库。
- 候选仓库未检出受 Git 管理的 LICENSE/COPYING 文件；这不是可移植许可。
  Owner 需确认权利主体、内部复制/修改范围与署名要求；否则不复制源码，可另行批准
  按 VRAE 需求独立实现。没有在本轮复制或执行 L2M 采集代码。

允许审查的最小候选：`assert_public_ip`、URL/scope 检查、`_resolve`、
`default_exchange`、有界 `fetch_page`，以及 discovery 的链接 inventory、页面角色与
代表页选择。适配时拆分传输与分类，避免 fetch 仅为一个页面而导入整套 discovery。
不移植 Builder、Renderer、Design Agent、生成器、商业 adapter、API、数据库或
`browser_verify.py` 的真实站导航。`fetch_referenced_assets` 与 snapshot 文件写入
逻辑不直接搬用，必须由 VRAE 资源/对象路径策略重新设计。

静态审查发现候选已用 IP socket + 原始 hostname 的 TLS SNI/Host，逐跳检查 DNS；
这只是候选实现证据，不是 VRAE SSRF PASS。尤其需重新验证：IPv4-mapped IPv6
候选逻辑允许映射的公网地址，而 VRAE 计划统一拒绝；候选超时重试/线程、编码路径、
Cookie/代理继承、流式总时限与浏览器 egress 都不能因“已有函数”而免验。

## 实际依赖与最小移植依赖

| 范围 | 静态依赖/观察结果 | RA-1 处理 |
| --- | --- | --- |
| url_fetch | 标准库 pathlib/hashlib/ipaddress/json/re/socket/ssl/threading/time/urllib.parse/http.client；bs4；本包 discovery | 抽出纯 HTTP 核心，尽量仅标准库；禁止生成运行时依赖 |
| discovery | re、urllib.parse、BeautifulSoup | 如确需解析 HTML，单独锁定 beautifulsoup4 及传递依赖 |
| bs4 现有 L2M 环境元数据 | beautifulsoup4 4.15.0、soupsieve 2.10、typing_extensions 4.16.0；前两者 MIT，后者 PSF-2.0 元数据 | 这是现有环境快照，未在 VRAE 安装/运行；移植时保留许可证并生成锁定清单 |
| 整仓 pyproject | beautifulsoup4>=4.12、jsonschema>=4.18、psycopg[binary]>=3.1；可选 playwright>=1.40 | 不照搬整仓依赖；HTTP 适配不需要 psycopg/Playwright |
| RA-1B 新依赖 | Playwright Python 包、对应 Chromium revision、基础镜像/OS 库 | 单独锁版本和镜像 digest；此轮未选择/下载/运行 |

## RA-1A：首个独立 PR，只读 HTTP 适配

建议分支 `feat/ra1a-safe-http-collection`，本轮不创建。

| 顺序 | 预计模块/工件 | 工作内容 | 可执行退出门禁 |
| --- | --- | --- | --- |
| A0 | `THIRD_PARTY_CODE_PROVENANCE.md`、依赖锁 | 固定许可、源 SHA、复制函数和修改清单 | 权利证据齐全；源文件 hashes 可复核 |
| A1（首个编码包） | `vrae/collection/policy.py`、`resolver.py`、`http_transport.py` | 注入 DNS/transport/clock 的独立只读 GET/HEAD；承接 RA-0 policy | 无浏览器/模型/后台依赖；合成 resolver/exchange 负例全部拒绝 |
| A2 | `vrae/collection/redirects.py`、`limits.py` | 每跳域/路径/IP 绑定、总时限/字节/跳数/速率/取消/撤权 | 重绑定、跳转逃逸、慢流与无长度响应有界停止 |
| A3 | `vrae/collection/robots.py`、`discovery.py`、`manifest.py` | 同策略读取 robots；仅已许可页面抽样；CaptureManifest 与 PageSnapshot | 未知 robots/访问拒绝按冻结策略停止，不判网站缺陷；快照 hashes 可重放 |
| A4 | `tests/collection/`、`tests/fixtures/sites/`、隔离测试配置 | 可控 DNS/HTTP/TLS 假站和网络命名空间集成 | 实际连接 IP 与校验地址一致；内网诱饵服务零请求；默认无公网出口 |

首包 A1 只建立协议与合成测试；A2–A4 仍在 RA-1A 独立门禁内，不先开实网。
建议初始合成限额：并发 1、L0 最多 5 页/L1 最多 8 页、HTML 1,500,000 bytes/页、
最多 5 跳、单次请求 10 秒、整任务 120 秒。属于拟冻结参数，非已实现承诺；所有拒绝、
重试与 robots 请求计入请求/时间预算，失败不自动换代理或绕开 WAF。

### URL/DNS/连接/网络的分层保护

1. 入口：RA-0 syntax gate + 规范化策略；拒绝 userinfo、IP literal、非默认端口、
   控制字符、编码分隔符/遍历、多重解码歧义。域名大小写/尾点/IDNA 的统一形式只计算一次。
2. 授权：从可信存储取得 tenant/run 对应的政策、版本、时间、撤销状态；每次连接和跳转
   检查 permitted host 与 scope path；不能相信请求方自己填写“授权通过”。
3. DNS：解析所有 A/AAAA；混有一个非公网地址即整体拒绝。拒绝回环、RFC1918、CGNAT、
   link-local、metadata、保留/文档/多播/未指定、IPv4-mapped IPv6、zone ID。
4. 连接：连接已验证 IP，不允许客户端重解析；TLS 验证原 hostname/SNI，Host 不变，
   验证 peer IP；多地址 failover 仅限已验证集合。不用全局 monkeypatch DNS。
5. 跳转：关闭自动 follow；每跳重新执行 1–4；拒绝跨域/越路径、HTTPS 降级、循环、
   非 HTTP(S)。不转发 Authorization/Cookie；不继承环境代理或 netrc 凭据。
6. 网络：单任务网络域默认 deny，仅通过受控出口；内网/metadata 在网络层再次拒绝。
   DNS 只能到指定 resolver。合成网络使用单独测试策略，不能将测试的 loopback 例外
   混入生产 SourcePolicy 或靠关闭保护来访问 fixture。

## RA-1B：第二个独立 PR，Chromium 只读观察与隔离

建议分支 `feat/ra1b-browser-isolation`。前置：RA-1A PASS、隔离设计审查和单独授权。
预计模块：`worker/browser/`、浏览器请求策略、容器/egress 配置、浏览器安全回归。

Python 调度 Worker 与 Chromium 分容器/网络域；Chromium 非 root、启用浏览器 sandbox、
只读根文件系统、临时 profile/tmpfs、禁止宿主目录挂载和 Docker socket、CPU/内存/PID/
磁盘/总运行时限制。浏览器没有 DB、VF、模型或对象存储管理密钥。使用单任务凭据或
受限工件通道输出截图/DOM，任务结束销毁 profile，不共享 cookies/localStorage。

浏览器强制走受控 egress proxy，由 proxy 做 DNS/IP pinning；网络层禁止直连、QUIC/UDP、
内网与 metadata。Playwright 路由拦截是补充，不能替代网络策略。禁止 Service Worker、
WebSocket、WebRTC 出站和后台通道；任何通道不能证明受控即 BROWSER_SECURITY_NO_GO。

默认仅允许页面源站 GET/HEAD；CDN 必须有独立 host/path/type/size 资源许可，逐跳验证。
禁止 POST/PUT/PATCH/DELETE、表单提交、上传、登录、购买；阻断并记录下载、弹窗、新页面
及任意外部导航。403/验证码/WAF 立即停止该路径，不绕过。下载被阻断仍要防止网络请求
已发生，不能只在 download 事件后删除文件。移动/桌面截图限于批准的 2–3 个代表页。

## 合成安全验收矩阵（计划，尚未执行）

| 组 | 输入/虚构站点 | 期望与观测证据 | 所属 |
| --- | --- | --- | --- |
| URL | localhost、127/8、十进制/十六进制 IP、IPv6、userinfo、混淆 IDNA、%2f/%5c/%2e/双编码 | 连接前拒绝，transport 调用数 0 | A |
| DNS | 公网+私网混合 A/AAAA、重绑定、NXDOMAIN、超时、zone/mapped IPv6 | 非公网零连接；完整拒绝原因 | A |
| Pinning/TLS | resolver 第二次给内网、SNI/证书不符、peer IP 不符 | 无隐式重新解析；拒绝证书/peer 错配 | A |
| Redirect | 跨域、跨路径、metadata、循环、超限、降级、相对 Location | 每跳策略日志；未许可目的地请求数 0 | A |
| Limits | 慢流、超大 chunk、无长度、压缩炸弹、无限分页、取消/撤权 | 总 bytes/时间/页数上限；不静默重试 | A |
| Static fixtures | `factory.test` 工业目录、`catalog.test` 多 SKU、`cms.test` CMS、`spa.test` 空壳、`blocked.test` 403 | 明确 coverage；空/阻断为 UNKNOWN/ACCESS_BLOCKED | A |
| Evidence | 伪 Evidence ID、跨 run/tenant、被修改 body/hash、部分写入 | 不输出客观 FAIL；manifest 有失败原因 | A |
| Subresources | 外域 CDN、CSS url、iframe、JS fetch、重定向图片、DNS 重绑定 | 默认拒绝；批准资源走同一出口验证 | B |
| Side effects | POST 表单/beacon、WebSocket、Service Worker、WebRTC、下载、新页面 | 诱饵服务器变更计数 0，防火墙/代理日志支持 | B |
| Isolation | JS 读 metadata、内网、其它任务 profile、宿主 secret；崩溃/资源耗尽 | 内网零包、无凭据、单任务终止及清理证据 | B |

单元 mock 通过不能替代 socket/TLS/网络域集成证据；真实浏览器通过也不能替代网络层。
不允许测试为 PASS 而删除攻击向量或给生产策略增加内网例外。

## 首次真实受限站点实验的独立授权

需要单独任务单列明站点权利/使用条件、确切域名与路径、L0/L1 模式、政策版本、有效期、
robots/条款处理、请求额度/时间窗、对方停止请求渠道、数据用途与保留期、责任人与预算。
默认只做 HTTP；浏览器需另选批准页面和资源政策。先完成合成安全门禁、网络层拒绝实测、
取消/撤销验证，Owner 批准后才能访问；本轮没有网站请求、DNS 采集、截图或真实模型。

## 服务、费用与 Owner 决策

RA-1A 合成开发无必须购买的 SaaS：本地 Python、隔离容器/虚拟机、可控 DNS/假站即可。
不需要 Supabase、LLM、生产 API、VPS 或浏览器云。RA-1B 需要本地/受限 CI 的容器计算、
Chromium 存储与 CPU；若现有设备不能提供网络隔离，再单独评估沙箱供应商/预算，不先购买。
GitHub 当前账单/限额需账号 Owner 处理，不能从错误注释判断应补多少费用；任何增加限额
须由 Owner 决定。未来实网计算/流量、证据存储、人工审核成本单列，未实测金额均为未知。

仅需 Owner 决定：接受 RA-0 替代本地证据并签署安全/契约审查；恢复 CI 的账户操作；
确认 L2M 使用权或选择独立实现；另行授权 RA-1A。实网站点、RA-1B、付费服务均留到其门禁。
