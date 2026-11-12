// Verify, then seal evidence only in the new authorized docs directory.
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../..');
const prefix='docs/03-engineering/ra3d-phase06-native-review-bridge/';
const base='696d4ae695041f0eeefa56d22039682a989380b2';
const git=(...a)=>execFileSync('git',a,{cwd:root,maxBuffer:20_000_000});
const sha=b=>createHash('sha256').update(b).digest('hex');
const blob=b=>createHash('sha1').update(Buffer.from(`blob ${b.length}\0`)).update(b).digest('hex');
const tree=ref=>new Map(git('ls-tree','-r','--full-tree',ref).toString().trim().split('\n').map(l=>{const [meta,file]=l.split('\t');return[file,meta]}));
const head=git('rev-parse','HEAD').toString().trim(),original=tree(base),current=tree('HEAD');
assert.equal(original.size,1793);
const mainFiles=[];for(const[file,meta]of original){assert.equal(current.get(file),meta,`MAIN_CHANGED ${file}`);mainFiles.push({file,mode_type_blob:meta})}
const changed=git('diff','--name-only',base).toString().trim().split('\n').filter(Boolean);assert(changed.every(f=>f.startsWith(prefix)),JSON.stringify(changed));
const status=git('status','--porcelain','--untracked-files=all').toString().trimEnd().split('\n').filter(Boolean);assert(status.every(l=>l.slice(3).startsWith(prefix)),JSON.stringify(status));
const evidence=path.join(here,'evidence'),entries=await readdir(evidence);
const runs=[];for(const name of entries.filter(n=>n.startsWith('browser-')).sort()){
  const r=JSON.parse(await readFile(path.join(evidence,name,'results.json'),'utf8'));
  for(const s of r.screenshots)assert.equal(sha(await readFile(path.join(evidence,name,s.file))),s.sha256);
  runs.push({directory:'evidence/'+name,status:r.status,counts:r.counts,screenshots:r.screenshots.length,inputs:r.inputs});
}
const last=runs.at(-1);assert.deepEqual(last.counts,{PASS:170,FAIL:0,ERROR:0,SKIP:0});assert.equal(last.status,'OFFLINE_INTERACTION_PASS');
const final=JSON.parse(await readFile(path.join(here,last.directory,'results.json'),'utf8'));assert.equal(final.observedExternalPageRequests.length,0);assert.equal(final.runtimeExceptions.length,0);assert.equal(final.screenshots.length,24);
const inputFiles=[];for(const [file,expected]of Object.entries(final.inputs)){const b=await readFile(path.join(here,file));assert.equal(sha(b),expected.sha256,`UNTESTED_INPUT ${file}`);inputFiles.push({file,sha256:sha(b),git_blob_sha:blob(b),matches_source_commit:current.get(prefix+file)?.endsWith(' '+blob(b))||false})}
const sourceExports=[];for(const name of entries.filter(n=>/^export-.*\.json$/.test(n)).sort()){
  const r=JSON.parse(await readFile(path.join(evidence,name),'utf8'));
  assert.equal(r.status,'NATIVE_REPLAY_AND_REFUSAL_PASS');assert.equal(r.positives.length,2);assert.equal(r.negatives.length,18);assert(r.negatives.every(n=>n.status==='REFUSED'));
  sourceExports.push({file:'evidence/'+name,python:r.python,positives:r.positives,negatives:r.negatives.map(n=>({id:n.id,error:n.error,error_type:n.error_type,layer:n.layer})),actual_approvals:r.actual_approvals,actual_shares:r.actual_shares});
}
assert(sourceExports.some(r=>r.python.startsWith('3.11.'))&&sourceExports.some(r=>r.python.startsWith('3.13.')));
const nativeCommands=[];const exporterBytes=await readFile(path.join(here,'export_bridge.py'));
for(const name of entries.filter(n=>/^python31[13]-/.test(n)).sort()){
  const row=JSON.parse(await readFile(path.join(evidence,name,'command.json'),'utf8'));
  assert.equal(row.exit,0);assert.equal(row.script_sha256,sha(exporterBytes),'UNTESTED_NATIVE_EXPORTER');
  assert.equal(sha(await readFile(path.join(evidence,name,'stdout.txt'))),row.stdout_sha256);
  assert.equal(sha(await readFile(path.join(evidence,name,'stderr.txt'))),row.stderr_sha256);
  nativeCommands.push({directory:'evidence/'+name,...row});
}
assert.equal(nativeCommands.length,2);
inputFiles.push({file:'export_bridge.py',sha256:sha(exporterBytes),git_blob_sha:blob(exporterBytes),matches_source_commit:current.get(prefix+'export_bridge.py')?.endsWith(' '+blob(exporterBytes))||false});
const pins=JSON.parse(git('show',base+':tests/reporting/fixtures/caller-pins.json'));
const dossiers=[];for(const c of ['404','200']){
  const x=JSON.parse(await readFile(path.join(here,`dossiers/contact-${c}.display.json`),'utf8'));
  const d=JSON.parse(await readFile(path.join(here,`dossiers/contact-${c}.draft.json`),'utf8'));
  assert.deepEqual(x.native_document,d);assert.deepEqual(x.held,pins[c]);assert.equal(d.draft_ref,pins[c].expected_draft_ref);assert.equal(sha(await readFile(path.join(here,x.native_html_path))),pins[c].expected_html_sha256);
  for(const item of x.shownClaims){const raw=Buffer.from(item.source.bodyBase64,'base64');assert.equal(sha(raw),item.source.sourceSha256);assert.equal(raw.subarray(...item.source.byteRange).toString('utf8'),item.source.quote);let v=d;for(const key of item.documentPointer.slice(1).split('/'))v=v[key];assert.deepEqual(item.claim,v)}
  const raw=Buffer.from(x.source.bodyBase64,'base64');assert.equal(raw.subarray(...x.source.byteRange).toString('utf8'),x.source.quote);
  assert(d.private&&!d.shareable&&d.approval_status==='NOT_APPROVED');
  if(c==='200'){assert.equal(d.native_report_version,null);assert.equal(d.issues.length,0);assert.equal(x.source.guardRef,null);assert.equal(x.source.bindingRef,null)}else{assert.equal(d.issues.length,1);assert.equal(d.issues[0].finding.buyer_task,'INQUIRE')}
  dossiers.push({case:c,html_sha256:d.html_sha256,draft_ref:d.draft_ref,native_report_version:d.native_report_version,shownClaims:x.shownClaims.map(v=>({pointer:v.documentPointer,guard_ref:v.claim.guard_ref,binding_ref:v.claim.binding_ref,status:v.claim.status})),main_source:x.source.citation,byteRange:x.source.byteRange});
}
const reuse=[];for(const f of ['workbench.js','workbench.css','browser-test.mjs']){const file='docs/03-engineering/ra3d-phase05-prototype/'+f;reuse.push({file,git_blob_sha:original.get(file).split(' ').at(-1),sha256:sha(git('show',base+':'+file)),usage:f==='browser-test.mjs'?'PINNED_CDP_HARNESS_GENERATOR_INPUT':'DIRECT_UNMODIFIED_LOCAL_ASSET'})}
for(const f of ['bridge-fixture.js','bridge-view.js','browser-test.mjs','prepare-browser-test.mjs','run-exports.mjs','summarize-evidence.mjs','seal-evidence.mjs','audit-delivery.mjs'])execFileSync(process.execPath,['--check',path.join(here,f)],{stdio:'pipe'});
const files=[];async function walk(dir){for(const e of await readdir(dir,{withFileTypes:true})){if(e.name==='runtime'||e.name==='__pycache__'||e.name.startsWith('profile-'))continue;const full=path.join(dir,e.name);if(e.isDirectory())await walk(full);else{const file=path.relative(here,full).replaceAll('\\','/');if(file==='evidence/manifest.json')continue;const b=await readFile(full);files.push({file,sha256:sha(b),git_blob_sha:blob(b),bytes:b.length})}}}await walk(here);
const manifest={kind:'NATIVE_READONLY_SYNTHETIC_BRIDGE_NOT_APPROVAL',acceptedMain:base,sourceCommit:head,mainFilesPreserved:mainFiles,sourceFiles:inputFiles,reusedAcceptedAssets:reuse,dossiers,exportRuns:sourceExports,nativeCommands,browserRuns:runs,finalBrowserRun:last.directory,browserCounts:last.counts,sourceCitationClicks:final.assertions.filter(a=>a.status==='PASS'&&/main-source-click|exact-native-source/.test(a.id)).length,files:files.sort((a,b)=>a.file.localeCompare(b.file)),excluded:['evidence/manifest.json self-reference','runtime/','__pycache__/','profile-* disposable browser state'],realApprovals:0,realShareGrants:0,humanGold:'0/26',productionRA3D:'NO_GO'};
await writeFile(path.join(evidence,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({status:'BRIDGE_EVIDENCE_SEALED',sourceCommit:head,mainBlobsModes:mainFiles.length,rawFiles:files.length,sourceMatchesCommit:inputFiles.every(f=>f.matches_source_commit),browser:last.counts,sourceClicks:manifest.sourceCitationClicks,dossiers:dossiers.map(d=>({case:d.case,shownClaims:d.shownClaims.length,html_sha256:d.html_sha256}))}));
