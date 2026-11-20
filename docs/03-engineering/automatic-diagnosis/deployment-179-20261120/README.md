# PR179 合并与上线记录

[PR179](https://github.com/gloweaseco-leo/VRAE/pull/179) 已按 Owner 指令合并并部署到原 VRAE 实例。
运行源码：`935d5dbb2fb58e1a8f0dbb12809be2feda7ada33`，文件树与 PR 最终 head
`b5de400e983ebc1fdf3c56af3ab0be883adcddf5` 一致。
不可变运行镜像：`sha256:25c3f7c58863972306c49956777e3f3bdff6a33d6043f8591f6d5da1db243fdf`。
上线验证完成于 2026-11-20 14:51 UTC 起。本文不代表客户业务或 VF 页面验收。

## 本次生效

- 自动任务使用 1.0.2 通用来源版本，旧定向/受控任务保留 1.0.1 默认；旧工件不改写。
- 五维确定性事实与 UNKNOWN 原因独立于 AI 成败交付，新增 page_scope 分组。
- 原根签名流程已将新自动任务授权上限从 4 页调整为 6 页，实际签名验证通过；旧计划未扩大。
- 原 Qwen provider/Guard/费用控制保持，来源 profile 版本匹配；模型失败不删除已有规则事实。
- 原人审、精确版本与定向分享继续控制正式报告，未自动批准任何客户报告。

实现与 VF 消费说明见 [五维事实](../five-task-facts/README.md) 和 [剩余范围与 V1.1 对齐](../five-task-facts/remaining-scope.md)。

## 上线验证

`verify.json`：四个服务容器运行，API/契约响应及错误身份拒绝通过；新 OpenAPI 包含
deterministic_diagnosis、page_scope、analysis_outcome、capture_summary。
原 22 份工件全部重放，22 份 AI 回执及其摘要一致，没有待处理/未记录 AI 任务；
模型配置有效，provider 出网允许地址数量为 2。

`capability.json`：直接验证实际私有 delegation 的原根签名、有效期和 6 页上限，
并核对新旧诊断版本与 Guard 版本绑定。最初运维探针误用了运行容器的 `/operator` 路径；
改为在原受控私有卷中通过同一签名验证器读取后通过，没有修改运行服务来迎合探针。

`public.json`、`session-probe.json`：同宿主容器经公开 HTTPS 验证服务、契约、错误 Bearer；
原 VF 身份不带邀请码连续创建两个独立会话均为 200，伪造主体/错误 Bearer 均为 403。
原已消费邀请及过期会话未重置。`report-probe.json` 记录诊断/报告端口八项正反检查，
包括错误证书、错误 Bearer、无证书拒绝。

正式镜像另在无网络、无生产数据/凭据挂载的容器内通过 11 项提取器/五维契约测试。
所有在线探针均未提交网站、未触发新采集、真实模型调用或人工批准；
共享模型账本仍为原 9 条记录，逻辑摘要为
`9a59d0b8664613f6c1d1e237a98d8ccd5cb01a7dba042be1fb682d8b626a2886`。
原每日人民币 5 元额度、2026-11-30 15:59:59 UTC 截止及未知费用处理均保留。

## CI 发现与修复

合并前 CI 暴露出通用版本应用过宽：旧受控站点的公共 H1 被排除，底层事实归零，
测试父进程退出后被上层记录为 API 未就绪。修复为仅自动计划选用新版本，且公共标题排除只处理多个 H1。
未放宽原事实断言、权限、超时或修改历史期望；补齐了 DISC 失败锚点的任务映射。

修复后真实 DNS/TLS 采集、独立 API、Linux 服务/冷备恢复、Windows 3.11/3.13 边界 CI 均通过。
本地最终六页 PG 链路 27 项、历史 11 项、类型 147 个文件、lint 和专项来源 8 项通过。
`ci-snapshot.json` 保留最终 PR head 的实际工作流状态：拍摄时 24 成功、1 个原有 B5A
ACCEPTED_SOURCE_CHANGED 冻结检查失败、1 个 B5-P0 尚在运行；没有声称全 CI 绿色。
原 B5A 门禁未修改或绕过。`compatibility-validation.json` 记录对应阶段与本地环境限制。

## 备份与回滚

切换前对原实例做了静止冷备份并校验归档摘要，私有输入封存于受控 Linux 卷。
备份没有复制、替换或重置共享模型账本，见 `backup.json`。
前一源码：`af8a4708102952b88f28ff0a16ad422e36592c77`；前一镜像：
`sha256:05e9744da3a59e3f08d4387574e87d5e1c0e3599e25eb73861064b3d4d12b417`。
回滚必须同时恢复匹配的模型许可源码 pin、后台 delegation 和 VF 源码 pin，不能只切换镜像。

## VF 私有交接与剩余边界

原项目、原 `feature/vf-b-offline-g1-adapter` 分支的 Preview Sensitive
`VRAE_DIAGNOSIS_SOURCE_SHA` 已更新为本次运行源码，并核对其作用域/更新元数据。
原身份、证书、私钥、Bearer 和服务期限均保留；没有导出凭据、修改 VF 代码/发布配置或触发 VF 部署。
见 `handoff.json`。

**VF 团队需自行重新部署以加载新变量，并按 #179 契约保留和展示字段。**
已构建的旧 VF 部署不会自动获得新环境变量。本轮没有验证 VF BFF 出网或浏览器页面，
也没有把报告健康检查当作已授权读取某份正式 L1；正式交付仍需真实 Reviewer 与定向分享。

VRAE 上线工作完成，等待 Owner 独立验收。
