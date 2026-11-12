// Transport-only relocation of the frozen PR56 suite, no assertions changed.
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../../../..');
const old='151cdac7d31580afac4c5624f675cb2915c2f5e2';
const file='docs/03-engineering/ra3d-phase06-native-review-bridge/reviewer-p1/compat-170-plus.mjs';
const original=execFileSync('git',['show',old+':'+file],{cwd:root,encoding:'utf8'});
const replacements=[
  ['const own=path.dirname(fileURLToPath(import.meta.url));',"const own=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');"],
  ["const out=path.join(own,'evidence',(baseline?'baseline-browser-':'reviewer-browser-')+runId);","const out=path.join(path.dirname(fileURLToPath(import.meta.url)),'evidence','browser-'+runId);"]
];
let next=original;for(const [from,to]of replacements){if(next.indexOf(from)<0||next.indexOf(from)!==next.lastIndexOf(from))throw Error('FROZEN_SHAPE_CHANGED');next=next.replace(from,to)}
let restored=next;for(const [from,to]of replacements.toReversed())restored=restored.replace(to,from);if(restored!==original)throw Error('FROZEN_SUITE_CHANGED');
const sha=s=>createHash('sha256').update(s).digest('hex');
await writeFile(path.join(here,'compat-293.mjs'),next);
await writeFile(path.join(here,'suite-pin.json'),JSON.stringify({oldFeature:old,file,original_sha256:sha(original),executed_sha256:sha(next),exact_reconstruction:true,replacements},null,2)+'\n');
console.log('FROZEN_293_TRANSPORT_ONLY_PINNED');
