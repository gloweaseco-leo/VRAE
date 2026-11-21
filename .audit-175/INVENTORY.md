# VRAE 本地工作区盘点 · Phase A READ_ONLY · Issue #175

审计开始：2026-11-20T01:42:59.673972+00:00；目录扫描结束：2026-11-20T01:48:58.177990+00:00；末尾对账：2026-11-20T01:54:13.309874+00:00。
本次只写入 `D:/Projects/VRAE/.audit-175/` 审计产物；没有清理、移动、归档、分支切换、fetch/pull、部署、模型调用或运行环境变更。
Codex3活动目录不进入：只从共享Git管理元数据和运行路径引用取得其HEAD/分支；工作区状态/大小均UNKNOWN_PROTECT。

## 结论与范围

- 19个VRAE相关顶层目录，连同其引用/隐藏目录共 **97个审计单元**；Git登记 **95个工作区**。
- **1个主Git仓库 + 94个linked worktree（其中1个活动目录只看管理元数据）+ 2个非Git证据目录**；没有发现第二个独立clone或已证实冗余普通副本。
- 全部可核对Git单元共用 **`D:/Projects/VRAE/.git`**；branch-vv共106个本地分支，不等于106份clone。其余顶层VRAE目录大多也是linked worktree。
- 已观察文件逻辑长度合计 **52.007 GiB**，18项大小不完整/未知；非实际分配磁盘占用。
- D组 **3项，逻辑长度合计 0.364 GiB（372.90 MiB）**；只是逐路径审批候选，当前批准清理/实际释放均为0。
- 两处QA树共37个tracked变化条目；一处分支有2个不被本轮远端heads/tags包含的提交，均保护。未读取patch正文。
- 检查范围限顶层名称含VRAE的目录、Git登记路径与其`.worktrees`直接子目录；其他项目未深入扫描。额外精确探测的`D:/Projects/gloweaseco-leo/VRAE`不存在。

## 实时GitHub基线

| 对象 | 实时SHA/状态 |
| --- | --- |
| main | `1e3cd9cd409e695dad8b4e0a8357130ae35f6d7e` |
| PR172（Draft/open） | `2114eb7521686e297e484afb999ebf21f1c59e36` |
| PR174（Draft/open） | `5861ae81e64c9752e39740db1524f244dfd43f2e` |
| VEYFRONT PR37（只读） | `3f38a5a16ba2998bcfeaaa7a5cfad4b30a0e384b` |

开放PR：#174 `codex1/vf-preview-173`, #172 `codex3/windows-funnel-live`, #141 `codex2/s2-cta-slice`, #135 `codex1/s2-ci-313-pilot`, #133 `codex1/ci-tiered-313`, #127 `codex2/s2-chrome-d0`, #124 `codex2/s2-c2-p1`。
实时读取heads加tags共102个引用，102个目标对象在本地可用于只读图可达性复核；没有fetch。
`HEAD...main`列是左/右计数，即本工作区相对上述实时main的ahead/behind；不是仅比较可能过期的origin/main。
upstream与cached-ahead/behind另存JSON，明确只代表本地缓存。没有以目录日期或分支名推断合并状态。
开放Issue包括153/173（运行与VF）、156（模型）、154/155（G1安全/消费者）、149/146（部署）、129/126（CI）、101/97/96/95/94（历史集成）；
这些Issue仍开放不自动表示其所有历史目录均可删，相关证据/运行引用/本地改动分别保护，完整编号在源快照中。

## 五级分组

