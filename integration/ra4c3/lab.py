"""Owned PG16 fixture bootstrap. Admin state never enters the HTTP process.

Only this new integration directory and the RA4C3 proof directory are writable;
the original migrations/lab/tests are read and reused without file edits.
"""
import argparse
import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
OWN=ROOT/'docs/03-engineering/ra4c3-pg-read'
LABEL='vrae.ra4c3'


def bounded(path):
    path=Path(path).resolve()
    assert path.is_relative_to(OWN.resolve())
    return path


def docker(*args, data=None, timeout=60):
    r=subprocess.run(['docker',*args],input=data,capture_output=True,timeout=timeout)
    if r.returncode:
        # Commands containing passwords are never used; Docker env is a temp file.
        raise RuntimeError('OWNED_DOCKER_COMMAND_FAILED_'+args[0])
    return r.stdout.decode().strip()


def wire(state_path):
    path=bounded(state_path)
    import integration.ra4a.support as original
    import integration.ra4a.p2a_support as p2a
    original.STATE=path
    p2a.STATE=path
    return original,p2a


def start(state_path, output, *, option_a_local_trial=False):
    state_path, output = bounded(state_path), bounded(output)
    # Never adopt an earlier run or delete its state on a failed new invocation.
    assert not state_path.exists() and not output.exists()
    try:
        if option_a_local_trial:
            _start(state_path, output, option_a_local_trial=True)
        else:
            _start(state_path, output)
    except BaseException:
        receipt = output / 'ownership.json'
        if receipt.exists():
            cleanup_owned(json.loads(receipt.read_text(encoding='utf-8')),
                          output / 'failure-cleanup')
        if state_path.exists():
            state_path.unlink()
        raise


def _start(state_path, output, *, option_a_local_trial=False):
    state_path,output=bounded(state_path),bounded(output)
    assert not state_path.exists()
    output.mkdir(parents=True,exist_ok=False)
    ident='vrae-ra4c3-'+uuid.uuid4().hex[:12]
    image=(ROOT/'infra/ra4a/image.txt').read_text().strip()
    state={'container':ident,'network':ident+'-local','volume':ident+'-data',
           'image':image,'host':'127.0.0.1','dbname':'vrae_ra4a_p1',
           'admin_password':secrets.token_urlsafe(32),
           'runtime_passwords':{n:secrets.token_urlsafe(24) for n in (
               'ra4a_test_a_app','ra4a_test_b_app','ra4a_test_a_worker',
               'ra4a_test_b_worker','ra4a_test_unassigned')}}
    state_path.parent.mkdir(parents=True,exist_ok=True)
    # Ownership receipt contains no credentials; partial startup is cleanable.
    public={k:state[k] for k in ('container','network','volume','image')}
    (output/'ownership.json').write_text(json.dumps(public,indent=2)+'\n',encoding='utf-8')
    # Owner comment 6843166796: one disposable synthetic local transport trial.
    # Ordinary bridge does NOT enforce kernel egress isolation.
    state['option_a_local_trial'] = option_a_local_trial
    network_args = [] if option_a_local_trial else ['--internal']
    docker('network','create',*network_args,'--label',LABEL+'=TEST_ONLY',state['network'])
    docker('volume','create','--label',LABEL+'=TEST_ONLY',state['volume'])
    with tempfile.NamedTemporaryFile(mode='w',delete=False) as f:
        f.write('POSTGRES_PASSWORD='+state['admin_password']+'\nPOSTGRES_DB=vrae_ra4a_p1\nPOSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n')
        config=Path(f.name)
    try:
        docker('run','-d','--name',ident,'--network',state['network'],'--label',LABEL+'=TEST_ONLY',
               '--env-file',str(config),'-p','127.0.0.1::5432','--mount',
               'type=volume,src='+state['volume']+',dst=/var/lib/postgresql/data',
               '--memory','512m','--cpus','1','--pids-limit','128',image)
    finally:
        config.unlink()
    binding=docker('port',ident,'5432/tcp')
    assert binding.startswith('127.0.0.1:') and '\n' not in binding
    state['port']=int(binding.rsplit(':',1)[1])
    state_path.write_text(json.dumps(state),encoding='utf-8')
    original,_=wire(state_path)
    deadline=time.monotonic()+60
    import psycopg
    while True:
        try:
            with original.connect() as c:
                row=c.execute("SELECT current_database(),current_setting('server_version_num')::int").fetchone()
                assert row[0]=='vrae_ra4a_p1' and 160000<=row[1]<170000
                break
        except psycopg.OperationalError:
            if time.monotonic()>=deadline:
                raise RuntimeError('OWNED_PG_STARTUP_DEADLINE') from None
            time.sleep(.25)
    digests=json.loads(docker('image','inspect','--format','{{json .RepoDigests}}',image))
    assert any(d.endswith('@'+image.split('@')[1]) for d in digests)
    (output/'ready.json').write_text(json.dumps({**public,'server_version_num':row[1],
        'loopback_only':True,'image_digest_verified':True},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'event':'OWNED_PG16_READY','container':ident,'version':row[1]}),flush=True)


