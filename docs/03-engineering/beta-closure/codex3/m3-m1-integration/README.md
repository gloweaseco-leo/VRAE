# M3：已验收 M1 的实际集成证据

本次代码验收 SHA：`77aa6177e6c15495412a422adc0c6a01b6bde5b6`。
正常合并 `08a999d8b7061af925f1f35cfcc55193a3c73b35` 的 merge 为
`db514e19013a8e1b7e888b0cc3dfa64351a1526e`，保留原 HEAD
`2defba323f8b83c1106e577e4750a5cf22abff46` 的历史。
本目录在验收结束后作为证据提交加入；不会把证据提交的 HEAD 冒称为原测试 HEAD。
证据提交不改变可执行文件。双版本 source-manifest 完全一致，根为
`9d4bc2092a4899c477fbe982f03219e803a96ca2a4baf3a454ec10978f3daa13`。

| 本机 / 低权限 Linux Worker Python | 原始 pytest | 结果 |
|---|---|---|
| 3.11.15 / 3.11.17 | [311/tests.xml](311/tests.xml) | 12/12 |
| 3.13.13 / 3.13.18 | [313/tests.xml](313/tests.xml) | 12/12 |

12 项中 7 项为 PG16/API/实际 M1 Worker/当前授权/浏览器/重启集成，
5 项为独立启动控制测试。`component-stages.xml` 只是控制器阶段日志，不能重复计为 pytest。
原始 JUnit 直接按字节复制，SHA256/CRC32 见 [manifest.json](manifest.json)。

实际验证从零新建、APP202 提交 404/200、原顺序 claim、真实采集与规则/Guard/报告生成、
事务持久化及签名当前任务读取。任务、来源、报告版本同源；启动时新结果为零。
同时验证相同幂等键复用任务、撤销当前分配后即使文件已缓存也拒读、实际 PG 重启且
不重新迁移/灌入报告、两个任务的 source/report/HTML 原字节一致，以及本机 Chrome
查看真实未批准 HTML、截图与浏览器退出。每轮所有自有资源清理通过，监督器 exit0，
保留真正 fatal/进程观测，未发现归属于本轮的 WER 崩溃或意外 SSR 退出。

首轮开发 RED 与其后修复开发轮的原始 JUnit 保存在原 `.private`，哈希列入 manifest。
首轮重启适配器没有刷新 Docker host port，未记录该轮重启后的实际映射；后续开发轮
实际观测到旧/新端口不同，并复用已验收 refresh_port。首轮还重复观测了已主动停止的
SSR；现在按实际进程对象记录主动停止，保留自然退出/真实崩溃检查。不能把首轮观测
误分类当成已确证的 Windows 原生崩溃，也不能覆盖任何历史 RED。

这里只发布白名单摘要、哈希与原始通过 JUnit，不发布源文档、报告 HTML、签名私钥、
token、数据库凭据或截图内容。原控制器在保留内存凭据时完成其发布目录的精确扫描；
原清理会移除管理状态文件。此目录再次检查仍保留的 Reviewer 凭据与签名材料，匹配零。

当前为 `M1_READY_M2_UI_PENDING`，不是整机 FINAL PASS。PR103 尚未 Owner 合并；
没有加载其代码。唯一 SSR 的 sealed 旧任务页不与新任务冒充关联；新报告诊断 HTML
不代表 M2 审核、持久回执、A4 或人工审批。后续在 M2 合并后完成同 SHA 完整链。
旧 A1/MAX3、历史 dump 和 RED 继续冻结；没有重新运行旧灾备专项、合并或部署。

操作入口见 [LOCAL_APPLICATION.md](../LOCAL_APPLICATION.md)。
本次 Draft 的 GitHub CI 链接与实际结论在 PR 回执单独记录；原有 CI 不等于执行了
此处 Windows 本机 M3 用例，没有修改原 CI 或添加未经授权的新 workflow。
