# VRAE 安全收口提案 · 只审批，不执行 · Issue #175

**Phase A结束后停止。当前删除/移动/归档/环境变更授权均为0；实际释放0。**
推荐先完成VF真实联调，或由Owner明确指定不影响联调的窗口，再对下面的规范化路径逐项批准；不能批量按名称/日期/VRAE前缀处理。

## 可释放空间的保守口径

已观察97个单元的文件逻辑长度合计52.007 GiB；活动树、私有子树、卷容量未知。
D组3项逻辑长度合计 **0.364 GiB / 372.90 MiB**，是当前最窄候选载荷估算；实际分配空间、共享硬链接与删除后释放量UNKNOWN。
其他A/B/C/E本轮不计入可释放空间。缓存/venv看起来大也可能被脚本、解释器或离线证据链依赖，不能把其全部大小当作安全可删量。

## D组逐项候选

下面只证明观察到的版本化内容可由保留的main/object store恢复、无非缓存local-data状态条目，以及已查运行面无引用。
尚未做Phase B归档/恢复演练、Owner逐项批准或执行前重查；linked worktree必须走未来经批准的Git管理流程，不能直接删文件夹或共享.git。

| ID | 唯一具体路径 | 载荷MiB | 判定证据 | 误删后果与执行前条件 |
| --- | --- | ---: | --- | --- |
| P011 | `D:/Projects/VRAE-Codex2/.worktrees/ci01-standard-time-budget` | 346.18 | HEAD `7928614fd297` 是实时main祖先；T/U/I=0/0/0；尺寸完整，无已观察运行引用 | 丢失本地checkout/可再生缓存及Git worktree配置；先核对未变化、无新引用并记录恢复方式，Owner单独批准 |
| P019 | `D:/Projects/VRAE-Codex2/.worktrees/l2-s4-ci-scope` | 0.04 | HEAD `4b18148c5e2f` 是实时main祖先；T/U/I=0/0/0；尺寸完整，无已观察运行引用 | 丢失本地checkout/可再生缓存及Git worktree配置；先核对未变化、无新引用并记录恢复方式，Owner单独批准 |
| P027 | `D:/Projects/VRAE-Codex2/.worktrees/ra3d-phase0` | 26.68 | HEAD `77c14bbf5a43` 是实时main祖先；T/U/I=0/0/0；尺寸完整，无已观察运行引用 | 丢失本地checkout/可再生缓存及Git worktree配置；先核对未变化、无新引用并记录恢复方式，Owner单独批准 |

## A/B/C/E的逐项处理建议

