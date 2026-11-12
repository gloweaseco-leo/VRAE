// Read-only verification and manifest creation, restricted to this new docs path.
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readdir,readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url));
const prefix='docs/03-engineering/ra3d-phase05-prototype/';
const base='61b88eb31d1dec668e7e05495b88fe2d8a5b25fe';
const git=(...args)=>execFileSync('git',args,{cwd:here,encoding:'utf8'}).trim();
const sha=b=>createHash('sha256').update(b).digest('hex');
const head=git('rev-parse','HEAD');
const tree=ref=>new Map(git('ls-tree','-r','--full-tree',ref).split('\n').filter(Boolean).map(line=>{const [meta,file]=line.split('\t');return[file,meta]}));
const original=tree(base),current=tree('HEAD');
assert.equal(original.size,1611,'EXPECTED_ACCEPTED_MAIN_FILE_COUNT');
const preserved=[];for(const [file,meta]of original){assert.equal(current.get(file),meta,`MAIN_BLOB_OR_MODE_CHANGED ${file}`);preserved.push({file,mode_type_blob:meta})}
const changed=git('diff','--name-only',base,'--','.');
assert(!changed.split('\n').filter(Boolean).some(p=>!p.startsWith(prefix)),changed);
// Also inspect the entire repository, not only this script's relative directory.
const repo=git('rev-parse','--show-toplevel');
const allDiff=execFileSync('git',['diff','--name-only',base],{cwd:repo,encoding:'utf8'}).trim().split('\n').filter(Boolean);
assert(allDiff.every(p=>p.startsWith(prefix)),JSON.stringify(allDiff));
const status=execFileSync('git',['status','--porcelain','--untracked-files=all'],{cwd:repo,encoding:'utf8'}).trimEnd().split('\n').filter(Boolean);
assert(status.every(line=>line.slice(3).replace(/^"|"$/g,'').startsWith(prefix)),JSON.stringify(status));
const fixture=JSON.parse(await readFile(path.join(here,'fixtures.json'),'utf8'));
const capture=JSON.parse(await readFile(path.join(here,'reference/synthetic-captures.json'),'utf8'));
for(const e of capture.captures){const b=Buffer.from(e.source,'utf8');assert.equal(sha(b),e.sourceSha256);assert.equal(b.subarray(...e.byteRange).toString('utf8'),e.quote)}
assert.equal(fixture.scenarios.contact.source.targetHttp,404);assert.equal(fixture.scenarios.coverage.source.targetHttp,200);assert.equal(fixture.scenarios.coverage.nativeReportVersion,null);
const runNames=(await readdir(path.join(here,'evidence'))).filter(n=>n.startsWith('browser-')).sort();
const runs=[];for(const name of runNames){const r=JSON.parse(await readFile(path.join(here,'evidence',name,'results.json'),'utf8'));runs.push({directory:'evidence/'+name,status:r.status,counts:r.counts,inputs:r.inputs,infrastructureError:r.infrastructureError,screenshotCount:r.screenshots.length});for(const shot of r.screenshots)assert.equal(sha(await readFile(path.join(here,'evidence',name,shot.file))),shot.sha256)}
const final=runs.at(-1);assert.equal(final.status,'OFFLINE_INTERACTION_PASS');assert.deepEqual(final.counts,{PASS:126,FAIL:0,ERROR:0,SKIP:0});
const latest=JSON.parse(await readFile(path.join(here,final.directory,'results.json'),'utf8'));assert.equal(latest.observedExternalPageRequests.length,0);assert.equal(latest.runtimeExceptions.length,0);
const sourceFiles=[];for(const [file,expected]of Object.entries(latest.inputs)){const b=await readFile(path.join(here,file));assert.equal(sha(b),expected.sha256,`UNTESTED_CHANGE ${file}`);let committed=false;try{committed=sha(execFileSync('git',['show',`${head}:${prefix}${file}`],{cwd:here,stdio:['ignore','pipe','ignore']}))===sha(b)}catch{}sourceFiles.push({file,sha256:sha(b),bytes:b.length,matches_head_git_blob:committed})}
for(const file of ['workbench.js','fixtures.js','prepare-fixtures.mjs','browser-test.mjs','seal-evidence.mjs'])execFileSync(process.execPath,['--check',path.join(here,file)],{stdio:'pipe'});
const files=[];async function walk(dir){for(const ent of await readdir(dir,{withFileTypes:true})){if(ent.name.startsWith('profile-'))continue;const full=path.join(dir,ent.name);if(ent.isDirectory())await walk(full);else{const file=path.relative(here,full).replaceAll('\\','/');if(file==='evidence/manifest.json')continue;const b=await readFile(full);files.push({file,sha256:sha(b),bytes:b.length})}}}await walk(here);
const manifest={kind:'PHASE05_SYNTHETIC_UI_EVIDENCE_NOT_APPROVAL',acceptedMain:base,sourceCommit:head,sourceFiles,provisionalReadOnlyReference:fixture.readingReferences.provisionalFeature,mainProtection:{verifiedAgainst:'HEAD Git tree; all tracked originals compared by mode/type/blob',preservedCount:preserved.length,originalFiles:preserved,allChangesRestrictedTo:prefix},finalBrowserRun:final.directory,actualRuns:runs,finalBrowserCounts:final.counts,screenshots:latest.screenshots,files:files.sort((a,b)=>a.file.localeCompare(b.file)),excluded:['evidence/manifest.json (self-reference)','disposable Chromium profile-* directories'],futurePhase0Cases:'A01-A48 NOT_RUN / IMPLEMENTATION_NOT_STARTED',actualHumanApprovals:0,actualGrants:0,actualCustomerAccesses:0,humanGold:'0/26',productionRA3D:'NO_GO'};
await writeFile(path.join(here,'evidence/manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({status:'MANIFEST_VERIFIED',sourceCommit:head,mainFilesPreserved:preserved.length,rawFiles:files.length,finalBrowserRun:final.directory,finalCounts:final.counts,sourceFilesMatchHead:sourceFiles.every(f=>f.matches_head_git_blob)}));
