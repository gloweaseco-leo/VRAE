// Does not write files. Run after the final commit to verify a clean delivery.
import {execFileSync} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const here=path.dirname(fileURLToPath(import.meta.url));
const prefix='docs/03-engineering/ra3d-phase05-prototype/';
const git=(...a)=>execFileSync('git',a,{cwd:here});
const sha=b=>createHash('sha256').update(b).digest('hex');
const m=JSON.parse(await readFile(path.join(here,'evidence/manifest.json'),'utf8'));
const head=git('rev-parse','HEAD').toString().trim();
assert.equal(git('status','--porcelain','--untracked-files=all').toString(),'','DELIVERY_TREE_NOT_CLEAN');
const entries=new Map(git('ls-tree','-r','--full-tree','HEAD').toString().trim().split('\n').map(l=>{const [meta,file]=l.split('\t');return[file,meta]}));
for(const row of m.mainProtection.originalFiles)assert.equal(entries.get(row.file),row.mode_type_blob);
assert.equal(m.mainProtection.originalFiles.length,1611);
for(const row of m.files){const blob=git('show',`${head}:${prefix}${row.file}`);assert.equal(sha(blob),row.sha256,`COMMITTED_BYTES_DIFFER ${row.file}`);assert.equal(blob.length,row.bytes);assert.equal(sha(await readFile(path.join(here,row.file))),row.sha256)}
for(const row of m.sourceFiles){assert(row.matches_head_git_blob);assert.equal(sha(git('show',`${m.sourceCommit}:${prefix}${row.file}`)),row.sha256);assert.equal(sha(git('show',`${head}:${prefix}${row.file}`)),row.sha256)}
const changed=git('diff','--name-status',m.acceptedMain,'HEAD','--',':/').toString().trim().split('\n');
assert(changed.every(l=>l.startsWith('A\t'+prefix)),JSON.stringify(changed));
console.log(JSON.stringify({status:'CLEAN_DELIVERY_VERIFIED',head,acceptedMain:m.acceptedMain,sourceCommit:m.sourceCommit,mainBlobsAndModesPreserved:m.mainProtection.originalFiles.length,addedFilesOnlyInAuthorizedDirectory:changed.length,manifestFilesVerifiedAgainstGit: m.files.length,browserCounts:m.finalBrowserCounts,sourceMatchesFinalHead:true,cleanTree:true}));
