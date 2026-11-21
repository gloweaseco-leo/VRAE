# PR181 已合并部署及 VF Preview 交接

Owner 明确授权合并部署。PR：https://github.com/gloweaseco-leo/VRAE/pull/181

- 最终验收 head：1169cb952874ac94ef8029b8109a02954844ffde。
- 合并及实际部署源码：306508cf4b6c052527aff1e8fc2ba5f87d82a99d；合并树与 head 完全一致。
- 原实例 vrae-windows 已升级，运行镜像见 build.json；本目录文档提交不是运行镜像源码版本。
- 自动新任务使用 l2-industrial-1.0.4；旧默认1.0.1及历史各版本继续保留。
- 原初始化器已追加增量009，新版本原申请语言绑定和 Qwen 提示1.3.0、Guard绑定均核验通过。

## 部署与数据完整性

部署前实例健康、无待处理任务。独立私有卷 vrae-windows-pr181-backups 保存原 PG、报告账本和密封操作材料冷备份，哈希已验证。
共享模型费用账本仅只读核对，没有复制、重置或恢复。

部署前后25份采集工件、25份AI回执的逻辑哈希完全一致，全部工件按原版本重放通过。共享模型费用账本仍为12笔、逻辑哈希相同。
此前PR180部署时的23份工件/10笔模型账目不是本次基线；Owner之后的真实诊断产生的新增结果完整保留。

API ready、OpenAPI、一次授权契约均200，响应绑定实际部署源码；错误Bearer为403。
新的无需邀请会话可创建，两个主体相互独立；伪造主体、错误Bearer被拒绝，历史邀请与已过期会话未恢复。
诊断443与报告8443的有效mTLS请求200，错误Bearer、错误证书或无证书均被拒绝。
原六页签名上限、证书、角色、费用许可和每日CNY5上限保持不变。

公网地址探测来自同宿主受信容器，不冒称独立网络或VF BFF的结果读取端到端验收。
本轮没有提交客户网址、没有新增真实模型调用或人工审批，不把健康核验当作修复后新报告验收。

## VF Preview

现有Sensitive变量 VRAE_DIAGNOSIS_SOURCE_SHA 已写入上述实际合并SHA；接口接受写入，回读元数据确认原变量ID、Preview目标、指定分支及更新时间，没有明文回读秘密。
沿用Linux私有卷root0600文件 VF_PREVIEW_DEPLOY_HOOK_URL；确认绑定 feature/vf-b-offline-g1-adapter，生产分支main未触发。
所有VRAE检查及源码写入通过后，仅POST一次，返回201。私有O_EXCL意图文件阻止重复POST，禁止自动重试和重定向重发。

对应Preview已READY，新地址：
https://veyfront-6powyx75d-gloweaseco-1757s-projects.vercel.app/website-diagnosis

部署ID：dpl_EKoWPtGTr8NqHwFgE87RHgZW5kcY。
VF源码：cafe11376cb5bbd95305094d2273e152b2bc8c0f，仍为此前的结果读取20秒修复。
没有修改VF仓库、页面或Production。该版本尚未接入PR181五维适配器，因此不能把READY写成五维页面已完成。

VF接入材料：[产品归属与五维交付](../product-scope-and-five-task-delivery/README.md)。
需要在BFF、前端状态和五维主体保留并展示buyerTasks等字段；新Hook部署只加载现有代码及更新后的来源标识，不替代VF的页面接入。
验收使用本次新Preview；旧构建地址保留旧构建配置。归属修复用于新诊断任务，历史报告仍按原版本读取，未被静默重写。

## 检查记录

最终head的26项工作流中25项成功。B5A signed TEST_ONLY Reviewer original read失败于原publication.py的旧源码冻结断言 ACCEPTED_SOURCE_CHANGED；已核对日志，原测试门槛保持不变，没有宣称CI全绿。
本次关键API、DNS/TLS、Windows边界、实际PG新版本协议、持久Linux服务及冷备份、Qwen原生离线协议均通过。
完整列表见ci.json，部署后实际检查见各JSON回执。等待Owner独立验收。