| ID | 路径 | 分组 | 证据/建议 | 本轮计入释放量 |
| --- | --- | --- | --- | ---: |
| P001 | `D:/Projects/VRAE` | A | 运行/启动路径引用，或共享Git根；不可动；观察载荷0.823 GiB，仅作盘点，不等于释放量 | 0 |
| P002 | `D:/Projects/VRAE-Beta-Owner` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.394 GiB，仅作盘点，不等于释放量 | 0 |
| P003 | `D:/Projects/VRAE-Codex2` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.171 GiB，仅作盘点，不等于释放量 | 0 |
| P004 | `D:/Projects/VRAE-Codex2/.worktrees/.b7-main-sync-evidence` | C | Git外历史证据目录；先保全归档核验，未断言全局唯一；观察载荷0.001 GiB，仅作盘点，不等于释放量 | 0 |
| P005 | `D:/Projects/VRAE-Codex2/.worktrees/.ci01-evidence` | C | Git外历史证据目录；先保全归档核验，未断言全局唯一；观察载荷0.001 GiB，仅作盘点，不等于释放量 | 0 |
| P006 | `D:/Projects/VRAE-Codex2/.worktrees/b3p0` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷0.721 GiB，仅作盘点，不等于释放量 | 0 |
| P007 | `D:/Projects/VRAE-Codex2/.worktrees/b5-oracle447` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷2.758 GiB，仅作盘点，不等于释放量 | 0 |
| P008 | `D:/Projects/VRAE-Codex2/.worktrees/b5b` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷1.135 GiB，仅作盘点，不等于释放量 | 0 |
| P009 | `D:/Projects/VRAE-Codex2/.worktrees/b6-resume-lf` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷0.643 GiB，仅作盘点，不等于释放量 | 0 |
| P010 | `D:/Projects/VRAE-Codex2/.worktrees/b6p0` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷0.771 GiB，仅作盘点，不等于释放量 | 0 |
| P012 | `D:/Projects/VRAE-Codex2/.worktrees/g1-c3-12b-audit` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.020 GiB，仅作盘点，不等于释放量 | 0 |
| P013 | `D:/Projects/VRAE-Codex2/.worktrees/g1-vfb-http-consumer` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷0.513 GiB，仅作盘点，不等于释放量 | 0 |
| P014 | `D:/Projects/VRAE-Codex2/.worktrees/l1-experience` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.467 GiB，仅作盘点，不等于释放量 | 0 |
| P015 | `D:/Projects/VRAE-Codex2/.worktrees/l2-deep-audit` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷0.468 GiB，仅作盘点，不等于释放量 | 0 |
| P016 | `D:/Projects/VRAE-Codex2/.worktrees/l2-executive-vf` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.521 GiB，仅作盘点，不等于释放量 | 0 |
| P017 | `D:/Projects/VRAE-Codex2/.worktrees/l2-launch-r0` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷0.539 GiB，仅作盘点，不等于释放量 | 0 |
| P018 | `D:/Projects/VRAE-Codex2/.worktrees/l2-native-report` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷0.450 GiB，仅作盘点，不等于释放量 | 0 |
| P020 | `D:/Projects/VRAE-Codex2/.worktrees/ra2b3` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.173 GiB，仅作盘点，不等于释放量 | 0 |
| P021 | `D:/Projects/VRAE-Codex2/.worktrees/ra2b5` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.014 GiB，仅作盘点，不等于释放量 | 0 |
| P022 | `D:/Projects/VRAE-Codex2/.worktrees/ra2b6` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.021 GiB，仅作盘点，不等于释放量 | 0 |
| P023 | `D:/Projects/VRAE-Codex2/.worktrees/ra2c1` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.013 GiB，仅作盘点，不等于释放量 | 0 |
| P024 | `D:/Projects/VRAE-Codex2/.worktrees/ra2c3-qa` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.026 GiB，仅作盘点，不等于释放量 | 0 |
| P025 | `D:/Projects/VRAE-Codex2/.worktrees/ra3b` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.038 GiB，仅作盘点，不等于释放量 | 0 |
| P026 | `D:/Projects/VRAE-Codex2/.worktrees/ra3c` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.194 GiB，仅作盘点，不等于释放量 | 0 |
| P028 | `D:/Projects/VRAE-Codex2/.worktrees/ra3d-phase05` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.097 GiB，仅作盘点，不等于释放量 | 0 |
| P029 | `D:/Projects/VRAE-Codex2/.worktrees/ra3d-phase06` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.122 GiB，仅作盘点，不等于释放量 | 0 |
| P030 | `D:/Projects/VRAE-Codex2/.worktrees/ra3d-reviewer-p1` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.246 GiB，仅作盘点，不等于释放量 | 0 |
| P031 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c-b5a` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.723 GiB，仅作盘点，不等于释放量 | 0 |
| P032 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c-b5p0` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷1.002 GiB，仅作盘点，不等于释放量 | 0 |
| P033 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c0` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.313 GiB，仅作盘点，不等于释放量 | 0 |
| P034 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c1` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.283 GiB，仅作盘点，不等于释放量 | 0 |
| P035 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c2` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.330 GiB，仅作盘点，不等于释放量 | 0 |
| P036 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c3` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.669 GiB，仅作盘点，不等于释放量 | 0 |
| P037 | `D:/Projects/VRAE-Codex2/.worktrees/ra4e-b7p0` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.449 GiB，仅作盘点，不等于释放量 | 0 |
| P038 | `D:/Projects/VRAE-Codex2/.worktrees/s2-buyer-cards` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.454 GiB，仅作盘点，不等于释放量 | 0 |
| P039 | `D:/Projects/VRAE-Codex2/.worktrees/s2-buyer-workbench` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.463 GiB，仅作盘点，不等于释放量 | 0 |
| P040 | `D:/Projects/VRAE-Codex2/.worktrees/s2-c2-p1` | B | 开放PR或未提交/远端可达性风险；不可动；PR #124；观察载荷0.830 GiB，仅作盘点，不等于释放量 | 0 |
| P041 | `D:/Projects/VRAE-Codex2/.worktrees/s2-chrome-d0` | B | 开放PR或未提交/远端可达性风险；不可动；PR #127；观察载荷0.445 GiB，仅作盘点，不等于释放量 | 0 |
| P042 | `D:/Projects/VRAE-Codex2/.worktrees/s2-cta-slice` | B | 开放PR或未提交/远端可达性风险；不可动；PR #141；观察载荷0.557 GiB，仅作盘点，不等于释放量 | 0 |
| P043 | `D:/Projects/VRAE-Codex2/.worktrees/s2-ux-browser` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷0.483 GiB，仅作盘点，不等于释放量 | 0 |
| P044 | `D:/Projects/VRAE-codex3-API-20261119` | A | 运行/启动路径引用，或共享Git根；不可动；PR #172；观察载荷UNKNOWN_PROTECT GiB，仅作盘点，不等于释放量 | 0 |
| P045 | `D:/Projects/VRAE-codex3-B7A1` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷3.326 GiB，仅作盘点，不等于释放量 | 0 |
| P046 | `D:/Projects/VRAE-codex3-B7A1-Resume-20261115` | B | 开放PR或未提交/远端可达性风险；不可动；2个远端heads/tags不可达提交先保存并验证可恢复；观察载荷2.744 GiB，仅作盘点，不等于释放量 | 0 |
| P047 | `D:/Projects/VRAE-codex3-B7P1` | A | 运行/启动路径引用，或共享Git根；不可动；观察载荷1.097 GiB，仅作盘点，不等于释放量 | 0 |
| P048 | `D:/Projects/VRAE-codex3-B7Restore-v1-20261115` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.392 GiB，仅作盘点，不等于释放量 | 0 |
| P049 | `D:/Projects/VRAE-codex3-BetaGold-20261114` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.381 GiB，仅作盘点，不等于释放量 | 0 |
| P050 | `D:/Projects/VRAE-codex3-BetaIntegration-20261114` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.394 GiB，仅作盘点，不等于释放量 | 0 |
| P051 | `D:/Projects/VRAE-codex3-Delivery-20261119` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.020 GiB，仅作盘点，不等于释放量 | 0 |
| P052 | `D:/Projects/VRAE-codex3-G1-20261118` | A | 运行/启动路径引用，或共享Git根；不可动；观察载荷≥0.485 GiB，仅作盘点，不等于释放量 | 0 |
| P053 | `D:/Projects/VRAE-codex3-L2-20261116` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.405 GiB，仅作盘点，不等于释放量 | 0 |
| P054 | `D:/Projects/VRAE-codex3-L2-UAT-20261118` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.484 GiB，仅作盘点，不等于释放量 | 0 |
| P055 | `D:/Projects/VRAE-codex3-L2Integration-20261116` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.453 GiB，仅作盘点，不等于释放量 | 0 |
| P056 | `D:/Projects/VRAE-codex3-L2Launch-20261118` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.484 GiB，仅作盘点，不等于释放量 | 0 |
| P057 | `D:/Projects/VRAE-codex3-S2Quality-20261117` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.544 GiB，仅作盘点，不等于释放量 | 0 |
| P058 | `D:/Projects/VRAE-codex3-S5-20261118` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.548 GiB，仅作盘点，不等于释放量 | 0 |
| P059 | `D:/Projects/VRAE-codex3-Targets-20261119` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.020 GiB，仅作盘点，不等于释放量 | 0 |
| P060 | `D:/Projects/VRAE/.worktrees/beta-disc-report-v1` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷2.726 GiB，仅作盘点，不等于释放量 | 0 |
| P061 | `D:/Projects/VRAE/.worktrees/beta-quality-20261114` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.391 GiB，仅作盘点，不等于释放量 | 0 |
| P062 | `D:/Projects/VRAE/.worktrees/beta-s2-generated-result-bridge` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.479 GiB，仅作盘点，不等于释放量 | 0 |
| P063 | `D:/Projects/VRAE/.worktrees/ci-tiered-313` | B | 开放PR或未提交/远端可达性风险；不可动；PR #133；观察载荷0.475 GiB，仅作盘点，不等于释放量 | 0 |
| P064 | `D:/Projects/VRAE/.worktrees/evidence-pack-perf` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.477 GiB，仅作盘点，不等于释放量 | 0 |
| P065 | `D:/Projects/VRAE/.worktrees/g1-s1-security` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.503 GiB，仅作盘点，不等于释放量 | 0 |
| P066 | `D:/Projects/VRAE/.worktrees/l2-industrial-buyer` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.457 GiB，仅作盘点，不等于释放量 | 0 |
| P067 | `D:/Projects/VRAE/.worktrees/qwen4-buyer-candidate` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.503 GiB，仅作盘点，不等于释放量 | 0 |
| P068 | `D:/Projects/VRAE/.worktrees/r1a-offline-security` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.495 GiB，仅作盘点，不等于释放量 | 0 |
| P069 | `D:/Projects/VRAE/.worktrees/ra2b4` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.016 GiB，仅作盘点，不等于释放量 | 0 |
| P070 | `D:/Projects/VRAE/.worktrees/ra2c2` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.016 GiB，仅作盘点，不等于释放量 | 0 |
| P071 | `D:/Projects/VRAE/.worktrees/ra2c3` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.022 GiB，仅作盘点，不等于释放量 | 0 |
| P072 | `D:/Projects/VRAE/.worktrees/ra2d0` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.012 GiB，仅作盘点，不等于释放量 | 0 |
| P073 | `D:/Projects/VRAE/.worktrees/ra2d1` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.013 GiB，仅作盘点，不等于释放量 | 0 |
| P074 | `D:/Projects/VRAE/.worktrees/ra3a` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.032 GiB，仅作盘点，不等于释放量 | 0 |
| P075 | `D:/Projects/VRAE/.worktrees/ra3b-independent-qa` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.040 GiB，仅作盘点，不等于释放量 | 0 |
| P076 | `D:/Projects/VRAE/.worktrees/ra3b-qa-candidate-d9d4e234a01a` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.024 GiB，仅作盘点，不等于释放量 | 0 |
| P077 | `D:/Projects/VRAE/.worktrees/ra3b-qa-v2-candidate-d9d4e234a01a` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.024 GiB，仅作盘点，不等于释放量 | 0 |
| P078 | `D:/Projects/VRAE/.worktrees/ra3c-independent-qa` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.158 GiB，仅作盘点，不等于释放量 | 0 |
| P079 | `D:/Projects/VRAE/.worktrees/ra3c-qa-phaseb-6a7a3d3a` | B | 开放PR或未提交/远端可达性风险；不可动；tracked变化3；观察载荷0.043 GiB，仅作盘点，不等于释放量 | 0 |
| P080 | `D:/Projects/VRAE/.worktrees/ra3c-qa-v2-e2f9466f06bb` | B | 开放PR或未提交/远端可达性风险；不可动；tracked变化34；观察载荷0.062 GiB，仅作盘点，不等于释放量 | 0 |
| P081 | `D:/Projects/VRAE/.worktrees/ra3d-d1d2-offline-review-contract` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.230 GiB，仅作盘点，不等于释放量 | 0 |
| P082 | `D:/Projects/VRAE/.worktrees/ra4a-p1-postgres-rls-queue` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.503 GiB，仅作盘点，不等于释放量 | 0 |
| P083 | `D:/Projects/VRAE/.worktrees/ra4a-p2a-private-bytes` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.492 GiB，仅作盘点，不等于释放量 | 0 |
| P084 | `D:/Projects/VRAE/.worktrees/ra4a-p2b1-review-cas-testonly` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.556 GiB，仅作盘点，不等于释放量 | 0 |
| P085 | `D:/Projects/VRAE/.worktrees/ra4a-p2b1-v3-py311` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.291 GiB，仅作盘点，不等于释放量 | 0 |
| P086 | `D:/Projects/VRAE/.worktrees/ra4a-p2b2a-identity-local` | A | 运行/启动路径引用，或共享Git根；不可动；观察载荷0.608 GiB，仅作盘点，不等于释放量 | 0 |
| P087 | `D:/Projects/VRAE/.worktrees/ra4b-p1-private-api-worker-testonly` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷5.737 GiB，仅作盘点，不等于释放量 | 0 |
| P088 | `D:/Projects/VRAE/.worktrees/ra4b-p2-assigned-task-projection-testonly` | E | 本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT；观察载荷1.627 GiB，仅作盘点，不等于释放量 | 0 |
| P089 | `D:/Projects/VRAE/.worktrees/real-qwen-provider` | E | 私有/未计量/时点不稳信息；UNKNOWN_PROTECT；观察载荷≥0.499 GiB，仅作盘点，不等于释放量 | 0 |
| P090 | `D:/Projects/VRAE/.worktrees/s2-c1-buyer-candidate` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.464 GiB，仅作盘点，不等于释放量 | 0 |
| P091 | `D:/Projects/VRAE/.worktrees/s2-c1-p0` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.462 GiB，仅作盘点，不等于释放量 | 0 |
| P092 | `D:/Projects/VRAE/.worktrees/s2-c1-p1` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.709 GiB，仅作盘点，不等于释放量 | 0 |
| P093 | `D:/Projects/VRAE/.worktrees/s2-c1-p1-batch2` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.462 GiB，仅作盘点，不等于释放量 | 0 |
| P094 | `D:/Projects/VRAE/.worktrees/s2-ci-313-pilot` | B | 开放PR或未提交/远端可达性风险；不可动；PR #135；观察载荷0.452 GiB，仅作盘点，不等于释放量 | 0 |
| P095 | `D:/Projects/VRAE/.worktrees/s2-info03-tech02` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.526 GiB，仅作盘点，不等于释放量 | 0 |
| P096 | `D:/Projects/VRAE/.worktrees/s3-offline-ai` | C | 有Git外历史证据；唯一性未证，先保全归档核验；观察载荷0.459 GiB，仅作盘点，不等于释放量 | 0 |
| P097 | `D:/Projects/VRAE/.worktrees/vf-preview-173` | B | 开放PR或未提交/远端可达性风险；不可动；PR #174；观察载荷0.486 GiB，仅作盘点，不等于释放量 | 0 |

