import {readFile, realpath, mkdtemp, mkdir, writeFile, rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {observe} from './observer.mjs';

export const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
export const sources=[
  {name:'ra4c3',file:'docs/03-engineering/ra4c3-pg-read/browser-test.mjs',blob:'3cf73d4ec0397acdca3d988ac4332ef7dfcf258b',deadlineMs:20000},
  {name:'b5b',file:'integration/b5b/browser.mjs',blob:'3f37f2268585f4a481c5882cfdb8e6e2d65f3578',deadlineMs:30000},
];
export async function contract(source,profile) {
  const bytes=await readFile(path.join(root,source.file));
  // Git applies the repository's checkout filters (Windows CRLF included).
  const blob=execFileSync('git',['hash-object','--path',source.file,source.file],{cwd:root,encoding:'utf8'}).trim();
  if(blob!==source.blob) throw Error('FROZEN_SOURCE_MISMATCH');
  const text=bytes.toString();
  const match=text.match(/chrome=spawn\(chromePath,(\[[^\n]+?\]),\{windowsHide:true,stdio:\['ignore','pipe','pipe'\]\}\)/);
  if(!match || !text.includes(`,${source.deadlineMs});chrome.on('error'`)) throw Error('LAUNCH_CONTRACT_MISMATCH');
  const args=Array.from(vm.runInNewContext(match[1],{profile},{timeout:100}));
  if(args.at(-1)!=='about:blank'||args.at(-2)!==`--user-data-dir=${profile}`) throw Error('PROFILE_CONTRACT_MISMATCH');
  return {args,blob,deadlineMs:source.deadlineMs};
}

async function main() {
  const output=path.resolve(process.argv[2]||'diagnostic-output');
  const bin=await realpath(process.env.RA4C0_CHROMIUM||'/usr/bin/google-chrome');
  const hash=createHash('sha256').update(await readFile(bin)).digest('hex');
  // Version comes only from our owned browser's version command, never a second
  // browser invocation that could select an existing default profile.
  const binary={path:bin,sha256:hash};
  const results=[];
  await mkdir(output,{recursive:true});
  for(const source of sources) {
    const profile=await mkdtemp(path.join(tmpdir(),'s2-chrome-d0-'));
    try {
      const c=await contract(source,profile);
      const r=await observe({bin,args:c.args,deadlineMs:c.deadlineMs,profile});
      // Flags are source-derived; replace only our random profile path in the public record.
      results.push({...source,launchArgs:c.args.map(a=>a.startsWith('--user-data-dir=')?'--user-data-dir=<owned-temp>':a),...r});
    } finally { await rm(profile,{recursive:true,force:true,maxRetries:3}); }
  }
  const head=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
  const toolHashes={};
  for(const file of ['observer.mjs','run.mjs','observer.test.mjs','fixture.mjs','verify.py','audit_history.py']) {
    toolHashes[file]=createHash('sha256').update(await readFile(path.join(root,'integration/s2_chrome_diagnostic',file))).digest('hex');
  }
  const receipt={schema:1,head,nodeVersion:process.version,toolHashes,
    acceptedBase:'cb86cdb1b57962aa89fa2ef4465131219c8c45e9',binary,results,
    historicalVerdict:'UNKNOWN; original three RED jobs remain RED; independent startup observation is not original-suite acceptance'};
  await writeFile(path.join(output,'startup.json'),JSON.stringify(receipt,null,2)+'\n');
  console.log(JSON.stringify(results.map(r=>({name:r.name,classification:r.classification,connected:r.connected}))));
  if(results.some(r=>r.classification!=='ENDPOINT_AVAILABLE'||r.connected!==true||!r.cleanup.closeObserved)) process.exitCode=1;
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) await main();
