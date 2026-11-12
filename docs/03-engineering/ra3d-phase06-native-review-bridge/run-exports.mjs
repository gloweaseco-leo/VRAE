// Capture exact commands, stdout/stderr and exit status; no dependency installs.
import {spawn} from 'node:child_process';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../..');
const sha=b=>createHash('sha256').update(b).digest('hex');
const rows=[];
for(const [label,python]of [['python311','../ra2b3/.venv/Scripts/python.exe'],['python313','../ra2b3/.venv/py313/Scripts/python.exe']]){
  const started=new Date().toISOString(),id=started.replace(/[:.]/g,'-');
  const out=path.join(here,'evidence',label+'-'+id);await mkdir(out,{recursive:true});
  const script=path.join(here,'export_bridge.py'),raw=await readFile(script);
  let stdout='',stderr='';const args=[script];
  const child=spawn(python,args,{cwd:root,windowsHide:true,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONUTF8:'1'}});
  child.stdout.on('data',d=>stdout+=d.toString('utf8'));child.stderr.on('data',d=>stderr+=d.toString('utf8'));
  const exit=await new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',resolve)});
  await writeFile(path.join(out,'stdout.txt'),stdout);await writeFile(path.join(out,'stderr.txt'),stderr);
  const row={python,args,cwd:root,started,ended:new Date().toISOString(),exit,script_sha256:sha(raw),stdout_sha256:sha(Buffer.from(stdout)),stderr_sha256:sha(Buffer.from(stderr))};
  await writeFile(path.join(out,'command.json'),JSON.stringify(row,null,2)+'\n');rows.push(row);
  console.log(JSON.stringify({label,exit,out,stdout:stdout.trim(),stderr:stderr.slice(0,600)}));
  if(exit!==0){process.exitCode=1;break;}
}
