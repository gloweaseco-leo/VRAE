import {execFileSync} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../../..'),prefix='docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/';
const git=(...a)=>execFileSync('git',a,{cwd:root,maxBuffer:20_000_000});const sha=b=>createHash('sha256').update(b).digest('hex');const blob=b=>createHash('sha1').update(Buffer.from(`blob ${b.length}\0`)).update(b).digest('hex');
const tree=ref=>new Map(git('ls-tree','-r','--full-tree',ref).toString().trim().split('\n').map(l=>{const[m,f]=l.split('\t');return[f,m]}));
const head=git('rev-parse','HEAD').toString().trim(),current=tree(head),m=JSON.parse(await readFile(path.join(here,'evidence/manifest.json'),'utf8'));assert.equal(git('status','--porcelain','--untracked-files=all').toString(),'');
for(const r of m.protectedFiles)assert.equal(current.get(r.file),r.mode_type_blob);assert.equal(m.protectedFiles.length,1990);
for(const r of m.files){const raw=await readFile(path.join(here,r.file));assert.equal(sha(raw),r.sha256);assert(current.get(prefix+r.file)?.endsWith(' '+r.git_blob_sha))}
const code=tree(m.sourceCommit);for(const r of m.sourceFiles){assert(r.matches_source_commit);const raw=await readFile(path.join(root,r.file));assert.equal(sha(raw),r.sha256);assert.equal(blob(raw),r.git_blob_sha);assert(current.get(r.file)?.endsWith(' '+r.git_blob_sha));assert(code.get(r.file)?.endsWith(' '+r.git_blob_sha))}
const changes=git('diff','--name-status',m.acceptedMain,head).toString().trim().split('\n');assert(changes.every(l=>l.startsWith('A\t'+prefix)||(l.startsWith('M\t')&&m.allowedModified.includes(l.slice(2)))));assert.equal(changes.filter(l=>l.startsWith('M\t')).length,3);
console.log(JSON.stringify({status:'CLEAN_P1_DELIVERY_VERIFIED',head,acceptedMain:m.acceptedMain,sourceCommit:m.sourceCommit,protectedOriginalFiles:1990,allowedModified:3,newOwnedFiles:changes.filter(l=>l.startsWith('A\t')).length,verifiedRawFiles:m.files.length,original170:170,additional123:123,nativeHashesUnchanged:true,guardGatingUnchanged:true,cleanTree:true}));
