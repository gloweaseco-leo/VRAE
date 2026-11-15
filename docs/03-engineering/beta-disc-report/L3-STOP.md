# S1 L3 STOP：新增原生测试与旧 B4 CI 固定总数冲突

已回读 Issue94 / Issue97 最新正文；执行基线与远端 main 均为
`447005b2951f43e8d8643632d663de268f278329`。独立 worktree：
`D:/Projects/VRAE/.worktrees/beta-disc-report-v1`，分支
`codex1/beta-disc-report-v1`。未导入任何未合并兄弟分支。

## 实际阻断

原生 `pytest --collect-only -q` 实收 **2519** 项，其中新增获准路径
`tests/reporting/beta_disc_report/` **46** 项，其余 **2473** 项。

现有 `.github/workflows/ra4b-p1.yml` 直接执行
`docs/03-engineering/ra4b-p1/unit_lab.py`；后者第 136 行固定：

```python
assert len(cases) == 2473 and len(skipped) == 25
```

因此即使新增源码和所有 pytest 测试全部通过，现有 B4 双 minor 作业仍会在
主机侧原生 JUnit 保留校验处失败。这是**源码与实际收集结果的只读前检结论**，
不是已经运行过的 GitHub CI 失败，也不是权限或事务安全失败。

Issue94 明确规定“需要改冻结断言，立即只读诊断 STOP”；Issue97 将旧 CI 列为
受保护边界。没有把 46 项移出完整发现，没有添加跳过，没有改此断言，没有
修改任何旧 workflow、SQL、Worker、migration、角色或 ACL。

## 提交 Owner 的最小差分方案（尚未实施）

仅扩展 `unit_lab.py` 的完整发现验收清单，精确接纳本轮新增的 46 个测试 ID：

1. 原 2473 个 ID 仍须逐项存在，原 25 个 SKIP 的精确归属、QA118、Review127、
   零 failure/error、原生 XML 及清理后 SHA/CRC 校验全部保留。
2. 新增 46 个 ID 单独固定清单与来源哈希，不接受任意新增或替换 ID。
3. 精确全集为 2519；通过数应由实际 JUnit 得出，不能预填为测试通过。
4. 若 Owner 在恢复前合入其他已验收 main，则按该精确新基线先回读清单，
   不能继续硬套这里的 2519 或历史 2473。

需要 Owner 明确允许上述旧 CI 验收清单兼容差分；当前没有实施权限。

## 已有实物与证据界限

- 已实现新版本 DISC Guard、报告及离线原生输入生成器；受保护 Guard 仅有
  显式版本分支。旧 `draft.py/renderer.py` 的 Git 内容差分为零。
- 八个真实合成案例完成 EvidencePack → 显式六规则 → FindingPackage →
  新 Guard → 私有 HTML → 不变字节回读；完整源链均在私有目录。
- Chromium：24 个视图（1280/375/320）、48 次实际证据回查点击、外部请求 0，
  私有标签／无可执行内容／无启用动作／单页打印检查通过。
- CI 同口径 Ruff 和 mypy 通过。上述不等于双 Python 全量通过。
- Python3.11/3.13 全量在约 22% 时因本 L3 STOP 主动终止；两者未形成完整
  JUnit，不能申报全量 PASS。所有后续 PG/CI 检查未执行，不能标 PASS。
- 首次路由方案触发冻结 `draft.py` 源码哈希的 collection RED，原生
  `related-py311.xml` 和当时差分保留。改用获准新版目录后保留旧文件和预期哈希。
  初次新增测试的输出字段错误及中断试跑也不计为验收通过。
- 原始 RED、旧 B4-P2 checkpoint、冻结测试、预期哈希均保留。

本轮提交／推送／Draft PR／GitHub CI 均为 0。无合并、部署、真实审批或分享。
S1 未验收，S2 未启动；B1/B2 仍为 2/7、Gold 0/26、G1/G2/G3 NO-GO。