| 分组 | 数量 | 已观察逻辑GiB（可不完整） | 判断规则 |
| --- | ---: | ---: | --- |
| A_正在运行/不可动 | 5 | 3.013 | 真实进程/容器输入/启动引用或共享Git管理根；无清理额度 |
| B_开放PR或未推送更改/不可动 | 9 | 6.092 | 开放PR、未提交patch或2个提交的可达性风险；先保存可恢复版本 |
| C_唯一历史证据须归档（唯一性未证时保守纳入） | 54 | 26.935 | Git外证据先保全；未哈希比较私有数据，不能声称已证明全局唯一或重复 |
| D_可清理候选（未授权执行） | 3 | 0.364 | Git clean、无非缓存本地数据、HEAD为实时main祖先、尺寸完整、无已观察运行引用 |
| E_证据不足暂保留 | 26 | 15.602 | 私有数据、环境/配置、大小或运行关联不能安全确认，UNKNOWN_PROTECT |

所有目录规范化绝对路径见下表。逻辑GiB前缀≥表示跳过了私有子树/重解析点或计量不完整；不能把它当作实际可释放下限。
T/U/I为tracked变化/未跟踪/ignored状态条目数，目录条目可能代表整棵树，绝不是文件总数；“clean”只指tracked。
父目录大小已排除表中独立列出的子工作树，因此同一文件树不重复汇总；共享object store只计入主仓一次。

## 完整目录表

