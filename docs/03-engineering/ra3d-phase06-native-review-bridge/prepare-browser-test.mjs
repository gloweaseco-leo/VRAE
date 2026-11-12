// Reuse the accepted Phase0.5 CDP harness verbatim; replace only test cases/input list.
import {execFileSync} from 'node:child_process';
import {writeFile,readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));
const original=execFileSync('git',['show','696d4ae695041f0eeefa56d22039682a989380b2:docs/03-engineering/ra3d-phase05-prototype/browser-test.mjs'],{cwd:here,encoding:'utf8'});
const inputs="['index.html','bridge.css','bridge-fixture.js','bridge-view.js','dossier-data.js','browser-test.mjs']";
const oldInputs="['index.html','workbench.css','workbench.js','fixtures.js','fixtures.json','browser-test.mjs']";
const marker="  for(const width of [1280,375,320]){";
if(!original.includes(marker)||!original.includes(oldInputs))throw Error('PINNED_HARNESS_SHAPE_CHANGED');
const prefix=original.slice(0,original.indexOf(marker)).replace(oldInputs,inputs).replace("scope:'SYNTHETIC_UI_ONLY_NOT_PRODUCTION_RA3D'","scope:'NATIVE_READONLY_SYNTHETIC_UI_NOT_PRODUCTION'");
const tests=await readFile(path.join(here,'browser-cases.txt'),'utf8');
const tail=original.slice(original.indexOf('}catch(e){infrastructureError='))
  .replace(oldInputs,inputs).replace("scope:'SYNTHETIC_UI_ONLY_NOT_PRODUCTION_RA3D'","scope:'NATIVE_READONLY_SYNTHETIC_UI_NOT_PRODUCTION'");
await writeFile(path.join(here,'browser-test.mjs'),'// Generated from pinned Phase0.5 harness + browser-cases.txt.\n'+prefix+tests+tail);
console.log('BROWSER_TEST_PREPARED_FROM_ACCEPTED_PHASE05');
