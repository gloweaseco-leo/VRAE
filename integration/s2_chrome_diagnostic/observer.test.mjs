import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {observe,classify} from './observer.mjs';
import {sources,contract} from './run.mjs';
const fixture=fileURLToPath(new URL('./fixture.mjs',import.meta.url));
const run=mode=>observe({bin:process.execPath,args:[fixture,mode],deadlineMs:1500});
test('spawn error cannot pass as endpoint',async()=>{
  const r=await observe({bin:fileURLToPath(new URL('./does-not-exist',import.meta.url)),args:[],deadlineMs:500});
  assert.equal(r.classification,'SPAWN_ERROR');assert.equal(r.spawnError,'ENOENT');assert.equal(r.cleanup.closeObserved,true);
});
test('early exit, normal exit, byte fingerprint and no raw stderr',async()=>{
  for(const [mode,code] of [['early',7],['normal',0]]) {
    const r=await run(mode);assert.equal(r.classification,'CHROME_EXIT_BEFORE_ENDPOINT');
    assert.equal(r.exitCode,code);assert.ok(r.exitAtMs>=r.spawnAtMs);assert.ok(r.closeAtMs>=r.exitAtMs);
    assert.equal(r.stderrSha256,createHash('sha256').update(code?'synthetic-secret-never-persist':'').digest('hex'));
    assert.equal(JSON.stringify(r).includes('synthetic-secret'),false);
  }
});
test('live no-endpoint decision precedes owned cleanup',async()=>{
  const r=await run('alive');assert.equal(r.classification,'NO_ENDPOINT_WITH_ALIVE_PROCESS');
  assert.equal(r.aliveAtDecision,true);assert.ok(r.decisionAtMs>=1500);assert.ok(r.exitAtMs>r.decisionAtMs);
  assert.equal(r.cleanup.closeObserved,true);
});
test('endpoint publication and connection are distinct observations',async()=>{
  for(const [mode,connected] of [['endpoint',true],['endpoint-closed',false]]) {
    const r=await run(mode);assert.equal(r.classification,'ENDPOINT_AVAILABLE');
    assert.equal(r.connected,connected);assert.ok(r.endpointAtMs<1500);assert.equal(r.cleanup.closeObserved,true);
  }
});
test('endpoint present but intentionally not connected',async()=>{
  const r=await observe({bin:process.execPath,args:[fixture,'endpoint'],deadlineMs:1500,connect:false});
  assert.equal(r.classification,'ENDPOINT_AVAILABLE');assert.equal(r.connected,null);
});
test('missing liveness and lifecycle evidence remains UNKNOWN',()=>{
  assert.equal(classify({spawnError:null,endpointAtMs:null,exitAtMs:null,aliveAtDecision:null,decisionAtMs:20}),'UNKNOWN');
});
test('frozen source flags are identical except owned profile; deadlines stay 20s/30s',async()=>{
  const a=await contract(sources[0],'/owned/synthetic'),b=await contract(sources[1],'/owned/synthetic');
  assert.deepEqual(a.args,b.args);assert.equal(a.deadlineMs,20000);assert.equal(b.deadlineMs,30000);
  assert.ok(a.args.includes('--proxy-server=http://127.0.0.1:9'));
  assert.ok(a.args.includes('--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1'));
  await assert.rejects(contract({...sources[0],blob:'0'.repeat(40)},'/owned/synthetic'),/FROZEN_SOURCE_MISMATCH/);
});
test('deadline extension rejected',async()=>{
  await assert.rejects(observe({bin:process.execPath,args:[],deadlineMs:60000}),/INVALID_DEADLINE/);
});