| ID | 规范化绝对路径 | 类别 | 类型/.git | HEAD | 分支 | 相对main ahead/behind | T/U/I | 逻辑GiB |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: |
| P001 | `D:/Projects/VRAE` | A | 主仓/目录 | `aba0a52dc425` | `feat/ra2c0-verified-findings` | 0	564 | 0/5/465 | 0.823 |
| P002 | `D:/Projects/VRAE-Beta-Owner` | E | linked/file | `ff06ceb325d8` | `DETACHED/非Git` | 0	261 | 0/0/3 | ≥0.394 |
| P003 | `D:/Projects/VRAE-Codex2` | C | linked/file | `d885f27cb6b3` | `feat/ra2b2-product-facts` | 0	563 | 0/1/16 | 0.171 |
| P004 | `D:/Projects/VRAE-Codex2/.worktrees/.b7-main-sync-evidence` | C | 非Git/无标记 | `UNKNOWN` | `DETACHED/非Git` | UNKNOWN | ?/?/? | 0.001 |
| P005 | `D:/Projects/VRAE-Codex2/.worktrees/.ci01-evidence` | C | 非Git/无标记 | `UNKNOWN` | `DETACHED/非Git` | UNKNOWN | ?/?/? | 0.001 |
| P006 | `D:/Projects/VRAE-Codex2/.worktrees/b3p0` | E | linked/file | `27bbe6208650` | `codex2/b3p0-testonly-atomic-review-intent` | 0	376 | 0/0/4 | 0.721 |
| P007 | `D:/Projects/VRAE-Codex2/.worktrees/b5-oracle447` | C | linked/file | `345a0ba8be55` | `DETACHED/非Git` | 0	359 | 0/0/26 | 2.758 |
| P008 | `D:/Projects/VRAE-Codex2/.worktrees/b5b` | C | linked/file | `9ea9ae4318e0` | `codex2/b5b-accepted-consumer` | 0	285 | 0/0/6 | 1.135 |
| P009 | `D:/Projects/VRAE-Codex2/.worktrees/b6-resume-lf` | E | linked/file | `01164f2bd86d` | `DETACHED/非Git` | 0	339 | 0/0/4 | 0.643 |
| P010 | `D:/Projects/VRAE-Codex2/.worktrees/b6p0` | E | linked/file | `01164f2bd86d` | `codex2/b6p0-private-handoff-preflight-testonly` | 0	339 | 0/0/4 | 0.771 |
| P011 | `D:/Projects/VRAE-Codex2/.worktrees/ci01-standard-time-budget` | D | linked/file | `7928614fd297` | `codex2/ci01-standard-time-budget` | 0	383 | 0/0/0 | 0.338 |
| P012 | `D:/Projects/VRAE-Codex2/.worktrees/g1-c3-12b-audit` | E | linked/file | `00431c308d69` | `codex2/verified-customer-report` | 0	32 | 0/0/6 | ≥0.020 |
| P013 | `D:/Projects/VRAE-Codex2/.worktrees/g1-vfb-http-consumer` | E | linked/file | `d1c88aa87ca1` | `codex2/g1-vfb-http-consumer` | 0	79 | 0/0/12 | 0.513 |
| P014 | `D:/Projects/VRAE-Codex2/.worktrees/l1-experience` | C | linked/file | `bf87e325416b` | `codex2/l1-diagnosis-experience` | 0	262 | 0/0/4 | 0.467 |
| P015 | `D:/Projects/VRAE-Codex2/.worktrees/l2-deep-audit` | E | linked/file | `bf3d5b0ede79` | `codex2/l2-deep-audit` | 0	237 | 0/0/3 | 0.468 |
| P016 | `D:/Projects/VRAE-Codex2/.worktrees/l2-executive-vf` | E | linked/file | `83e205f2a625` | `codex2/l2-executive-vf` | 0	108 | 0/0/43 | ≥0.521 |
| P017 | `D:/Projects/VRAE-Codex2/.worktrees/l2-launch-r0` | E | linked/file | `36eafdb87a1f` | `codex2/l2-launch-r0` | 0	89 | 0/0/9 | 0.539 |
| P018 | `D:/Projects/VRAE-Codex2/.worktrees/l2-native-report` | E | linked/file | `c173ca8a0784` | `codex2/l2-native-report` | 0	227 | 0/0/3 | 0.450 |
| P019 | `D:/Projects/VRAE-Codex2/.worktrees/l2-s4-ci-scope` | D | linked/file | `4b18148c5e2f` | `codex2/l2-s4-ci-scope-clean` | 0	109 | 0/0/0 | 0.000 |
| P020 | `D:/Projects/VRAE-Codex2/.worktrees/ra2b3` | C | linked/file | `59696a45b1c0` | `feat/ra2b3-info01-bounded-observation` | 0	552 | 0/0/19 | 0.173 |
| P021 | `D:/Projects/VRAE-Codex2/.worktrees/ra2b5` | C | linked/file | `33c23a1c4430` | `feat/ra2b5-trust-facts` | 0	539 | 0/0/18 | 0.014 |
| P022 | `D:/Projects/VRAE-Codex2/.worktrees/ra2b6` | C | linked/file | `1a84989a8e6b` | `feat/ra2b6-trust01-optin` | 0	527 | 0/0/18 | 0.021 |
| P023 | `D:/Projects/VRAE-Codex2/.worktrees/ra2c1` | C | linked/file | `ccd2e5a0abfc` | `feat/ra2c1-info01-finding-integration` | 0	543 | 0/0/18 | 0.013 |
| P024 | `D:/Projects/VRAE-Codex2/.worktrees/ra2c3-qa` | C | linked/file | `55f8e33c14b4` | `test/ra2c3-independent-adversarial` | 0	519 | 0/0/14 | 0.026 |
| P025 | `D:/Projects/VRAE-Codex2/.worktrees/ra3b` | C | linked/file | `d9d4e234a01a` | `codex2/ra3b-claim-provenance` | 0	509 | 0/0/27 | 0.038 |
| P026 | `D:/Projects/VRAE-Codex2/.worktrees/ra3c` | C | linked/file | `e2f9466f06bb` | `codex2/ra3c-private-l1-report` | 0	487 | 0/0/34 | 0.194 |
| P027 | `D:/Projects/VRAE-Codex2/.worktrees/ra3d-phase0` | D | linked/file | `77c14bbf5a43` | `codex2/ra3d-phase0-review-design` | 0	493 | 0/0/0 | 0.026 |
| P028 | `D:/Projects/VRAE-Codex2/.worktrees/ra3d-phase05` | C | linked/file | `57adbb854fca` | `codex2/ra3d-phase05-offline-reviewer-prototype` | 0	482 | 0/0/6 | 0.097 |
| P029 | `D:/Projects/VRAE-Codex2/.worktrees/ra3d-phase06` | C | linked/file | `489c5e973f6d` | `codex2/ra3d-phase06-native-review-evidence-bridge` | 0	479 | 0/0/6 | 0.122 |
| P030 | `D:/Projects/VRAE-Codex2/.worktrees/ra3d-reviewer-p1` | C | linked/file | `d2e5afaa5d5f` | `codex2/ra3d-phase06-reviewer-first-p1` | 0	447 | 0/0/9 | 0.246 |
| P031 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c-b5a` | C | linked/file | `ca6f2137478f` | `codex2/ra4c-b5a-signed-review-read-testonly` | 0	378 | 0/0/15 | 0.723 |
| P032 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c-b5p0` | C | linked/file | `345a0ba8be55` | `codex2/ra4c-b5p0-signed-to-testonly-intent` | 0	359 | 0/0/29 | 1.002 |
| P033 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c0` | C | linked/file | `eda0616e8436` | `codex2/ra4c0-operator-console-shell` | 0	433 | 0/1/23 | 0.313 |
| P034 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c1` | C | linked/file | `34912bb31842` | `codex2/ra4c1-review-target-read-bridge` | 0	419 | 0/5/10 | 0.283 |
| P035 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c2` | C | linked/file | `fc948b5a7d3c` | `codex2/ra4c2-offline-review-proposal-ux` | 0	408 | 0/3/13 | 0.330 |
| P036 | `D:/Projects/VRAE-Codex2/.worktrees/ra4c3` | C | linked/file | `68c530472f50` | `codex2/pr74-local-320-ack-repair` | 0	385 | 0/52/15 | 0.669 |
| P037 | `D:/Projects/VRAE-Codex2/.worktrees/ra4e-b7p0` | C | linked/file | `30ca324c8c6a` | `codex2/ra4e-b7p0-disposable-pg-restore` | 0	380 | 0/4/6 | 0.449 |
| P038 | `D:/Projects/VRAE-Codex2/.worktrees/s2-buyer-cards` | C | linked/file | `cda7c2c62233` | `codex2/s2-buyer-cards` | 0	142 | 0/0/33 | 0.454 |
| P039 | `D:/Projects/VRAE-Codex2/.worktrees/s2-buyer-workbench` | C | linked/file | `d8ca843c3a45` | `codex2/s2-buyer-workbench` | 0	147 | 0/0/33 | 0.463 |
| P040 | `D:/Projects/VRAE-Codex2/.worktrees/s2-c2-p1` | B | linked/file | `82638fc1eb4d` | `codex2/s2-c2-p1` | 5	160 | 0/0/14 | 0.830 |
| P041 | `D:/Projects/VRAE-Codex2/.worktrees/s2-chrome-d0` | B | linked/file | `3cf4fcbafd94` | `codex2/s2-chrome-d0` | 2	153 | 0/0/2 | 0.445 |
| P042 | `D:/Projects/VRAE-Codex2/.worktrees/s2-cta-slice` | B | linked/file | `a7f20a7db877` | `codex2/s2-cta-slice` | 6	107 | 0/0/40 | 0.557 |
| P043 | `D:/Projects/VRAE-Codex2/.worktrees/s2-ux-browser` | E | linked/file | `ee407367c881` | `codex2/s2-ux-browser` | 0	167 | 0/0/3 | 0.483 |
| P044 | `D:/Projects/VRAE-codex3-API-20261119` | A | linked/只看管理元数据 | `2114eb752168` | `codex3/windows-funnel-live` | UNKNOWN | UNKNOWN | UNKNOWN_PROTECT |
| P045 | `D:/Projects/VRAE-codex3-B7A1` | E | linked/file | `447005b2951f` | `codex3/ra4b-recovery-claimv2-testonly` | 0	365 | 0/6/1 | 3.326 |
| P046 | `D:/Projects/VRAE-codex3-B7A1-Resume-20261115` | B | linked/file | `8670332166f4` | `codex3/beta-b7a1-recovery-20261115` | 2	315 | 0/0/2 | 2.744 |
| P047 | `D:/Projects/VRAE-codex3-B7P1` | A | linked/file | `447005b2951f` | `codex3/ra4e-b7p1-private-recovery-ops-testonly` | 0	365 | 0/168/5 | 1.097 |
| P048 | `D:/Projects/VRAE-codex3-B7Restore-v1-20261115` | E | linked/file | `a3a8d469cd68` | `codex3/beta-b7p1-six-schema-restore` | 0	316 | 0/0/5 | ≥0.392 |
| P049 | `D:/Projects/VRAE-codex3-BetaGold-20261114` | E | linked/file | `447005b2951f` | `codex3/beta-gold-ready-20261114` | 0	365 | 0/1/15 | ≥0.381 |
| P050 | `D:/Projects/VRAE-codex3-BetaIntegration-20261114` | E | linked/file | `69a56a1368aa` | `codex3/beta-s2-disc-consumer-20261115` | 0	264 | 0/0/27 | ≥0.394 |
| P051 | `D:/Projects/VRAE-codex3-Delivery-20261119` | E | linked/file | `b20362f78eeb` | `codex3/invited-delivery-bridge` | 0	50 | 0/0/3 | ≥0.020 |
| P052 | `D:/Projects/VRAE-codex3-G1-20261118` | A | linked/file | `32c2f5816c16` | `codex3/l2-g1-offline-http` | 0	66 | 0/0/3 | ≥0.485 |
| P053 | `D:/Projects/VRAE-codex3-L2-20261116` | E | linked/file | `85eac176816f` | `codex3/l2-workbench-business-handoff` | 0	242 | 0/0/46 | ≥0.405 |
| P054 | `D:/Projects/VRAE-codex3-L2-UAT-20261118` | E | linked/file | `89a5115e3b8c` | `codex3/l2-owner-uat-20261118` | 0	97 | 0/0/3 | ≥0.484 |
| P055 | `D:/Projects/VRAE-codex3-L2Integration-20261116` | E | linked/file | `155d62ff0d9d` | `codex3/l2-runtime-integration` | 0	181 | 0/17/48 | ≥0.453 |
| P056 | `D:/Projects/VRAE-codex3-L2Launch-20261118` | E | linked/file | `d76ae1b9515d` | `codex3/l2-launch-private-runtime` | 0	81 | 0/0/1 | ≥0.484 |
| P057 | `D:/Projects/VRAE-codex3-S2Quality-20261117` | E | linked/file | `fac41bb2c948` | `codex3/s2-quality-p0` | 0	125 | 0/6/63 | ≥0.544 |
| P058 | `D:/Projects/VRAE-codex3-S5-20261118` | E | linked/file | `f37a729a0ba2` | `codex3/l2-s5-integration` | 0	101 | 0/7/41 | ≥0.548 |
| P059 | `D:/Projects/VRAE-codex3-Targets-20261119` | E | linked/file | `994c0372b2b3` | `codex3/authorized-target-pipeline` | 0	55 | 0/0/13 | ≥0.020 |
| P060 | `D:/Projects/VRAE/.worktrees/beta-disc-report-v1` | C | linked/file | `384e5e8b64ac` | `codex1/beta-disc-report-v1` | 0	330 | 0/0/55 | 2.726 |
| P061 | `D:/Projects/VRAE/.worktrees/beta-quality-20261114` | C | linked/file | `447005b2951f` | `codex1/beta-quality-20261114` | 0	365 | 0/1/32 | 0.391 |
| P062 | `D:/Projects/VRAE/.worktrees/beta-s2-generated-result-bridge` | C | linked/file | `19f88de36e0d` | `codex1/m1-consumer-integration` | 0	304 | 0/0/47 | 0.479 |
| P063 | `D:/Projects/VRAE/.worktrees/ci-tiered-313` | B | linked/file | `50952c040eeb` | `codex1/ci-tiered-313` | 2	143 | 0/0/53 | 0.475 |
| P064 | `D:/Projects/VRAE/.worktrees/evidence-pack-perf` | C | linked/file | `ae81f0c9b739` | `codex1/evidence-pack-perf` | 0	222 | 0/0/39 | 0.477 |
| P065 | `D:/Projects/VRAE/.worktrees/g1-s1-security` | C | linked/file | `daccb364b58f` | `codex1/g1-s1-security` | 0	79 | 0/0/40 | 0.503 |
| P066 | `D:/Projects/VRAE/.worktrees/l2-industrial-buyer` | C | linked/file | `194e92c09328` | `codex1/l2-industrial-buyer` | 0	234 | 0/0/21 | 0.457 |
| P067 | `D:/Projects/VRAE/.worktrees/qwen4-buyer-candidate` | E | linked/file | `853711c6d298` | `codex1/qwen4-local-runtime` | 0	1 | 0/0/46 | ≥0.503 |
| P068 | `D:/Projects/VRAE/.worktrees/r1a-offline-security` | C | linked/file | `7b89ec51e6e4` | `codex1/r1a-offline-security` | 0	94 | 0/0/41 | 0.495 |
| P069 | `D:/Projects/VRAE/.worktrees/ra2b4` | C | linked/file | `33f2fb93755e` | `feat/ra2b4-seo01-static-signals` | 0	536 | 0/0/18 | 0.016 |
| P070 | `D:/Projects/VRAE/.worktrees/ra2c2` | C | linked/file | `e3db2be776ae` | `feat/ra2c2-seo01-finding-package` | 0	534 | 0/0/18 | 0.016 |
| P071 | `D:/Projects/VRAE/.worktrees/ra2c3` | C | linked/file | `995325203be1` | `feat/ra2c3-trust01-finding-package` | 0	525 | 0/0/18 | 0.022 |
| P072 | `D:/Projects/VRAE/.worktrees/ra2d0` | C | linked/file | `23414fdb2798` | `feat/ra2d0-gold-quality-harness` | 0	562 | 0/0/18 | 0.012 |
| P073 | `D:/Projects/VRAE/.worktrees/ra2d1` | C | linked/file | `d9be1de9c9b7` | `feat/ra2d1-human-gold-review` | 0	556 | 0/0/18 | 0.013 |
| P074 | `D:/Projects/VRAE/.worktrees/ra3a` | C | linked/file | `7702f78a156a` | `feat/ra3a-offline-model-gateway` | 0	516 | 0/0/21 | 0.032 |
| P075 | `D:/Projects/VRAE/.worktrees/ra3b-independent-qa` | C | linked/file | `221bfc9a0038` | `test/ra3b-independent-adversarial` | 0	495 | 0/0/14 | 0.040 |
| P076 | `D:/Projects/VRAE/.worktrees/ra3b-qa-candidate-d9d4e234a01a` | C | linked/file | `d9d4e234a01a` | `DETACHED/非Git` | 0	509 | 0/2/10 | 0.024 |
| P077 | `D:/Projects/VRAE/.worktrees/ra3b-qa-v2-candidate-d9d4e234a01a` | C | linked/file | `d9d4e234a01a` | `DETACHED/非Git` | 0	509 | 0/2/10 | 0.024 |
| P078 | `D:/Projects/VRAE/.worktrees/ra3c-independent-qa` | C | linked/file | `5cc32291c9f2` | `test/ra3c-independent-product-acceptance` | 0	452 | 0/1/21 | 0.158 |
| P079 | `D:/Projects/VRAE/.worktrees/ra3c-qa-phaseb-6a7a3d3a` | B | linked/file | `6a7a3d3aa5f4` | `DETACHED/非Git` | 0	492 | 3/0/11 | 0.043 |
| P080 | `D:/Projects/VRAE/.worktrees/ra3c-qa-v2-e2f9466f06bb` | B | linked/file | `e2f9466f06bb` | `DETACHED/非Git` | 0	487 | 34/0/12 | 0.062 |
| P081 | `D:/Projects/VRAE/.worktrees/ra3d-d1d2-offline-review-contract` | C | linked/file | `12f7795c1c66` | `codex1/ra3d-d1d2-offline-review-contract` | 0	440 | 0/1/28 | 0.230 |
| P082 | `D:/Projects/VRAE/.worktrees/ra4a-p1-postgres-rls-queue` | C | linked/file | `1ea983a93ebf` | `codex1/ra4a-p1-postgres-rls-queue` | 0	426 | 0/1/21 | 0.503 |
| P083 | `D:/Projects/VRAE/.worktrees/ra4a-p2a-private-bytes` | C | linked/file | `ab251882d48c` | `codex1/ra4a-p2a-private-bytes` | 0	415 | 0/1/21 | 0.492 |
| P084 | `D:/Projects/VRAE/.worktrees/ra4a-p2b1-review-cas-testonly` | C | linked/file | `475acd54f5dc` | `codex1/ra4a-p2b1-review-cas-testonly` | 0	402 | 0/1/22 | 0.556 |
| P085 | `D:/Projects/VRAE/.worktrees/ra4a-p2b1-v3-py311` | C | linked/file | `8e99cb522a5c` | `DETACHED/非Git` | 0	411 | 0/4/21 | 0.291 |
| P086 | `D:/Projects/VRAE/.worktrees/ra4a-p2b2a-identity-local` | A | linked/file | `c4fa79d7acee` | `codex1/ra4a-p2b2a-identity-local` | 0	398 | 0/0/41 | 0.608 |
| P087 | `D:/Projects/VRAE/.worktrees/ra4b-p1-private-api-worker-testonly` | C | linked/file | `c3641aea6eba` | `codex1/ra4b-p1-private-api-worker-testonly` | 0	366 | 0/18/35 | 5.737 |
| P088 | `D:/Projects/VRAE/.worktrees/ra4b-p2-assigned-task-projection-testonly` | E | linked/file | `447005b2951f` | `codex1/ra4b-p2-assigned-task-projection-testonly` | 0	365 | 0/7/2 | 1.627 |
| P089 | `D:/Projects/VRAE/.worktrees/real-qwen-provider` | E | linked/file | `e9859f898922` | `codex1/qwen4-live-batch2` | 0	31 | 0/0/61 | ≥0.499 |
| P090 | `D:/Projects/VRAE/.worktrees/s2-c1-buyer-candidate` | C | linked/file | `ebeab94de123` | `codex1/s2-c1-buyer-candidate` | 0	147 | 0/0/56 | 0.464 |
| P091 | `D:/Projects/VRAE/.worktrees/s2-c1-p0` | C | linked/file | `562f7ecea674` | `codex1/s2-c1-p0` | 0	161 | 0/0/45 | 0.462 |
| P092 | `D:/Projects/VRAE/.worktrees/s2-c1-p1` | C | linked/file | `8ea2d28edb33` | `codex1/s2-c1-p1` | 0	154 | 0/0/52 | 0.709 |
| P093 | `D:/Projects/VRAE/.worktrees/s2-c1-p1-batch2` | C | linked/file | `67a376935f03` | `codex1/s2-c1-p1-batch2` | 0	150 | 0/0/53 | 0.462 |
| P094 | `D:/Projects/VRAE/.worktrees/s2-ci-313-pilot` | B | linked/file | `6a66432f10b1` | `codex1/s2-ci-313-pilot` | 2	141 | 0/0/9 | 0.452 |
| P095 | `D:/Projects/VRAE/.worktrees/s2-info03-tech02` | C | linked/file | `7da26306a58b` | `codex1/s2-info03-tech02` | 0	105 | 0/0/83 | 0.526 |
| P096 | `D:/Projects/VRAE/.worktrees/s3-offline-ai` | C | linked/file | `2f95c3003d6e` | `codex1/s3-offline-ai` | 0	138 | 0/0/52 | 0.459 |
| P097 | `D:/Projects/VRAE/.worktrees/vf-preview-173` | B | linked/file | `5861ae81e64c` | `codex1/vf-preview-173` | 2	0 | 0/0/0 | 0.486 |

## 本地代码保护明细

- **P046 `D:/Projects/VRAE-codex3-B7A1-Resume-20261115`**：HEAD非实时main祖先；以下提交不被本轮heads/tags包含，按未推送代码风险保留（未查远端PR内部引用/服务端reflog，不断言从未上传）：
  - `8670332166f499d2a419c3c63f5468f84012909d`
  - `85aa7a034d3a1e47fe999dbe09101115faed4e3b`

**P079 `D:/Projects/VRAE/.worktrees/ra3c-qa-phaseb-6a7a3d3a`**：3个tracked变化；仅列文件名，不读取/发布patch正文。

- `tests/reporting/fixtures/ra3c_codex1_cases.json`
- `tests/reporting/fixtures/ra3c_codex1_inputs.json`
- `tests/reporting/test_ra3c_independent_acceptance.py`

**P080 `D:/Projects/VRAE/.worktrees/ra3c-qa-v2-e2f9466f06bb`**：34个tracked变化；仅列文件名，不读取/发布patch正文。

- `docs/03-engineering/ra3c-independent-qa/adapter-preflight-v1/adapter_draft.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/AUTHORING_FREEZE_0.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/AUTHORING_RECORD.md`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/FREEZE_V2.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/README.md`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/V1_TO_V2_CHANGES.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/V1_TO_V2_FUNCTION.diff`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/adapter_v2.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/audit_source_v2.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/author_test_v2.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/authoring-freeze-helper-v0.txt`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/bind_candidate.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/build_browser_inputs.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/capture_browser_v2.mjs`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/fixtures/admissible-requests.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/fixtures/candidate-binding.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/fixtures/cases.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/fixtures/guard-requests.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/freeze_v2.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/legacy_transport.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/make_dossier.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/prepare_browser_source.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/prepare_fixtures.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/prepare_worktree.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/run_final.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/select_request_witnesses.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/source-replay-py311.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/source-replay-py313.json`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/support.py`
- `docs/03-engineering/ra3c-independent-qa/owner-adjudicated-v2/test_acceptance_v2.py`
- `docs/03-engineering/ra3c-independent-qa/phase-b-native-v1/adapter.py`
- `tests/reporting/fixtures/ra3c_codex1_cases.json`
- `tests/reporting/fixtures/ra3c_codex1_inputs.json`
- `tests/reporting/test_ra3c_independent_acceptance.py`

## 计量与审计限制

只遍历文件/目录metadata（长度、mtime、是否重解析点），没有读取env、私钥、Bearer、邀请、客户内容、ledger数据库或私有卷文件。
`.private/.aws/.codex/.agents`子树、重解析点不进入；每单元25秒尺寸预算，到限标未知。本次运行中目录不冻结，快照不是事务快照。
mtime是文件系统元数据，不是“最后使用”证明；JSON含目录mtime和观察到的最新文件mtime。虚拟环境也可能藏在docs/.runtime，不能把docs桶全称为唯一证据。
NTFS分配、压缩、稀疏/硬链接、目录开销和Docker Desktop VHDX回收均未测；逻辑长度不承诺磁盘空间释放。未读取volume大小。
主仓新增的`.audit-175/`未跟踪条目是本次产物，已从尺寸统计排除；原有其他未跟踪内容没有修改。
详见 `RUNTIME_PROTECTION.md`、`CLEANUP_PROPOSAL.md`、`AUDIT_SNAPSHOT.json`。本次到报告提交即停止，Phase B不获自动授权。
