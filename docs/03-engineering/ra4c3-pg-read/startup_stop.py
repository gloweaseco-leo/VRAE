"""Read-only startup diagnosis and removal of exactly this owned failed lab."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE=Path(__file__).resolve().parent
folder=HERE/'evidence/startup-01'
ownership=json.loads((folder/'ownership.json').read_text(encoding='utf-8'))
ident=ownership['container']
assert re.fullmatch(r'vrae-ra4c3-[0-9a-f]{12}',ident)
assert ownership['network']==ident+'-local' and ownership['volume']==ident+'-data'


def run(*args):
    return subprocess.run(['docker',*args],capture_output=True,timeout=30)


proof={'state':'RA4C3_REAL_PG_STARTUP_HARD_STOP','authority':'Issue #73: Real runtime failures, source mismatch or production-like grant are hard STOP.',
       'ownership':ownership,'database_migrations_executed':False,'http_process_started':False,
       'real_model_calls':0,'native_decisions':0,'share_grants':0,'diagnostics':[],'cleanup':[]}
for name,args in (
    ('state',['inspect','--format','{{json .State}}',ident]),
    ('published_ports',['inspect','--format','{{json .NetworkSettings.Ports}}',ident]),
    ('port_command',['port',ident,'5432/tcp']),
    ('postgres_startup_log',['logs','--tail','60',ident]),
):
    result=run(*args)
    raw=result.stdout+result.stderr
    (folder/(name+'.log')).write_bytes(raw)
    proof['diagnostics'].append({'name':name,'exit':result.returncode,'file':name+'.log',
                                 'sha256':hashlib.sha256(raw).hexdigest()})
for kind,key in (('container','container'),('network','network'),('volume','volume')):
    name=ownership[key]
    template='{{json .Config.Labels}}' if kind=='container' else '{{json .Labels}}'
    check=run('inspect','--format',template,name) if kind=='container' else run(kind,'inspect','--format',template,name)
    assert check.returncode==0
    assert json.loads(check.stdout)['vrae.ra4c3']=='TEST_ONLY'
    removed=run('rm','-f',name) if kind=='container' else run(kind,'rm',name)
    assert removed.returncode==0
    absent=run(kind,'inspect',name)
    assert absent.returncode!=0 and (b'no such' in absent.stderr.lower() or b'not found' in absent.stderr.lower())
    proof['cleanup'].append({'kind':kind,'name':name,'label_verified':True,'absent_after':True})
(folder/'HARD_STOP.json').write_bytes(json.dumps(proof,indent=2).encode()+b'\n')
print(json.dumps({'state':proof['state'],'diagnostics':proof['diagnostics'],'cleanup':proof['cleanup']},indent=2))
