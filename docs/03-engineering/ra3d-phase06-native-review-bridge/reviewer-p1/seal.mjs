// P1 audit/manifest only; never writes old artifacts or regenerates native reports.
import {execFileSync} from 'node:child_process';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../../..');
const stem='docs/03-engineering/ra3d-phase06-native-review-bridge/',prefix=stem+'reviewer-p1/';
const base='a1321dac611ac2a38dca3b4785d71b0256d92136',ui=['index.html','bridge-view.js','bridge.css'];
const allowed=new Set(ui.map(f=>stem+f));
const git=(...a)=>execFileSync('git',a,{cwd:root,maxBuffer:20_000_000});
const sha=b=>createHash('sha256').update(b).digest('hex');
const blob=b=>createHash('sha1').update(Buffer.from(`blob ${b.length}\0`)).update(b).digest('hex');
const tree=ref=>new Map(git('ls-tree','-r','--full-tree',ref).toString().trim().split('\n').map(l=>{const[meta,file]=l.split('\t');return[file,meta]}));
const head=git('rev-parse','HEAD').toString().trim(),before=tree(base),current=tree(head);assert.equal(before.size,1993);
const protectedFiles=[];for(const [file,meta]of before){assert.equal(current.get(file)?.split(' ')[0],meta.split(' ')[0]);if(!allowed.has(file)){assert.equal(current.get(file),meta,`FORBIDDEN_CHANGE ${file}`);protectedFiles.push({file,mode_type_blob:meta})}}
assert.equal(protectedFiles.length,1990);
const diff=git('diff','--name-status',base).toString().trim().split('\n').filter(Boolean);assert(diff.every(l=>l.startsWith('A\t'+prefix)||(l.startsWith('M\t')&&allowed.has(l.slice(2)))),JSON.stringify(diff));
const status=git('status','--porcelain','--untracked-files=all').toString().trimEnd().split('\n').filter(Boolean);assert(status.every(l=>allowed.has(l.slice(3))||l.slice(3).startsWith(prefix)),JSON.stringify(status));
const evidence=path.join(here,'evidence'),runs=[];for(const name of (await readdir(evidence)).filter(n=>n.includes('-browser-')).sort()){
  const r=JSON.parse(await readFile(path.join(evidence,name,'results.json'),'utf8'));
  for(const s of r.screenshots)assert.equal(sha(await readFile(path.join(evidence,name,s.file))),s.sha256);
  runs.push({directory:'evidence/'+name,status:r.status,counts:r.counts,screenshots:r.screenshots.length});
}
const old=runs.filter(r=>r.directory.includes('baseline-browser-')&&r.status==='OFFLINE_INTERACTION_PASS').at(-1);
const latest=runs.filter(r=>r.directory.includes('reviewer-browser-')).at(-1);assert(old);assert.deepEqual(old.counts,{PASS:170,FAIL:0,ERROR:0,SKIP:0});assert.deepEqual(latest.counts,{PASS:293,FAIL:0,ERROR:0,SKIP:0});
const load=r=>readFile(path.join(here,r.directory,'results.json'),'utf8').then(JSON.parse);
const a=await load(old),b=await load(latest);assert.equal(b.observedExternalPageRequests.length,0);assert.equal(b.runtimeExceptions.length,0);
const core=b.assertions.filter(r=>!r.id.startsWith('P1-'));assert.equal(core.length,170);assert.deepEqual(core.map(r=>r.id).sort(),a.assertions.map(r=>r.id).sort());assert(core.every(r=>r.status==='PASS'));assert.equal(b.assertions.filter(r=>r.id.startsWith('P1-')).length,123);
for(const f of ui){const raw=await readFile(path.join(here,old.directory,'input-files',f));assert.equal(sha(raw),sha(git('show',base+':'+stem+f)),`OLD_BASELINE_NOT_ORIGINAL ${f}`)}
for(const [f,row]of Object.entries(b.inputs))assert.equal(sha(await readFile(path.join(root,stem+f))),row.sha256,`UNTESTED_UI ${f}`);
const suite=await readFile(path.join(here,'compat-170-plus.mjs'),'utf8'),compat=JSON.parse(await readFile(path.join(here,'reference/suite-compatibility.json'),'utf8'));
assert.equal(sha(Buffer.from(suite)),compat.generatedSha256);assert.equal(await readFile(path.join(here,latest.directory,'executed-suite.mjs'),'utf8'),suite);
let restored=suite;for(const c of compat.changes.toReversed())restored=restored.replace(c.to,c.from);
const original=git('show',base+':'+stem+'browser-test.mjs');assert.equal(restored,original.toString('utf8'));assert.equal(sha(original),compat.originalSha256);assert.equal(sha(await readFile(path.join(here,'reference/original-170.git-bytes.mjs'))),sha(original));
const nativePins=JSON.parse(git('show',base+':tests/reporting/fixtures/caller-pins.json'));
const native=[];for(const c of ['404','200']){const d=JSON.parse(await readFile(path.join(root,stem+`dossiers/contact-${c}.draft.json`),'utf8'));assert.equal(d.html_sha256,nativePins[c].expected_html_sha256);assert.equal(sha(await readFile(path.join(root,stem+`dossiers/contact-${c}.html`))),d.html_sha256);native.push({case:c,draft_ref:d.draft_ref,html_sha256:d.html_sha256,native_report_version:d.native_report_version})}
const oldView=git('show',base+':'+stem+'bridge-view.js').toString('utf8'),newView=await readFile(path.join(root,stem+'bridge-view.js'),'utf8');const guard=s=>s.slice(s.indexOf('  function syncPositive()'),s.indexOf('  new MutationObserver(sync)'));
assert.equal(guard(newView),guard(oldView),'NATIVE_ACK_GATING_CHANGED');
const sourceFiles=[];for(const file of [...ui.map(f=>stem+f),...['compat-170-plus.mjs','prepare-suite.mjs','reviewer-cases.txt'].map(f=>prefix+f)]){const raw=await readFile(path.join(root,file));sourceFiles.push({file,sha256:sha(raw),git_blob_sha:blob(raw),matches_source_commit:current.get(file)?.endsWith(' '+blob(raw))||false})}
for(const file of ['prepare-suite.mjs','compat-170-plus.mjs','seal.mjs','audit.mjs'])execFileSync(process.execPath,['--check',path.join(here,file)],{stdio:'pipe'});
const files=[];async function walk(dir){for(const e of await readdir(dir,{withFileTypes:true})){if(e.name==='runtime'||e.name.startsWith('profile-'))continue;const full=path.join(dir,e.name);if(e.isDirectory())await walk(full);else{const file=path.relative(here,full).replaceAll('\\','/');if(file==='evidence/manifest.json')continue;const raw=await readFile(full);files.push({file,sha256:sha(raw),git_blob_sha:blob(raw),bytes:raw.length})}}}await walk(here);
const manifest={kind:'REVIEWER_FIRST_P1_OFFLINE_ONLY',acceptedMain:base,sourceCommit:head,allowedModified:[...allowed],protectedFiles,sourceFiles,native,browserRuns:runs,baseline:old,final:latest,original170Exact:true,original170CorePassed:170,additionalPassed:123,compatibility:compat,files:files.sort((x,y)=>x.file.localeCompare(y.file)),excluded:['manifest self-reference','runtime','disposable profile-*'],nativeGuardGatingUnchanged:true,realApprovals:0,realShares:0,humanUsabilityStudy:'NOT_MEASURED',productionRA3D:'NO_GO'};
await writeFile(path.join(evidence,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({status:'P1_EVIDENCE_SEALED',head,protectedMainFiles:1990,allowedUiFiles:3,nativeHashesUnchanged:true,original170:170,additional:123,rawFiles:files.length,baseline:old.directory,final:latest.directory,sourceMatchesCommit:sourceFiles.every(f=>f.matches_source_commit)}));
