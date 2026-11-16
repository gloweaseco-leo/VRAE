# VEYFRONT 内部合成诊断：浏览器 L0 → L1 操作

已验收基线：`df5428c503f22a86429b2b9a4263551776d7253a`（M1、TaskClient、M2 已合并）。
本入口启动现有 PG16、原 API、独立低权限正式 M1 Worker 和唯一 M2 签名 SSR。
只处理固定的合成制造业404/200来源。内部决定保留 NOT_APPROVED，不构成正式人审或外部交付。

## 准备一次本机环境

从当前已冻结候选的仓库根目录运行。需要 Docker Desktop、Python3.11或3.13、Node22+、Chrome。
已有锁定环境和 `vrae-ra4b-p1:311` 镜像时跳过环境准备。

```powershell
py -3.11 -m venv integration/beta_review/codex3/.private/operator311
integration/beta_review/codex3/.private/operator311/Scripts/python.exe -m pip install -r requirements-ra4b-p1.lock
integration/beta_review/codex3/.private/operator311/Scripts/python.exe docs/03-engineering/ra4b-p1/runtime_lab.py m3-build-311-once --build-only --private-output
```

此处 build-only 只建立已验收的锁定运行镜像，不执行旧验收专项。标签需唯一。
后续用该环境的 python，或已配置同样锁定依赖的 python。3.13需用3.13环境构建`:313`镜像。
Chrome默认路径为`C:/Program Files/Google/Chrome/Application/chrome.exe`；
如不同，在本机设置`B5B_CHROMIUM`为实际Chrome路径。

## 启动与打开浏览器

每个 run 名称只用一次，限小写字母、数字、短横线（3–48字符）。

```powershell
python scripts/beta_internal.py app doctor
python scripts/beta_internal.py app start --run veyfront-synthetic-001 --minor 3.11
python scripts/beta_internal.py app status --run veyfront-synthetic-001
```

等待`M3_READY`，status给出本轮实际`127.0.0.1`地址。启动时会用真实APP202和正式Worker
生成两个当前已分配的合成身份入口任务；它们不是预制报告，也不是后续操作员新提交的任务。
然后运行受控合成Reviewer签名助手：

```powershell
python scripts/beta_internal.py app open --run veyfront-synthetic-001
```

保留这个终端，Chrome会打开“提交新的合成制造业诊断”。签名助手只处理服务器实际发出的
一次性挑战；签名私钥留在启动器内存中，API bearer与Reviewer密码不会进入网页。
不需要在浏览器复制token、数据库身份或私钥。

## 在页面完成一次新业务

1. 选择“制造业·联系路径404”或“制造业·静态路径200”，点击“提交新诊断任务”。
2. 页面显示本次真实APP202的request/run/job与来源，以及PENDING。Worker自动执行；
   点击“刷新任务状态”直到TEST_ONLY_DONE。刷新与Worker写入由本机启动器协调，原权限和预算不变。
3. 点击“签名打开本次新生成报告”。签名助手完成新的受控挑战后，查看本次任务的中文L1、
   Evidence、Guard、来源、报告版本与文件/内容哈希。DONE本身不作为报告读取授权。
4. 对整份报告和每个有据问题选择“内部批准／拒绝／修订”。修订需填写说明。
   点击“保存本版本内部回执”，确认显示“已持久化”及回执标识。
5. 点击中文A4入口，查看带“合成样本·内部审核·禁止外发”标识的审阅稿。
   用Chrome打印功能选择A4、另存为PDF、关闭浏览器页眉页脚；样式提供单页投影。
6. 返回任务列表，换另一种来源再提交。200应显示0个有据问题和证据不足，不能据此判断网站健康、
   表单送达或询盘成功；仍可保存针对覆盖摘要的内部决定。

签名会话沿用原短有效期，导航不会延长。过期时拒绝读写，助手会重新认证并回到任务列表；
需重新打开同一任务取得新挑战，不自动重放审核提交。关闭Chrome可结束助手，服务保持运行，
可再次执行open。整个隔离运行有原有约30分钟自动清理上限。

## 重启后回读

队列空闲时，在另一个终端执行：

```powershell
python scripts/beta_internal.py app restart-pg --run veyfront-synthetic-001
```

该命令真正重启PG、API、Worker和唯一SSR，更新私有HTTP身份及公开签名锚，保留任务路由卷。
不会重新迁移、灌报告或改审核回执。队列忙时拒绝重启。
等待命令完成后，在浏览器刷新。旧会话会被拒绝；助手重新认证后，从“当前Reviewer的已提交任务”
选择原任务，重新签名打开，核对原job、版本和报告哈希，再查看原持久回执及其A4。

## 停止与验收

```powershell
python scripts/beta_internal.py app stop --run veyfront-synthetic-001
python scripts/beta_internal.py app status --run veyfront-synthetic-001
```

等待`CLOSED`和正常结果；STOP_REQUESTED不代表清理已完成。正常停止会清理本轮隔离数据库、
进程、容器、网络和卷，操作前如需保留A4，请先保存本机PDF。原历史RED/dump/A1/MAX3不受影响。

受控自动验收使用同一个入口、真实Chrome鼠标/键盘事件，在1280/375/320完成两种新来源、
三种内部决定、持久回执、A4与两次真实重启：

```powershell
python scripts/beta_internal.py app verify --run <另一个已M3_READY的新run>
```

verify每个run只执行一次，原生pytest整体验收入口为
`integration/beta_review/codex3/m3_business_cases.py`，设置唯一`M3_RUN`和`M3_MINOR`。
截图、PDF、原始JUnit与私有日志留在C3`.private`；只有明确筛选、扫描的证据公开。
旧的`--component-preview`及程序化M1模式仅作历史兼容，不是当前M3业务入口。

## 集成边界

唯一业务SSR为已验收`b5b_http.Application(...generated=...)`，UID10003，仅持Reviewer凭据、
公共JWKS及独立HTTP服务bearer。PG/API/SSR共用受控loopback命名空间；宿主机有限转发只搬运
该SSR的请求/响应，不渲染页面、不执行审核、不建立第二业务站点。APP/Worker数据库配置不进入SSR。
Worker UID10002只执行正式M1 CLI，原claim顺序、租约、SQL/RLS、Guard与HTTP/CDP预算保持不变。
所有输出来自本次实际Worker；签名读取仍要求当前分配、来源、epoch和原字节重放。
