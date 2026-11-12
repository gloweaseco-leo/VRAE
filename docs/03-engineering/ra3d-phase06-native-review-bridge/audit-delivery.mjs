// Read-only final Git/manifest/clean-tree audit; no writes or approvals.
import {execFileSync} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../..'),prefix='docs/03-engineering/ra3d-phase06-native-review-bridge/';
const git=(...a)=>execFileSync('git',a,{cwd:root,maxBuffer:20_000_000});
const sha=b=>createHash('sha256').update(b).digest('hex');
const blob=b=>createHash('sha1').update(Buffer.from(`blob ${b.length}\0`)).update(b).digest('hex');
const tree=ref=>new Map(git('ls-tree','-r','--full-tree',ref).toString().trim().split('\n').map(l=>{const [meta,file]=l.split('\t');return[file,meta]}));
const head=git('rev-parse','HEAD').toString().trim(),current=tree(head),m=JSON.parse(await readFile(path.join(here,'evidence/manifest.json'),'utf8'));
assert.equal(git('status','--porcelain','--untracked-files=all').toString(),'');
for(const r of m.mainFilesPreserved)assert.equal(current.get(r.file),r.mode_type_blob);
assert.equal(m.mainFilesPreserved.length,1793);
for(const r of m.files){const b=await readFile(path.join(here,r.file));assert.equal(sha(b),r.sha256);assert.equal(blob(b),r.git_blob_sha);assert(current.get(prefix+r.file)?.endsWith(' '+r.git_blob_sha),`GIT_BYTES_DIFFER ${r.file}`)}
const code=tree(m.sourceCommit);for(const r of m.sourceFiles){assert(r.matches_source_commit);assert(current.get(prefix+r.file)?.endsWith(' '+r.git_blob_sha));assert(code.get(prefix+r.file)?.endsWith(' '+r.git_blob_sha))}
const changes=git('diff','--name-status',m.acceptedMain,head).toString().trim().split('\n');assert(changes.every(l=>l.startsWith('A\t'+prefix)),JSON.stringify(changes));
console.log(JSON.stringify({status:'CLEAN_NATIVE_BRIDGE_DELIVERY_VERIFIED',head,acceptedMain:m.acceptedMain,sourceCommit:m.sourceCommit,mainBlobsModesPreserved:m.mainFilesPreserved.length,authorizedAddedFiles:changes.length,verifiedRawFiles:m.files.length,sourceMatchesFinal:true,cleanTree:true,browser:m.browserCounts,sourceCitationClicks:m.sourceCitationClicks}));
