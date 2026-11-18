import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readFile, realpath, stat} from 'node:fs/promises';
import net from 'node:net';

export const spawnOptions=Object.freeze({windowsHide:true,stdio:Object.freeze(['ignore','pipe','pipe'])});

export async function executableIdentity(requestedExecutable) {
  const resolvedExecutable=await realpath(requestedExecutable);
  return {requestedExecutable,resolvedExecutable,executedExecutable:requestedExecutable,
    requestedDiffersFromRealpath:requestedExecutable!==resolvedExecutable,
    sha256:createHash('sha256').update(await readFile(resolvedExecutable)).digest('hex')};
}

export function classify(r) {
  if (r.spawnError) return 'SPAWN_ERROR';
  if (r.endpointAtMs !== null) return 'ENDPOINT_AVAILABLE';
  if (r.exitAtMs !== null && r.exitAtMs <= r.decisionAtMs) return 'CHROME_EXIT_BEFORE_ENDPOINT';
  if (r.aliveAtDecision === true) return 'NO_ENDPOINT_WITH_ALIVE_PROCESS';
  return 'UNKNOWN';
}

// Only traverse children of our child. Never enumerate the machine's processes.
async function ownedTree(pid) {
  if (process.platform !== 'linux' || !pid) return null;
  const rows = [], seen = new Set();
  async function visit(id, parent) {
    if (seen.has(id) || rows.length >= 128) return;
    seen.add(id);
    try {
      const s = await readFile(`/proc/${id}/stat`, 'utf8');
      const fields = s.slice(s.lastIndexOf(')') + 2).split(' ');
      if (Number(fields[1]) !== parent) return;
      rows.push({pid:id, ppid:parent, state:fields[0]});
      const children = await readFile(`/proc/${id}/task/${id}/children`, 'utf8');
      for (const c of children.trim().split(/\s+/).filter(Boolean)) await visit(Number(c), id);
    } catch { /* disappearance is an observation gap, never proof of exit */ }
  }
  await visit(pid, process.pid);
  return rows;
}

function tcp(port) {
  return new Promise(resolve => {
    const socket = net.connect({host:'127.0.0.1', port});
    const finish = value => { socket.destroy(); resolve(value); };
    socket.setTimeout(250, () => finish(false));
    socket.once('connect', () => finish(true));
    socket.once('error', () => finish(false));
  });
}

async function publicVersion(endpoint) {
  return new Promise(resolve=>{
    let ws, timer;
    const finish=value=>{clearTimeout(timer);try {ws?.close();} catch {} resolve(value);};
    timer=setTimeout(()=>finish(null),500);
    try {
      ws=new WebSocket(endpoint);
      ws.addEventListener('error',()=>finish(null),{once:true});
      ws.addEventListener('open',()=>ws.send(JSON.stringify({id:1,method:'Browser.getVersion'})),{once:true});
      ws.addEventListener('message',event=>{
        try {const m=JSON.parse(event.data);if(m.id===1) finish(m.result?.product?.match(/\b\d+\.\d+\.\d+\.\d+\b/)?.[0]??null);} catch {finish(null);}
      });
    } catch {finish(null);}
  });
}

