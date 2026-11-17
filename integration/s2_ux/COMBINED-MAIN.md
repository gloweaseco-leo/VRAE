# PR124 与 PR121 accepted main 组合验收

Owner指令：PR124#6964152145；本轮不改P1业务实现或旧安全权威。

在原 `codex2/s2-c2-p1` worktree 正常merge accepted main
`a5b8c30ccefb656c266d75e66f9f20ceb7df1080`，没有force/rebase或复制Draft。
集成merge `970ca35da7b20995deeb607ffbfd270954e799a0`，parents为
`6dc8efb8e888a6a4cff6f5d53bb1be87dfb28ee5` 与上述accepted main；
merge tree `16f405c3c314af8732eadd12de0553de06ac04ed`。

`evidence/combined-main/source-manifest.json` 记录源文件blob、工作字节/LF哈希、
父提交/tree及继承的12个accepted C1文件。17条权威/接口路径与accepted main相同，
6条P1运行/UI路径与原PR124候选相同。旧execution blob仍
`c183970fd90ec69729221a4174c38d193f4b054b`；pack blob仍
`8d45d5882103323e62bc4bd61a4379899e759966`。
清单仅用于开发审计，不是任务/来源授权或新SourceSnapshot。

新增C2自有 `test_combined_main.py`：

- 实际调用accepted `evaluate_s2/verify_s2_projection`，确认原生报告payload/hash与五维阅读不变；
  不推断BrowserPins，不把S2EvaluationProjection当成DeepReport。
- 在真实C2解析结果中篡改UNKNOWN→PASS、证据引用或JSON pointer并自重哈希，仍被独立重算拒绝。
- 投影一致性仍可重放时，原签名审阅身份撤销依旧阻止五维页读取；投影ref不恢复会话权限。

组合专项双minor各81 PASS（C1合同76 + C2组合5），原始JUnit在上述目录。
完整C2/C1/旧L2兼容集在本轮继续执行，最终状态以新HEAD回执为准。
C2自有CI加入C1合同测试和完整Git历史checkout，以原已验收Git源码进行旧行为对照，
没有改变原执行器、C1端口或旧断言。新HEAD的自然CI独立统计全部workflow/job/attempt；
旧HEAD40/40只作历史基线，不记作本轮组合通过。

富DOM P2的分层授权已收到；按Owner顺序，PR124合并后才开独立小PR做离线v2合同/producer POC。
本轮不启动P2，不把已有POC接入真实Worker/pack，不晋升ev-ref/正式规则结果。
