"""Render only metadata captured for Phase A; never touches source worktrees."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
load=lambda name:json.loads((OUT/name).read_text(encoding='utf-8'))
inv=load('inventory-snapshot.json'); gh=load('github-snapshot.json'); runtime=load('runtime-snapshot.json'); end=load('end-reconciliation.json')
assert inv['complete']
rows=inv['entries']
def norm(p):return str(p).replace('\\','/').rstrip('/').lower()
def gib(n):return f'{n/(1024**3):.3f}'
def mbytes(n):return f'{n/(1024**2):.2f}'
def size(row):
    d=row['size']
    if d.get('reason')=='ACTIVE_TREE_NOT_ENTERED':return 'UNKNOWN_PROTECT'
    return ('≥' if not d['complete'] else '')+gib(d['logical_bytes_observed'])
def ancestry(row):
    return 'YES' if row.get('head_ancestor_of_live_main') else 'NO/UNKNOWN'
def safe(s):return str(s).replace('|','/').replace('\n',' ')
def pubpath(p):return str(p).replace('\\','/')
end_heads={norm(k):v for k,v in end['end_worktree_metadata'].items()}
for row in rows:
    row['open_prs']=[p['number'] for p in gh['open_prs'] if p['branch']==row.get('branch') or p['head']==row.get('head')]
    row['head_changed_during_audit']=norm(row['path']) in end_heads and end_heads[norm(row['path'])]!=row.get('head')
    categories=Counter()
    for values in row.get('local_data_categories',{}).values():categories.update(values)
    code_risk=row.get('tracked_change_entries',0)>0 or row['id'] in end['local_commit_risks']
    if row.get('runtime_reference_observed'):
        group,reason='A','运行/启动路径引用，或共享Git根；不可动'
    elif row['open_prs'] or code_risk:
        group,reason='B','开放PR或未提交/远端可达性风险；不可动'
    elif row.get('git_kind')=='NON_REPOSITORY_DIRECTORY' and 'evidence' in row['path'].lower():
        group,reason='C','Git外历史证据目录；先保全归档核验，未断言全局唯一'
    elif (row.get('git_kind')=='LINKED_WORKTREE' and row.get('git_state')=='TRACKED_CLEAN'
          and row.get('head_ancestor_of_live_main') and not row['head_changed_during_audit'] and row['size']['complete']
          and all(k=='REGENERABLE_CACHE_METADATA' for k in categories)):
        group,reason='D','HEAD已被实时main包含；仅版本化文件/可再生缓存，无已观察运行引用'
    elif categories.get('PRIVATE_OR_CONFIGURATION_UNKNOWN_PROTECT') or not row['size']['complete'] or row['head_changed_during_audit']:
        group,reason='E','私有/未计量/时点不稳信息；UNKNOWN_PROTECT'
    elif categories.get('EVIDENCE_OR_GENERATED_UNKNOWN_PROTECT'):
        group,reason='C','有Git外历史证据；唯一性未证，先保全归档核验'
    else:
        group,reason='E','本地环境或其他未版本化数据未证明可再生；UNKNOWN_PROTECT'
    row.update(classification=group,classification_reason=reason)

counts=Counter(r['classification'] for r in rows)
logical=sum(r['size']['logical_bytes_observed'] for r in rows)
drows=[r for r in rows if r['classification']=='D']
dlogical=sum(r['size']['logical_bytes_observed'] for r in drows)
top=[r for r in rows if Path(r['path']).parent==Path('D:/Projects')]
fullnames={'A':'A_正在运行/不可动','B':'B_开放PR或未推送更改/不可动','C':'C_唯一历史证据须归档（唯一性未证时保守纳入）','D':'D_可清理候选（未授权执行）','E':'E_证据不足暂保留'}
header=f'''# VRAE 本地工作区盘点 · Phase A READ_ONLY · Issue #175

审计开始：{inv['started_at']}；目录扫描结束：{inv['finished_at']}；末尾对账：{end['observed_at']}。
本次只写入 `D:/Projects/VRAE/.audit-175/` 审计产物；没有清理、移动、归档、分支切换、fetch/pull、部署、模型调用或运行环境变更。
Codex3活动目录不进入：只从共享Git管理元数据和运行路径引用取得其HEAD/分支；工作区状态/大小均UNKNOWN_PROTECT。

## 结论与范围

- {len(top)}个VRAE相关顶层目录，连同其引用/隐藏目录共 **{len(rows)}个审计单元**；Git登记 **{len(inv['registered_worktrees'])}个工作区**。
- **1个主Git仓库 + 94个linked worktree（其中1个活动目录只看管理元数据）+ 2个非Git证据目录**；没有发现第二个独立clone或已证实冗余普通副本。
- 全部可核对Git单元共用 **`D:/Projects/VRAE/.git`**；branch-vv共106个本地分支，不等于106份clone。其余顶层VRAE目录大多也是linked worktree。
- 已观察文件逻辑长度合计 **{gib(logical)} GiB**，{sum(not r['size']['complete'] for r in rows)}项大小不完整/未知；非实际分配磁盘占用。
- D组 **{len(drows)}项，逻辑长度合计 {gib(dlogical)} GiB（{mbytes(dlogical)} MiB）**；只是逐路径审批候选，当前批准清理/实际释放均为0。
- 两处QA树共37个tracked变化条目；一处分支有2个不被本轮远端heads/tags包含的提交，均保护。未读取patch正文。
- 检查范围限顶层名称含VRAE的目录、Git登记路径与其`.worktrees`直接子目录；其他项目未深入扫描。额外精确探测的`D:/Projects/gloweaseco-leo/VRAE`不存在。

## 实时GitHub基线

| 对象 | 实时SHA/状态 |
| --- | --- |
| main | `{end['main_sha']}` |
| PR172（Draft/open） | `{end['prs']['172']['sha']}` |
| PR174（Draft/open） | `{end['prs']['174']['sha']}` |
| VEYFRONT PR37（只读） | `{gh['vf_pr37']['head']}` |

开放PR：{', '.join('#'+str(p['number'])+' `'+p['branch']+'`' for p in gh['open_prs'])}。
实时读取heads加tags共102个引用，102个目标对象在本地可用于只读图可达性复核；没有fetch。
`HEAD...main`列是左/右计数，即本工作区相对上述实时main的ahead/behind；不是仅比较可能过期的origin/main。
upstream与cached-ahead/behind另存JSON，明确只代表本地缓存。没有以目录日期或分支名推断合并状态。
开放Issue包括153/173（运行与VF）、156（模型）、154/155（G1安全/消费者）、149/146（部署）、129/126（CI）、101/97/96/95/94（历史集成）；
这些Issue仍开放不自动表示其所有历史目录均可删，相关证据/运行引用/本地改动分别保护，完整编号在源快照中。

## 五级分组

| 分组 | 数量 | 已观察逻辑GiB（可不完整） | 判断规则 |
| --- | ---: | ---: | --- |
'''
for key in 'ABCDE':header+=f'| {fullnames[key]} | {counts[key]} | {gib(sum(r["size"]["logical_bytes_observed"] for r in rows if r["classification"]==key))} | '+{
'A':'真实进程/容器输入/启动引用或共享Git管理根；无清理额度',
'B':'开放PR、未提交patch或2个提交的可达性风险；先保存可恢复版本',
'C':'Git外证据先保全；未哈希比较私有数据，不能声称已证明全局唯一或重复',
'D':'Git clean、无非缓存本地数据、HEAD为实时main祖先、尺寸完整、无已观察运行引用',
'E':'私有数据、环境/配置、大小或运行关联不能安全确认，UNKNOWN_PROTECT'}[key]+' |\n'
header+='''
所有目录规范化绝对路径见下表。逻辑GiB前缀≥表示跳过了私有子树/重解析点或计量不完整；不能把它当作实际可释放下限。
T/U/I为tracked变化/未跟踪/ignored状态条目数，目录条目可能代表整棵树，绝不是文件总数；“clean”只指tracked。
父目录大小已排除表中独立列出的子工作树，因此同一文件树不重复汇总；共享object store只计入主仓一次。

## 完整目录表

| ID | 规范化绝对路径 | 类别 | 类型/.git | HEAD | 分支 | 相对main ahead/behind | T/U/I | 逻辑GiB |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: |
'''
for r in rows:
    tui='UNKNOWN' if r.get('active_exclusion') else '/'.join(str(r.get(k,'?')) for k in ('tracked_change_entries','untracked_entries','ignored_entries'))
    typ={'PRIMARY_REPOSITORY':'主仓/目录','LINKED_WORKTREE':'linked/file','LINKED_WORKTREE_METADATA':'linked/只看管理元数据','NON_REPOSITORY_DIRECTORY':'非Git/无标记'}.get(r.get('git_kind'),'UNKNOWN')
    header+=f"| {r['id']} | `{pubpath(r['path'])}` | {r['classification']} | {typ} | `{(r.get('head') or 'UNKNOWN')[:12]}` | `{safe(r.get('branch') or 'DETACHED/非Git')}` | {r.get('live_main_ahead_behind') or 'UNKNOWN'} | {tui} | {size(r)} |\n"
header+='''
## 本地代码保护明细

'''
for rid, risk in end['local_commit_risks'].items():
    r=next(x for x in rows if x['id']==rid)
    header+=f"- **{rid} `{pubpath(r['path'])}`**：HEAD非实时main祖先；以下提交不被本轮heads/tags包含，按未推送代码风险保留（未查远端PR内部引用/服务端reflog，不断言从未上传）：\n"
    for sha in risk['not_reachable_from_locally_available_live_refs']:header+=f'  - `{sha}`\n'
for rid, data in end['dirty_paths'].items():
    r=next(x for x in rows if x['id']==rid)
    header+=f"\n**{rid} `{pubpath(r['path'])}`**：{data['count']}个tracked变化；仅列文件名，不读取/发布patch正文。\n\n"
    header+='\n'.join('- `'+p+'`' for p in data['paths'])+'\n'
header+='''
## 计量与审计限制

只遍历文件/目录metadata（长度、mtime、是否重解析点），没有读取env、私钥、Bearer、邀请、客户内容、ledger数据库或私有卷文件。
`.private/.aws/.codex/.agents`子树、重解析点不进入；每单元25秒尺寸预算，到限标未知。本次运行中目录不冻结，快照不是事务快照。
mtime是文件系统元数据，不是“最后使用”证明；JSON含目录mtime和观察到的最新文件mtime。虚拟环境也可能藏在docs/.runtime，不能把docs桶全称为唯一证据。
NTFS分配、压缩、稀疏/硬链接、目录开销和Docker Desktop VHDX回收均未测；逻辑长度不承诺磁盘空间释放。未读取volume大小。
主仓新增的`.audit-175/`未跟踪条目是本次产物，已从尺寸统计排除；原有其他未跟踪内容没有修改。
详见 `RUNTIME_PROTECTION.md`、`CLEANUP_PROPOSAL.md`、`AUDIT_SNAPSHOT.json`。本次到报告提交即停止，Phase B不获自动授权。
'''
(OUT/'INVENTORY.md').write_text(header,encoding='utf-8')

rt=f'''# 运行依赖保护清单 · Issue #175 · Phase A

元数据起点：{runtime['observed_at']}；终验：{runtime.get('end_observed_at')}。
只用Docker筛选后的Mounts/State/Image/RestartPolicy、Windows进程/服务/计划任务/启动快捷方式/Run键路径摘要。
不读Config.Env、原始命令行输出、容器文件、Tailscale配置或任何volume内容；没有exec/stop/restart/up/prune。
镜像未提供可用OCI revision标签，故**不能从镜像ID推定实际服务源码SHA**；审计PR SHA也不是运行readback。

## 宿主目录保护

| ID | 目录 | 实证与误删后果 |
| --- | --- | --- |
'''
for r in rows:
    if r['classification']=='A':
        reasons=[]
        if r['id']=='P001':reasons.append('唯一共享.git object store/refs/worktree管理根；删除会破坏整个95工作区家族')
        for group in ('processes','tasks','services','startup','registry_run'):
            for item in runtime['windows'].get(group,[]):
                if any(norm(p)==norm(r['path']) for p in item.get('roots',[])):
                    reasons.append(group+': '+str(item.get('name'))+((' PID '+str(item['pid'])) if 'pid'in item else ''))
        for c in runtime['docker']['containers']:
            if any(any(norm(p)==norm(r['path']) for p in m['project_roots']) for m in c['mounts']):reasons.append('容器输入绑定: '+c['name'])
        if r.get('active_exclusion'):reasons.append('PR172与VF联调活动树，不入内；启动/构建/后续运维源必须保留')
        rt+=f"| {r['id']} | `{pubpath(r['path'])}` | {'；'.join(reasons)}；误删可能中断进程、重启/恢复或Git访问 |\n"
rt+='''
```mermaid
flowchart LR
  G[主仓 .git 共享管理根] --> W[95个Git工作区]
  S[用户Startup VRAE-TemporaryWake] --> A[Codex3 API活动目录]
  S --> B[B7P1旧目录仍被进程引用]
  LP[vrae-local-pg] --> A
  GP[运行中G1 PG] --> GD[Codex3 G1目录输入]
  P[两个现存Python进程] --> ID[ra4a-p2b2a-identity-local解释器]
  WR[vrae-windows-runtime] --> WO[windows-operator / windows-ledger]
  WA[vrae-windows-ai] --> Q[共享vrae-local-ledger]
  LA[vrae-local-ai] --> Q
  T[Windows Tailscale Auto Running] --> F[现存公网入口依赖]
```

## 容器元数据（全部保留；不是清理目标）

| 名称 | 状态 | 镜像ID | 重启策略 | named volume/受保护宿主根 |
| --- | --- | --- | --- | --- |
'''
for c in runtime['docker']['containers']:
    deps=[]
    for m in c['mounts']:
        if m.get('volume'):deps.append(m['volume']+(' (RW)' if m.get('read_write') else ' (RO)'))
        deps.extend(pubpath(p) for p in m.get('project_roots',[]))
        if m.get('backing_named_volume_if_observed'):deps.append('输入背后卷: '+m['backing_named_volume_if_observed'])
    rt+=f"| {c['name']} | {c['status']} | `{c['image_id'].removeprefix('sha256:')[:12]}` | {c['restart_policy']} | {'; '.join(deps) or '无卷/宿主挂载；镜像与运行仍须保留'} |\n"
rt+='''
两个AI容器都显示同一vrae-local-ledger挂载；这里只说明共享可变依赖，**没有检查账本内容或推断并发调用**。不得因“重复AI”自行停止、迁移或清空任一卷。
Windows服务的API/Worker可能在同一runtime进程树内，未exec故未独立核验内部Worker数量，不冒称已验证单Worker。
镜像大小为共享层口径，不是可释放量；所有现存镜像与VHDX不在Phase A清理提案内。

## 命名卷保护

| 卷名 | 保护级别 | 内容/容量 |
| --- | --- | --- |
'''
mounted=set()
for c in runtime['docker']['containers']:
    for m in c['mounts']:
        if m.get('volume'):mounted.add(m['volume'])
        if m.get('backing_named_volume_if_observed') not in (None,'UNKNOWN_PROTECT'):mounted.add(m['backing_named_volume_if_observed'])
for v in runtime['docker']['volumes']:
    level='A_现存容器引用/不可动' if v['name'] in mounted else 'E_UNKNOWN_PROTECT（私有根/备份仍需保留）'
    rt+=f"| `{v['name']}` | {level} | 未读取，容量UNKNOWN，不计释放量 |\n"
rt+='''
即使卷未在某个容器的Mounts中出现，也不表示可删：root私有卷可通过文件级bind或仅由受信操作者/备份流程使用。
未读取Docker宿主mountpoint、私有卷文件、备份内容或ledger数据库；容器内敏感输入路径已遮蔽。

## Windows启动/服务与盲区

Tailscale服务Running/Auto；用户Startup有VRAE-TemporaryWake.lnk，全用户Startup有Tailscale.lnk。
VRAE相关已观察计划任务/Run键匹配为0；这只说明该次查询没有匹配，不保证不存在其他登录用户、相对路径、变量拼接、人工命令或远程调度。
两个tailscaled进程的命令信息不可见；Tailscale节点/路由配置未读取。不能为了补足审计关闭VPN或调整路由。
普通项目目录没有观察到引用并非对所有潜在消费者的数学证明；D候选还需Owner在批准窗口逐项复核。
当前活动树大小与dirty/untracked/ignored未知；未进入它，也未要求Codex3暂停联调。备份任务存在性/私有恢复链内容未取证，按UNKNOWN_PROTECT。
本轮没有启动、停止、重启或部署任何容器/进程，没有运行模型或更改系统启动入口。
'''
(OUT/'RUNTIME_PROTECTION.md').write_text(rt,encoding='utf-8')

proposal=f'''# VRAE 安全收口提案 · 只审批，不执行 · Issue #175

**Phase A结束后停止。当前删除/移动/归档/环境变更授权均为0；实际释放0。**
推荐先完成VF真实联调，或由Owner明确指定不影响联调的窗口，再对下面的规范化路径逐项批准；不能批量按名称/日期/VRAE前缀处理。

## 可释放空间的保守口径

已观察97个单元的文件逻辑长度合计{gib(logical)} GiB；活动树、私有子树、卷容量未知。
D组{len(drows)}项逻辑长度合计 **{gib(dlogical)} GiB / {mbytes(dlogical)} MiB**，是当前最窄候选载荷估算；实际分配空间、共享硬链接与删除后释放量UNKNOWN。
其他A/B/C/E本轮不计入可释放空间。缓存/venv看起来大也可能被脚本、解释器或离线证据链依赖，不能把其全部大小当作安全可删量。

## D组逐项候选

下面只证明观察到的版本化内容可由保留的main/object store恢复、无非缓存local-data状态条目，以及已查运行面无引用。
尚未做Phase B归档/恢复演练、Owner逐项批准或执行前重查；linked worktree必须走未来经批准的Git管理流程，不能直接删文件夹或共享.git。

| ID | 唯一具体路径 | 载荷MiB | 判定证据 | 误删后果与执行前条件 |
| --- | --- | ---: | --- | --- |
'''
for r in drows:
    proposal+=f"| {r['id']} | `{pubpath(r['path'])}` | {mbytes(r['size']['logical_bytes_observed'])} | HEAD `{r['head'][:12]}` 是实时main祖先；T/U/I={r['tracked_change_entries']}/{r['untracked_entries']}/{r['ignored_entries']}；尺寸完整，无已观察运行引用 | 丢失本地checkout/可再生缓存及Git worktree配置；先核对未变化、无新引用并记录恢复方式，Owner单独批准 |\n"
proposal+='''
## A/B/C/E的逐项处理建议

| ID | 路径 | 分组 | 证据/建议 | 本轮计入释放量 |
| --- | --- | --- | --- | ---: |
'''
for r in rows:
    if r['classification']=='D':continue
    detail=r['classification_reason']
    if r['open_prs']:detail+='；PR '+','.join('#'+str(p) for p in r['open_prs'])
    if r.get('tracked_change_entries'):detail+='；tracked变化'+str(r['tracked_change_entries'])
    if r['id'] in end['local_commit_risks']:detail+='；2个远端heads/tags不可达提交先保存并验证可恢复'
    detail+='；观察载荷'+size(r)+' GiB，仅作盘点，不等于释放量'
    proposal+=f"| {r['id']} | `{pubpath(r['path'])}` | {r['classification']} | {detail} | 0 |\n"
proposal+='''
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
'''
(OUT/'CLEANUP_PROPOSAL.md').write_text(proposal,encoding='utf-8')

public={'audit_started_at':inv['started_at'],'audit_finished_at':inv['finished_at'],'end_reconciliation_at':end['observed_at'],
 'phase':'A_READ_ONLY_STOP_AFTER_REPORT','classes':dict(counts),'directory_count':len(rows),'registered_worktrees':len(inv['registered_worktrees']),
 'logical_bytes_observed_not_allocated':logical,'candidate_D_logical_bytes':dlogical,'actual_bytes_freed':0,
 'main_sha':end['main_sha'],'prs':end['prs'],'vf_pr37':gh['vf_pr37'],'entries':rows,
 'runtime':runtime,'local_code_risks':{'dirty_paths':end['dirty_paths'],'commit_risks':end['local_commit_risks']},
 'limitations':inv['size_semantics'],'no_private_contents_read':True,'no_runtime_mutation':True,'no_git_fetch_pull':True}
(OUT/'AUDIT_SNAPSHOT.json').write_text(json.dumps(public,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ('INVENTORY.md','RUNTIME_PROTECTION.md','CLEANUP_PROPOSAL.md','AUDIT_SNAPSHOT.json')}
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'classes':dict(counts),'D_candidates':[{'id':r['id'],'path':r['path'],'logical_bytes':r['size']['logical_bytes_observed']} for r in drows],
 'observed_logical_GiB':gib(logical),'D_candidate_MiB':mbytes(dlogical),'report_sizes':{n:(OUT/n).stat().st_size for n in manifest}},ensure_ascii=False))