export async function observe({bin, args, deadlineMs, profile=null, connect=true}) {
  if (!Number.isInteger(deadlineMs) || deadlineMs < 1 || deadlineMs > 30000) throw Error('INVALID_DEADLINE');
  const start = process.hrtime.bigint();
  const now = () => Number(process.hrtime.bigint()-start)/1e6;
  const r = {schema:1, nodePid:process.pid, nodeParentPid:process.ppid, childPid:null,
    deadlineMs, spawnAtMs:null, spawnError:null, exitAtMs:null, exitCode:null,
    signal:null, closeAtMs:null, endpointAtMs:null, endpointPort:null,
    connected:null, aliveAtDecision:null, decisionAtMs:null, tree:null,
    profileExists:null, activePortFileExists:null, stderrBytes:0, cleanup:{}};
  const digest = createHash('sha256');
  let tail='', endpoint=null, decide, decisionMade=false;
  const decision = new Promise(resolve => { decide=resolve; });
  const finish = () => { if (!decisionMade) { decisionMade=true; r.decisionAtMs=now(); decide(); } };
  const child = spawn(bin,args,spawnOptions);
  // Preserve the original stdout PIPE and its unread/backpressure behavior.
  // The frozen launchers do not consume stdout, so neither does this observer.
  r.childPid=child.pid??null;
  child.once('spawn',()=>{r.spawnAtMs=now();});
  child.once('error',e=>{r.spawnError=['ENOENT','EACCES','EPERM'].includes(e.code)?e.code:'OTHER';finish();});
  child.once('exit',(code,signal)=>{r.exitAtMs=now();r.exitCode=code;r.signal=signal;finish();});
  const closed = new Promise(resolve=>child.once('close',()=>{r.closeAtMs=now();resolve();}));
  child.stderr.on('data',b=>{
    r.stderrBytes+=b.length;digest.update(b);
    tail=(tail+b.toString('utf8')).slice(-4096);
    const m=tail.match(/ws:\/\/127\.0\.0\.1:(\d+)\/devtools\/browser\/[\w-]+/);
    if (m && !decisionMade && now()<=deadlineMs && Number(m[1])<=65535) {
      endpoint=m[0];r.endpointAtMs=now();r.endpointPort=Number(m[1]);finish();
    }
  });
  const timer=setTimeout(()=>{
    if (child.pid && r.exitAtMs===null && !r.spawnError) {
      try { process.kill(child.pid,0);r.aliveAtDecision=true; } catch { r.aliveAtDecision=null; }
    }
    finish();
  },deadlineMs);
  await decision;clearTimeout(timer);
  // Classification is fixed before cleanup: our own termination cannot imply a startup exit.
  r.classification=classify(r);
  r.tree=await ownedTree(child.pid);
  r.executable=null;
  if(process.platform==='linux' && r.tree?.some(p=>p.pid===child.pid)) {
    try {
      const exe=`/proc/${child.pid}/exe`;
      const info=await stat(exe);
      if(info.size<=512*1024*1024) r.executable={path:await realpath(exe),sha256:createHash('sha256').update(await readFile(exe)).digest('hex')};
    } catch { /* exited or inaccessible: leave actual executable UNKNOWN */ }
  }
  if (profile) {
    r.profileExists=await stat(profile).then(s=>s.isDirectory(),()=>null);
    r.activePortFileExists=await stat(`${profile}/DevToolsActivePort`).then(s=>s.isFile(),e=>e.code==='ENOENT'?false:null);
  }
  r.browserVersion=null;
  if (endpoint && connect) {
    r.connected=await tcp(r.endpointPort);
    if(r.connected) r.browserVersion=await publicVersion(endpoint);
  }
  r.cleanup.termRequested=false;r.cleanup.killRequested=false;
  if (child.pid && r.exitAtMs===null) { r.cleanup.termRequested=child.kill('SIGTERM'); }
  async function waitClose(ms) {
    let t;const result=await Promise.race([closed.then(()=>true),new Promise(resolve=>{t=setTimeout(()=>resolve(false),ms);})]);
    clearTimeout(t);return result;
  }
  if (!await waitClose(1000) && child.pid && r.exitAtMs===null) r.cleanup.killRequested=child.kill('SIGKILL');
  r.cleanup.closeObserved=await waitClose(1000);
  r.binaryExitCategory=r.exitAtMs===null?'UNOBSERVED':r.signal?'SIGNALLED':r.exitCode===0?'EXIT_ZERO':'EXIT_NONZERO';
  if (!r.cleanup.closeObserved) { child.stdout.destroy(); child.stderr.destroy(); child.unref(); }
  r.stderrSha256=digest.digest('hex');
  // No stderr text, endpoint UUID, environment or profile content leaves this function.
  return r;
}
