# RA-1B B6：Worker SIGKILL 后自动退出可靠性

Owner于2026-11-11授权最小收口。重新fetch后main仍为
`8bc460764dedb6a87c2e7806b2d3b382875596de`，分支原HEAD为
`3e46fd47a36286c2ce280b651627a46964b3e734`，未覆盖原提交。

## 根因与修复范围

失败run42968878052在Worker退出约79ms后做一次inspect；相同实现的
run42969519632约102ms检查时成功。这两次历史记录不能单独证明Agent永远可靠。
代码审查发现原监督脚本把异步退出契约误写成即时状态断言：
Agent收到Unix EOF后调用child.kill，另一协程通过线程执行child.wait，
回到事件循环后退出PID1；Docker随后才完成容器状态转换。
Worker的docker run返回不构成上述流程完成的同步屏障。

本次只改变`scripts/verify_ra1b.py`的退出确认：使用`docker wait`等待状态收敛，
整个命令最多5秒。它不发送信号、不停止容器；超时仍为SECURITY_BLOCKED，
finally可强制清理但不能把失败变为通过。原Agent生命周期机制未改动，
`infra/ra1b/agent.py`只增加单调时钟日志。无固定sleep修复、重试成功策略或安全策略变更。

新增检查：退出后Running=false、Pid=0、docker top无运行进程；删除后容器和IPC卷均不存在。
Chromium主进程由child.wait回收，其余后代由独立PID namespace的PID1退出触发内核终止回收；
Docker停止状态/Pid0及top失败在强制删除前确认，不能把docker rm当作自动退出证明。
“自然/自动退出”指Agent自行终止Chromium并退出，无监督器停止介入；
Agent发SIGKILL导致Chromium=-9、容器exit1是现有预期，不表示进程自行正常exit0。

## 连续真实专项

命令：`python scripts/verify_ra1b.py <独立证据目录> --cases worker_kill`。
在Docker Desktop4.59.0 / Engine29.2.0 / Linux amd64上连续20次运行，
每次均新建容器、Profile和tmpfs IPC卷；20通过、0失败、0跳过。
最慢docker wait命令确认耗时0.656秒；最慢Agent EOF→PID1退出前日志0.728933秒。
每次保留Worker强杀137、攻击触发、诱饵0/写入0、Sandbox、socket EPERM、资源限制及清理证据。

示例第1次有效专项（b6-special-02）Agent单调时钟：

| 事件 | monotonic_ns | 相对EOF |
|---|---:|---:|
| Unix EOF | 1106574265908 | 0ms |
| relay断开 | 1106574426919 | 0.161ms |
| Chromium终止信号发出 | 1106574471246 | 0.205ms |
| socket关闭请求 | 1106773724211 | 199.458ms |
| Chromium wait回收完成 | 1106974341267 | 400.075ms |
| PID1退出前 | 1106974554016 | 400.288ms |

该次Supervisor记录Worker退出→docker wait返回约515ms；Docker确认非Running、Pid0、
top无进程后才进入删除阶段。Windows宿主和Linux VM时钟起点不同，不能跨两者直接相减。
这些实测证明有限但非零的异步收敛时间，支持“即时检查竞态”的修复判断；
不声称能从旧日志还原历史79ms时刻的所有内核调度细节。

最初b6-special-01因执行沙箱不能读Docker配置/pipe而失败，尚未运行攻击，原始日志保留；
经权限流程授权后才开始20次有效专项。首次选用RA-0 venv缺h11，未启动回归；
改用原RA-1A venv，没有改依赖。Python3.11.15/3.13.13各425通过、0失败、25环境限定跳过；
compileall、Ruff、mypy、pip check全部exit0。全部原RA-0/RA-1A测试与安全负例保留。

## 证据与最终门禁

[b6-summary.json](ra1b-evidence/b6-summary.json)含20次逐事件时间线、精确命令与源码SHA256，
[b6-raw.zip](ra1b-evidence/b6-raw.zip)含438份原始日志、配置、摘要及归档脚本；
归档SHA256 `2619274f5951e8d0b4df9e10f907e6b11473b7fa31f84bbc4dc79befef89ae0d`。
原失败[日志](ra1b-evidence/hosted-final-browser-failure.log)未删除；
相同旧实现后来成功的[日志](ra1b-evidence/b6-prior-success-browser.log)另存，不覆盖失败。

专项通过后，提交本修复触发一次完整四作业CI：Python3.11、Python3.13、isolated-http、
isolated-browser（含全部16场景）。最终SHA、run/job、四份真实日志及结果记录在
[Draft PR #6](https://github.com/gloweaseco-leo/VRAE/pull/6)，避免为记录CI结果循环产生新提交。
本文件提交时不预判该次CI；只有最终SHA四个作业实际成功且上述门禁全部满足，
才可标记 **RA-1B FINAL PASS CANDIDATE**，否则继续 **SECURITY_BLOCKED**。

审计：产品代码、RA-1A、契约、测试攻击集、Sandbox/Seccomp/网络/权限/资源限制未改；
没有新框架、服务、采购、数据库、生产调度或RA-2代码。
剩余生产能力和隐私/供应链风险沿用原最终审计，20次有限样本不是所有环境的可靠性证明。
停止在Draft，最终签署由Owner决定；不合并、不部署、不进入RA-2。
