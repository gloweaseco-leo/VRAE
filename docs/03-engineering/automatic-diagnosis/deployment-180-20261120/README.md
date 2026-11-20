# PR180 合并、VRAE 部署和 VF Preview 触发记录

Owner 明确授权合并、部署、私有保存 `VF_PREVIEW_DEPLOY_HOOK_URL`，并在 VF 源码标识写入成功后 POST 一次。

- PR：https://github.com/gloweaseco-leo/VRAE/pull/180
- 最终 PR head：`6b18f16921f0fab3016c3fadace5d395c6c80550`。
- 合并及实际部署源码：`6a4a41aceb361d6f93dd1580d3a570145e01854c`。
- 原实例：`vrae-windows`；沿用原 PG、报告账本、Qwen 共享费用账本及 Preview 身份。
- 本目录为部署回执，其文档提交不是运行镜像源码版本。

## VRAE 实际核验

API ready、OpenAPI、一次授权契约均返回200，响应源码标识与部署版本一致；错误 Bearer 返回403。
OpenAPI 包含 deterministic_diagnosis、analysis_outcome、capture_summary、page_scope 和 customer_presentation。
两次不带邀请的会话创建均成功且主体独立，伪造主体及错误 Bearer 均被拒绝；原已消费邀请与过期会话未恢复。
诊断443、报告8443的有效证书请求成功，错误证书、错误 Bearer 和无证书均被拒绝。
公网地址核验来自同宿主的受信操作容器，不冒称 VF BFF 出站或独立外部网络验证。

原签名采集上限仍为6页。新自动诊断版本、Guard 绑定、Qwen 提示版本与 committed_language 增量008均已核验；旧诊断默认版本保留。
23份历史采集工件全部通过原 replay_input 重放，23份 AI 回执与部署前哈希一致。
共享模型账本仍为10笔，逻辑哈希保持不变；未重置或复制。费用仍受原每日 CNY5 许可约束。
本轮没有提交客户网站、没有新增真实模型调用，也不将部署健康核验当作客户诊断验收。

私有冷备份已写入独立卷 vrae-windows-pr180-backups，文件哈希见 backup.json。
第一次升级的初始化步骤返回非零，原控制器已回滚原代码及私有许可。随后单独运行新镜像原初始化器成功，重新升级及全部实例检查通过。
第一次初始化失败的底层 stderr 未由控制器传出，具体根因尚无充分证据；没有修改迁移、跳过检查或恢复覆盖客户数据。

## VF Preview 交接

Hook 保存在 Linux 私有卷的同名键文件 VF_PREVIEW_DEPLOY_HOOK_URL，root0600；本目录仅留摘要和回执，不包含 Hook URL。
先确认 Hook 绑定 feature/vf-b-offline-g1-adapter，且与生产 main 不同。
随后更新现有 Sensitive 环境变量 VRAE_DIAGNOSIS_SOURCE_SHA 至实际合并版本；Vercel 接受写入，回读元数据确认原变量 ID、Preview 目标、分支及更新时间。
敏感值没有明文回读。更新接口首次因提交原 key 字段被 Vercel 拒绝，改为仅更新 value 后成功；拒绝请求未触发 Hook。
在上述写入成功且 VRAE 检查通过后，向私有 Hook 仅 POST 一次，返回201。私有 O_EXCL 意图文件禁止自动重复 POST，禁用重定向重发。

对应 VF Preview 部署为 READY：
https://veyfront-hf650nxnp-gloweaseco-1757s-projects.vercel.app

Preview 分支别名：
https://veyfront-git-feature-vf-b-offl-2715b7-gloweaseco-1757s-projects.vercel.app

VF 部署源码为 06b7f382641d40f957da23f7abfb96730e3b452b。此次 Hook 重部署该分支已有代码，没有修改 VF 仓库、页面或 Production 配置。
部署 READY 不证明 VF 页面已消费新 customer_presentation 或已有客户诊断完整展示，交由 Owner 独立验收。

## CI 状态

最终 PR head 的26项工作流中24项成功、2项失败，完整列表见 ci.json。
失败项为 B5A signed TEST_ONLY Reviewer original read、RA4C3 TEST_ONLY actual PG read UI；未降低测试门槛，不宣称 CI 全绿。
M2 的 Python3.13 浏览器步骤首次失败，重跑失败任务后3.11与3.13均成功；原 PG/Worker 检查通过。
实际 DNS/TLS、独立 API、Windows 公网 mTLS、Linux 持久服务与备份、工业诊断及 Qwen 原生离线协议工作流均成功。
