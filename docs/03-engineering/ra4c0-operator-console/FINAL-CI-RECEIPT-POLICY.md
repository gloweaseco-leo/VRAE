# 精确最终 HEAD 回执

在最终 CI 推送前提交应用、测试、合成 fixture、原始本地 JUnit/日志、截图、来源封存、限制和本说明。核对最新已验收 main，只做普通 merge。没有 rebase、强推、额外 infra 修改或测试选择/预期变更。

最终四项真实 GitHub CI 完成后，下载原始 run/jobs、Draft PR、真实 Git merge 对象、四项原始 checkout 日志，以及原始 `ra1b-synthetic-security-evidence` ZIP。核验精确 HEAD、已验收 main、merge-ref 顺序父 SHA、64+54 实际 QA 调用结果、原始网络/容器负例、P1 原用例及所有日志哈希。

这些 **post-CI 回执**保留在本授权目录的 `evidence/hosted-<run>-<UTC>/`，故意不再提交，以保持被四项 CI 检验的精确 Draft HEAD。最终 PR body 提供 HEAD/main/merge-ref、全部 job/artifact 链接、计数、哈希和限制；本地原始 ZIP 与回执保持可回查。不会为把回执自身写进 Git 而再制造一个未经同轮 CI 检验的新 HEAD。这与已验收 PR #48、PR #58 的精确 HEAD 回执协议一致。

每份本地记录保留实际开始 SHA，旧基线全量 JUnit 不改称新 main 结果。新 main 的双 Python 默认全量由最终四项 hosted CI 执行；本地补充应用/P1/原生回放和三尺寸浏览器按合入后源码实测。所有应用 blob 与源码哈希可对照封存记录。

保持 Draft，不自动合并或部署。四绿只代表工程候选，不代表 Owner FINAL PASS、真实人工审批或客户分享。真实身份、数据库、ShareGrant、客户访问和付费模型调用仍未实现。