def migrate(state_path, p2a=True):
    original,private=wire(state_path)
    original.migrate()
    if p2a:
        private.migrate_p2a()
    return original,private


def seed(state_path, profile, role='ra4a_test_a_app'):
    from psycopg import sql
    from vrae.persistence.private_postgres import TestOnlyPrivateBytes
    original,p2a=migrate(state_path)
    p2a.seed_base()
    name='vrae_p2a_'+uuid.uuid4().hex[:12]
    with original.connect(dbname='postgres') as c:
        c.execute(sql.SQL('CREATE DATABASE {} TEMPLATE vrae_ra4a_p1').format(sql.Identifier(name)))
    with original.connect(dbname=name) as c:
        c.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
        c.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO ra4a_app,ra4a_worker,p2a_fixture_writer').format(sql.Identifier(name)))
    with original.connect('p2a_test_a_writer',dbname=name) as writer:
        port=TestOnlyPrivateBytes(writer,mode='TEST_ONLY_PRIVATE_BYTES_PG16')
        for case in ('404','200'):
            g=p2a.graph(case)
            port.register(g,provenance=g)
    state=json.loads(bounded(state_path).read_text(encoding='utf-8'))
    value={'mode':'TEST_ONLY_PRIVATE_BYTES_PG16','host':'127.0.0.1','port':state['port'],
           'dbname':name,'user':role,'password':state['runtime_passwords'][role]}
    profile=bounded(profile)
    profile.parent.mkdir(parents=True,exist_ok=True)
    profile.write_text(json.dumps(value),encoding='utf-8')
    print(json.dumps({'event':'SYNTHETIC_ORIGINAL_BYTE_GRAPHS_SEEDED','cases':['404','200'],
        'profile_role':role,'admin_in_profile':False}),flush=True)
    return name


def cleanup_owned(state, output):
    output=bounded(output)
    assert re.fullmatch(r'vrae-ra4c3-[0-9a-f]{12}',state['container'])
    assert state['network']==state['container']+'-local' and state['volume']==state['container']+'-data'
    output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for kind,key in (('container','container'),('network','network'),('volume','volume')):
        name=state[key]
        args=['inspect','--format','{{json .Config.Labels}}',name] if kind=='container' else [kind,'inspect','--format','{{json .Labels}}',name]
        probe=subprocess.run(['docker',*args],capture_output=True)
        if probe.returncode==0:
            assert json.loads(probe.stdout)[LABEL]=='TEST_ONLY'
            docker(*(['rm','-f',name] if kind=='container' else [kind,'rm',name]))
        else:
            assert b'no such' in probe.stderr.lower() or b'not found' in probe.stderr.lower()
        absent=subprocess.run(['docker',kind,'inspect',name],capture_output=True)
        assert absent.returncode and (b'no such' in absent.stderr.lower() or b'not found' in absent.stderr.lower())
        rows.append({'kind':kind,'name':name,'absent_after':True})
    (output/'teardown.json').write_text(json.dumps({'owned_only':True,'resources':rows},indent=2)+'\n',encoding='utf-8')
    print('OWNED_RA4C3_CONTAINER_NETWORK_VOLUME_ABSENT',flush=True)


def stop(state_path, output):
    state_path = bounded(state_path)
    cleanup_owned(json.loads(state_path.read_text(encoding='utf-8')), output)
    state_path.unlink()


def bootstrap_action(action, state_path, output, profile=None):
    """Migration/seed CLI failures tear down only this run's verified resources."""
    state_path = bounded(state_path)
    assert state_path.exists()
    try:
        if action == 'migrate':
            migrate(state_path)
        else:
            assert action == 'seed'
            seed(state_path, profile)
    except BaseException:
        stop(state_path, output)
        # Failed credential profile must not survive a partial bootstrap.
        if profile is not None:
            profile = bounded(profile)
            if profile.exists():
                profile.unlink()
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('start','migrate','seed','stop'))
    parser.add_argument('--state',required=True)
    parser.add_argument('--output')
    parser.add_argument('--profile')
    parser.add_argument('--option-a-local-trial', action='store_true')
    args=parser.parse_args()
    if args.action=='start':
        start(args.state,args.output,option_a_local_trial=args.option_a_local_trial)
    elif args.action in ('migrate', 'seed'):
        assert args.output is not None
        bootstrap_action(args.action, args.state, args.output, args.profile)
    else:
        stop(args.state,args.output)
