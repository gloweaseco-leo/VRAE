// Versioned transport/disclosure adapter. All original 170 assertions stay exact.
import {execFileSync} from 'node:child_process';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const own=path.dirname(fileURLToPath(import.meta.url));
const base='a1321dac611ac2a38dca3b4785d71b0256d92136';
const file='docs/03-engineering/ra3d-phase06-native-review-bridge/browser-test.mjs';
const raw=execFileSync('git',['show',base+':'+file],{cwd:own});
const original=raw.toString('utf8');let s=original;const changes=[];
function replace(from,to,why){if(!s.includes(from)||s.indexOf(from)!==s.lastIndexOf(from))throw Error('SOURCE_SHAPE_MISMATCH_'+why);s=s.replace(from,to);changes.push({from,to,why})}
replace('const here=path.dirname(fileURLToPath(import.meta.url));',"const own=path.dirname(fileURLToPath(import.meta.url));\nconst here=path.resolve(own,'..');\nconst baseline=process.argv.includes('--baseline');",'Read current bridge from parent; baseline flag only affects extra tests/output labels');
replace("const out=path.join(here,'evidence','browser-'+runId);","const out=path.join(own,'evidence',(baseline?'baseline-browser-':'reviewer-browser-')+runId);",'All writes restricted to reviewer-p1');
replace("async function click(selector){const p=await ev(","async function click(selector){\n  const parents=await ev(`(()=>{const e=document.querySelector(${JSON.stringify(selector)}),a=[];for(let n=e?.parentElement;n;n=n.parentElement)if(n.tagName==='DETAILS'&&!n.open&&n.querySelector(':scope > summary')!==e){if(!n.id)throw Error('UNNAMED_DISCLOSURE');a.push(n.id)}return a.reverse()})()`);\n  for(const id of parents)await click('#'+id+' > summary');\n  const p=await ev(",'Use real mouse summary clicks to reveal closed ancestor panels; do not change assertion values or skip controls');
replace("const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('MISSING '+${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();", "const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw Error('MISSING '+${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();",'Identity anchor: click rectangle source remains unchanged');
replace('async function click(selector){\n  const parents=', "async function click(selector){\n  await ev(`new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))`);\n  const parents=",'Wait two animation frames before real pointer actions; no retries or altered outcomes');
replace("for(const id of parents)await click('#'+id+' > summary');\n  const p=await ev(","for(const id of parents)await click('#'+id+' > summary');\n  await ev(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))})()`);\n  const p=await ev(",'Wait for scroll/layout before measuring the original target rectangle');
replace('      await screenshot(`native-${c}-${width}.png`,true);','      await screenshot(`first-viewport-${c}-${width}.png`,false);\n      await screenshot(`native-${c}-${width}.png`,true);','Additional actual first-viewport screenshot in both old/new runs');
const extras=await readFile(path.join(own,'reviewer-cases.txt'),'utf8');
replace("  await check('zero-external-page-requests'",extras+"\n  await check('zero-external-page-requests'",'New reviewer-only assertions; original global network/runtime checks still run after all actions');
replace("  const inputFiles={};", "  await writeFile(path.join(out,'executed-suite.mjs'),await readFile(fileURLToPath(import.meta.url)));\n  const inputFiles={};",'Keep exact executed compatibility suite as raw evidence');
let restored=s;for(const c of changes.toReversed())restored=restored.replace(c.to,c.from);
if(restored!==original)throw Error('ORIGINAL_170_NOT_EXACTLY_RECONSTRUCTIBLE');
await mkdir(path.join(own,'reference'),{recursive:true});await writeFile(path.join(own,'reference/original-170.git-bytes.mjs'),raw);
await writeFile(path.join(own,'compat-170-plus.mjs'),s);
const hash=b=>createHash('sha256').update(b).digest('hex');
await writeFile(path.join(own,'reference/suite-compatibility.json'),JSON.stringify({base,file,originalGitBlob:execFileSync('git',['rev-parse',base+':'+file],{cwd:own,encoding:'utf8'}).trim(),originalSha256:hash(raw),generatedSha256:hash(Buffer.from(s)),originalExactlyReconstructible:true,changes},null,2)+'\n');
console.log('ORIGINAL_170_EXACTLY_RECONSTRUCTIBLE_WITH_DOCUMENTED_ADAPTER');