## 最小保留结构与未来备份顺序

1. 保留唯一`D:/Projects/VRAE/.git`与其管理记录；主仓当前checkout在旧feature分支，不能为“整理”现在切main或移动它。
2. 保留A组实际运行引用的5个宿主根、全部现存VRAE容器/镜像/命名卷、Tailscale与既有Startup；继续保留PR172/174联调树。
3. 保留其余开放PR工作区（124/127/133/135/141）及两处dirty QA树、恢复分支2个风险提交；各自归属开发者确认前不可动。
4. C组先由有权人识别唯一证据、来源权限及保留期限，形成私有加密归档、文件清单和校验和，并实际恢复抽验后才讨论回收原目录。
   本轮只确认Git外证据存在，没有读内容或做跨目录内容hash，不能把“可能重复”当成已去重。E组同样先解除UNKNOWN_PROTECT。
5. Git历史保存应覆盖全部分支/tags和显式列出的detached HEAD/风险提交；仅一个main clone或普通`--all`集合不自动证明所有detached/未提交工作已保存。
   dirty patch、未跟踪与ignored文件需另外私有保存；不把root私钥、客户材料或ledger复制进Git/公开artifact。
6. 运行卷与备份链只由唯一受信操作者按原冷备/一致性恢复流程处理，保持原canonical账本、权限状态与单实例边界。
   本轮不归档、不导出、不校验私有卷内容；未来任何卷/镜像清理需单独提案，不能混入工作目录清理。

## Owner逐路径批准单（未来阶段）

每一项批准必须明确：ID+规范化绝对路径、允许动作、保护/备份位置与校验、恢复步骤、VF窗口及原操作者确认。
执行前再核对Git HEAD/dirty/untracked/ignored、实际远端可达性、进程/容器挂载/Startup依赖及无新资料；任一变化立即退回保留。
一次只处理一个经批准项并回读，不因一次成功推广到其父目录、其他worktree、分支或卷。现在没有任何Phase B动作获批。
