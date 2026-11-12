// Generate a readable index from original results; never changes raw results.
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));
const names=await readdir(path.join(here,'evidence'));
const exports=[];for(const name of names.filter(n=>/^export-.*\.json$/.test(n)).sort())exports.push({name,r:JSON.parse(await readFile(path.join(here,'evidence',name),'utf8'))});
const runs=[];for(const name of names.filter(n=>n.startsWith('browser-')).sort())runs.push({name,r:JSON.parse(await readFile(path.join(here,'evidence',name,'results.json'),'utf8'))});
const last=runs.at(-1),e=exports.at(-1),dir='evidence/'+last.name;
const table=rows=>rows.map(r=>'| '+r.join(' | ')+' |').join('\n');
const md=`# Phase 0.6 实际结果与原始证据

验收对象是只读原生合成桥，不是生产人审。输入与 expected pins 固定来自 main 696d4ae695041f0eeefa56d22039682a989380b2。每个原生模块的 Git blob、原始 Git bytes SHA256、本地 bytes SHA256 和实际 import 路径在 exporter JSON 中；未导入其他 worktree 或 PR #48。

## 原生 API 实测

双 Python 各执行真实 EvidencePack.load / FindingPackage.load / GuardResult.load / build_draft / ReportDraft.load / render。各 **2 个 native 正例通过 + 18 个非法副本明确拒绝**，无 stub/mocked Guard，也不生成新可信 pins。单独 wrapper 保存 command.json、stdout、stderr 与 exit=0；前序直接执行也保留原始 JSON。

| 原始运行 | Python | 正例 | 明确拒绝 | 状态 |
| --- | --- | --- | --- | --- |
${table(exports.map(({name,r})=>['['+name+'](evidence/'+name+')',r.python.split(' ')[0],r.positives.length,r.negatives.length,r.status]))}

404：1 issue / INQUIRE / native REVIEW_REQUIRED；200：0 issue / native=null。HTML 与独立 held pins 一致：404 6170722c97015cf113c3d7898c5cc342bf7cfea0113038bd07a48fdfd55d808c；200 4d815b29563341930c8a7a2b75f3aad416f04b3dc08683b7902c6f286d5e28a5。主联系 quote 对应原始 body UTF-8 [158,177)，不是手填 mock。

| 非法尝试 | 实际拒绝类 | 原始错误码 | 首个拒绝层 |
| --- | --- | --- | --- |
${table(e.r.negatives.map(n=>[n.id,n.error_type,n.error,n.layer]))}

N06/N07 是桥接层对独立 held draft/html pin 的比较；其余使用 native 错误，不把本地自定义字段伪装成 native API。所有负例均使用 detached 原始输入副本，原始 expected pins 保留在每条记录。没有“重签 Guard 后继续”或非法输入变成空绿报。具体 mutation 与复跑代码见 export_bridge.py；所有 raw error 保留。

## 真实新鲜 Chromium

最终：[${last.name}/results.json](${dir}/results.json)，Chromium ${last.r.browser.product}，**${last.r.counts.PASS} PASS / ${last.r.counts.FAIL} FAIL / ${last.r.counts.ERROR} ERROR / ${last.r.counts.SKIP} SKIP**，${last.r.screenshots.length} 张原始 PNG。三宽度 1280/375/320、两份 dossier，33 次实际来源打开（6 次主入口 + 27 次逐条 claim）与返回。每条断言包含焦点、UI 反馈与内存轨迹；六份当时输入的精确 bytes 在 input-files/。

实测包含：12px 顶部私有提示与 above-fold、零横向溢出；原生 report id/version/真实捕获时间；原始 byte slice/quote/body/citation、键盘 Tab/Space、回查后焦点；404 事实/三条候选编辑分层；200 无 CTA Guard 字段且 native=null；逐条 claim 全部核对才可继续内存模拟；全量 native hash；原生 HTML 在独立 sandbox renderer 中实际加载，其 URL、NOT APPROVED 正文、scripts=0/forms=0 已读取；模拟操作后原生 JSON 字节不变；刷新清空。

源弹窗在打开时聚焦标题、滚动位置为 0，12px NOT APPROVED 提示可见；长原生引用可展开，减少手机默认滚动。页面外部请求 **${last.r.observedExternalPageRequests.length}**，Runtime 异常 **${last.r.runtimeExceptions.length}**；没有 enabled send/share/export。CDP loopback 控制不属于页面 API 请求。观测仅限受测页面，不声称 OS 级所有流量为零。

| 场景 | 1280 桌面 | 375 手机 | 320 窄屏 |
| --- | --- | --- | --- |
${table([['原生 404','native-404'],['404 原始字节','native-evidence-404'],['404 单条来源弹窗','native-claim-dialog-404'],['404 仅内存结果','native-result-404'],['原生 200 零问题','native-200'],['200 原始字节','native-evidence-200'],['200 来源弹窗','native-claim-dialog-200'],['200 内部范围模拟','native-result-200']].map(([title,p])=>[title,...[1280,375,320].map(w=>'['+w+']('+dir+'/'+p+'-'+w+'.png)')]))}

## 保留全部 FAIL / ERROR

| 原始运行 | PASS | FAIL | ERROR | SKIP |
| --- | --- | --- | --- | --- |
${table(runs.map(({name,r})=>['['+name+'](evidence/'+name+'/results.json)',r.counts.PASS,r.counts.FAIL,r.counts.ERROR,r.counts.SKIP]))}

首轮沙箱 CDP Page.enable 超时未计 PASS，经批准以仅本地文件/封锁外网的 Chromium 重试。第一个实际 FAIL 是 404 证据面板缺 evidence_ref，补齐实际 evidence/snapshot/locator 后重跑；没有改原生 source/Guard 或降低预期。第二个 FAIL 的原检查只看主 frame tree，未识别 sandbox file iframe 的独立 renderer；保留原 FAIL，新增附着 OOPIF 读取实际 URL/DOM 的更强检查。之后 143 PASS 的中间运行保留；截图审阅再改善弹窗默认焦点/固定私有提示并新增断言，最终为 ${last.r.counts.PASS} PASS。断言 FAIL 后的执行 ERROR 也原样保留，不拆除重复记号来美化计数。

原 Chromium stderr 含本机启动/网络服务诊断，保留原始 CRLF；不将“页面 Runtime 异常=0”说成进程完全没有诊断。一次前期 Python -c 的 PowerShell 引号解析 SyntaxError 未写文件，随后改用受版本控制的 inspect_inputs.py；摘要生成器首次 Node 执行也因反引号转义 SyntaxError 退出 1，未写 RESULTS，修正后生成。两者不计成功测试。任何封存/命令问题单列，不清洗原始记录。

## 封存与门禁

seal-evidence.mjs 验证独立 held pins、原 HTML SHA、每条显示 pointer 与 native claim 完全一致、每个 quote 的原始 byte slice、所有截图 SHA、最终浏览器输入一致、旧 Phase0.5 资产复用和所有 1793 个 main 文件 mode/blob 保留。manifest 排除自身和临时浏览器 profile/runtime，避免循环 SHA。audit-delivery.mjs 在最终提交后只读验证 clean tree、清单 raw bytes 与 Git blob 以及最终源文件一致；精确最终 SHA 记录在 Draft PR 中。

GitHub CI 若触发，必须对应最终 HEAD + 最新已验收 main，实际四项结果和原始日志链接记录在 Draft PR；它们是主干回归，不能冒充 native 来源投影或真人流程验收。Phase0 的未来 A01–A48 保持 NOT_RUN，PR48 QA 不修改、不认领。本轮无真实身份/审批/分享/客户访问，Human Gold 0/26，RA3D production NO_GO。
`;
await writeFile(path.join(here,'RESULTS.md'),md);
console.log(JSON.stringify({status:'RESULTS_INDEX_WRITTEN',final:last.name,counts:last.r.counts,exportRuns:exports.length,browserRuns:runs.length}));
