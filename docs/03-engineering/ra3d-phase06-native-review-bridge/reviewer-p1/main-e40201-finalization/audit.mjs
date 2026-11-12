// Finalization-only proof. Frozen feature, native evidence and accepted QA stay unchanged.
import {execFileSync} from 'node:child_process';
import {readFile,readdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../../../..');
const stem='docs/03-engineering/ra3d-phase06-native-review-bridge/',p1=stem+'reviewer-p1/',prefix=p1+'main-e40201-finalization/';
const base='e40201bf399cc8c5d11a708fcbe33c31f01e67b2',old='151cdac7d31580afac4c5624f675cb2915c2f5e2',merge='a46b3b15599ce407c131090782c6fcec58f890f4';
const allowed=new Set(['index.html','bridge-view.js','bridge.css'].map(f=>stem+f));
const git=(...a)=>execFileSync('git',a,{cwd:root,maxBuffer:25_000_000});
const sha=b=>createHash('sha256').update(b).digest('hex'),blob=b=>createHash('sha1').update(Buffer.from(`blob ${b.length}\0`)).update(b).digest('hex');
const tree=ref=>new Map(git('ls-tree','-r','--full-tree',ref).toString().trim().split('\n').map(l=>{const [meta,file]=l.split('\t');return[file,meta]}));
const head=git('rev-parse','HEAD').toString().trim(),main=tree(base),prior=tree(old),now=tree(head);
const parents=git('show','-s','--format=%P',merge).toString().trim().split(' ');assert.deepEqual(parents,[old,base]);
const protectedFiles=[];for(const[file,meta]of main){assert.equal(now.get(file)?.split(' ')[0],meta.split(' ')[0]);if(!allowed.has(file)){assert.equal(now.get(file),meta,`MAIN_CHANGED ${file}`);protectedFiles.push({file,mode_type_blob:meta})}}
const featureFiles=[];for(const[file,meta]of prior){if(file.startsWith(p1)||allowed.has(file)){assert.equal(now.get(file),meta,`FROZEN_FEATURE_CHANGED ${file}`);featureFiles.push({file,mode_type_blob:meta})}}
const dirty=git('status','--porcelain','--untracked-files=all').toString().trimEnd().split('\n').filter(Boolean);assert(dirty.every(l=>l.slice(3).startsWith(prefix)),JSON.stringify(dirty));
const ui=[];const oldResult=JSON.parse(git('show',old+':'+p1+'evidence/reviewer-browser-2026-11-12T10-57-30-395Z/results.json'));
for(const[f,row]of Object.entries(oldResult.inputs)){const raw=await readFile(path.join(root,stem+f));assert.equal(sha(raw),row.sha256,`OLD_INPUT_CHANGED ${f}`);ui.push({file:stem+f,sha256:sha(raw),git_blob_sha:blob(raw)})}
const runs=[];for(const name of (await readdir(path.join(here,'evidence'))).filter(n=>n.startsWith('browser-')).sort()){
  const r=JSON.parse(await readFile(path.join(here,'evidence',name,'results.json'),'utf8'));for(const s of r.screenshots)assert.equal(sha(await readFile(path.join(here,'evidence',name,s.file))),s.sha256);
  runs.push({directory:'evidence/'+name,status:r.status,counts:r.counts,screenshots:r.screenshots.length});
}
const last=runs.at(-1),r=JSON.parse(await readFile(path.join(here,last.directory,'results.json'),'utf8'));
assert.deepEqual(r.counts,{PASS:293,FAIL:0,ERROR:0,SKIP:0});assert.equal(r.observedExternalPageRequests.length,0);assert.equal(r.runtimeExceptions.length,0);assert.equal(r.screenshots.length,42);
assert.equal(new Set(r.assertions.map(x=>x.id)).size,293);assert.deepEqual(r.assertions.map(x=>x.id).sort(),oldResult.assertions.map(x=>x.id).sort());assert(r.assertions.every(x=>x.status==='PASS'));
for(const[f,row]of Object.entries(r.inputs))assert.equal(sha(await readFile(path.join(root,stem+f))),row.sha256);
const pin=JSON.parse(await readFile(path.join(here,'suite-pin.json'),'utf8'));const suite=await readFile(path.join(here,'compat-293.mjs'),'utf8');assert.equal(sha(suite),pin.executed_sha256);assert.equal(await readFile(path.join(here,last.directory,'executed-suite.mjs'),'utf8'),suite);
let restored=suite;for(const[from,to]of pin.replacements.toReversed())restored=restored.replace(to,from);assert.equal(sha(restored),pin.original_sha256);assert.equal(restored,git('show',old+':'+pin.file).toString('utf8'));
const qa=[];for(const file of ['.dockerignore','pyproject.toml','tests/reporting/test_ra3c_independent_acceptance.py','tests/reporting/test_ra3c_owner_adjudicated_v2.py','docs/03-engineering/ra3c-independent-qa/phase-c-main-integration/collection_contract_minimal.py']){assert.equal(now.get(file),main.get(file));qa.push({file,mode_type_blob:main.get(file),git_bytes_sha256:sha(git('show',base+':'+file))})}
const changed=git('diff','--name-status',base,head).toString().trim().split('\n').filter(Boolean);assert(changed.every(l=>l.startsWith('A\t'+p1)||(l.startsWith('M\t')&&allowed.has(l.slice(2)))),JSON.stringify(changed));
const native=[];for(const c of ['404','200']){const file=stem+`dossiers/contact-${c}.html`;assert.equal(now.get(file),prior.get(file));native.push({case:c,file,sha256:sha(await readFile(path.join(root,file)))})}
if(process.argv.includes('--seal')){
  const files=[];async function walk(dir){for(const e of await readdir(dir,{withFileTypes:true})){if(e.name==='runtime'||e.name.startsWith('profile-'))continue;const full=path.join(dir,e.name);if(e.isDirectory())await walk(full);else{const file=path.relative(here,full).replaceAll('\\','/');if(file==='manifest.json')continue;const raw=await readFile(full);files.push({file,sha256:sha(raw),git_blob_sha:blob(raw),bytes:raw.length})}}}await walk(here);
  await writeFile(path.join(here,'manifest.json'),JSON.stringify({kind:'PR56_NEW_MAIN_FINALIZATION_ONLY',acceptedMain:base,oldFeature:old,normalMerge:merge,normalMergeParents:parents,auditedSourceHead:head,protectedMainFiles:protectedFiles,unchangedOldFeatureFiles:featureFiles,uiInputs:ui,qaAndDockerPins:qa,native,browserRuns:runs,finalBrowser:last,originalCore170:170,additionalP1:123,suiteTransportOnly:true,files:files.sort((a,b)=>a.file.localeCompare(b.file)),realApprovals:0,realShares:0,productionRA3D:'NO_GO'},null,2)+'\n');
  console.log(JSON.stringify({status:'NEW_MAIN_SOURCE_AND_UI_SEALED',head,mainFiles:main.size,mainProtected:protectedFiles.length,frozenFeatureFiles:featureFiles.length,browser:r.counts,rawFiles:files.length,normalMerge:merge,parents,qaV1V2DockerUnchanged:true}));
}else{
  assert.equal(dirty.length,0,'TREE_NOT_CLEAN');const m=JSON.parse(await readFile(path.join(here,'manifest.json'),'utf8'));for(const f of m.files){const raw=await readFile(path.join(here,f.file));assert.equal(sha(raw),f.sha256);assert(now.get(prefix+f.file)?.endsWith(' '+f.git_blob_sha))}
  console.log(JSON.stringify({status:'CLEAN_NEW_MAIN_FINALIZATION_VERIFIED',head,acceptedMain:base,normalMerge:merge,parents,mainFiles:main.size,mainProtected:protectedFiles.length,frozenFeatureFiles:featureFiles.length,rawFilesVerified:m.files.length,oldUiInputsUnchanged:true,browser:r.counts,qaV1V2DockerUnchanged:true,cleanTree:true}));
}
