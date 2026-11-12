# PR56 收口 · 新 main 集成与原样重放

依据 [Owner 最终收口评论](https://github.com/gloweaseco-leo/VRAE/pull/56#issuecomment-6822250351)，没有重新开发界面。

在原 `ra3d-reviewer-p1` worktree / `codex2/ra3d-phase06-reviewer-first-p1` 分支普通 merge 已验收 main **e40201bf399cc8c5d11a708fcbe33c31f01e67b2**，无冲突，无 rebase/cherry-pick/force。

普通 merge SHA：**a46b3b15599ce407c131090782c6fcec58f890f4**。

有序父 SHA：

1. 原 PR56 功能 HEAD：151cdac7d31580afac4c5624f675cb2915c2f5e2
2. 最新已验收 main：e40201bf399cc8c5d11a708fcbe33c31f01e67b2

只在本新目录添加收口证据。原 376 个功能文件（373 个旧 P1 文件 +3 个授权 UI 文件）全部 blob/mode 不变；main 的 2628 个原始文件中，除同样三份既有 UI 差异外，**2625 个受保护文件逐 blob/mode 保留**。新 main 的 QA V1/V2、 collection transport、pyproject 默认收集约定、Docker allowlist、原生报告/Guard/held pins 保持原样。Codex1 Issue57 分支未读取或修改。

新鲜 Chromium 156、1280/375/320 ×404/200：**293 PASS /0 FAIL /0 ERROR /0 SKIP**，42 张新原始截图；原 170 +新增 123 的 ID 集与原成功运行完全相同。页面外部请求/Runtime 异常均 0。此次原始数据位于 [browser-2026-11-12T11-44-12-381Z](evidence/browser-2026-11-12T11-44-12-381Z/results.json)，所有截图、输入、CDP 日志和 stderr 均为本次执行，不复用旧成果。

`compat-293.mjs` 来自原冻结 suite，只做两项可逆路径重定位：从当前目录定位原界面/旧 suite，以及将输出移入本版本化目录。所有 293 断言、驱动、禁用门禁和预期完全不变。`suite-pin.json` 给出源/执行 SHA 与逆变换，UI 六份 snapshot SHA 与原运行一致。没有生成或改写原生报告。

- [本次 source/hash/main/QA manifest](manifest.json)
- [准备工具两次非通过记录](TOOLING_NOTES.md)
- 原比较、原非通过与原验收记录仍在上一层目录，未覆盖。

复跑与审计（仓库根）：

```text
node docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/main-e40201-finalization/prepare.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/main-e40201-finalization/compat-293.mjs
node docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/main-e40201-finalization/audit.mjs --seal
node docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/main-e40201-finalization/audit.mjs
```

最终精确 HEAD、四项新 hosted CI 的 job IDs、实际 checkout/parents/tree、V2 实际 64+54 收集与 118 passed 调用回执，在原 Draft PR56 描述回填。旧 run 43206000844 仍仅作为历史旧基线 CI，不作为本次最终门禁。

不修改 Guard/冻结 QA 或收集期望以获得 GREEN。V1 历史 RED 仍保留，默认发现规则按已验收 main 原样继承。无生产 RA3D、真实身份/人工批准、ShareGrant、客户访问、实站/模型、付费 API、部署、外发或自行合并。Human Gold 0/26；完成后保持 Draft，等待单独 Owner FINAL PASS。
