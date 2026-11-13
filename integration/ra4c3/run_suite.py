"""Fresh original P1 v1/v2/P2A + C3, with original sources/assertions intact."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time

from integration.ra4c3 import lab


def run(output, *, browser=False, browser_first=False):
    output = lab.bounded(output)
    output.mkdir(parents=True, exist_ok=False)
    state = output.parent.parent / 'runtime' / (output.name + '-state.json')
    profile = output.parent.parent / 'runtime' / (output.name + '-profile.json')
    records = []
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=lab.ROOT).decode().strip()
    source_files=[]
    for line in git('ls-tree','-r','HEAD','--','apps/operator_console','integration/ra4c3',
                    'vrae','db','infra','tests','.github/workflows',
                    'docs/03-engineering/ra4c3-pg-read/browser-test.mjs',
                    'docs/03-engineering/ra4c3-pg-read/browser-input.mjs').splitlines():
        identity,name=line.split('\t',1)
        mode,kind,blob=identity.split()
        file=lab.ROOT/name
        source_files.append({'path':name,'mode':mode,'git_blob':blob,
            'lf_sha256':hashlib.sha256(file.read_bytes().replace(b'\r\n',b'\n')).hexdigest()})
    (output/'source.json').write_bytes(json.dumps({'actual_head':git('rev-parse','HEAD'),
        'head_and_ordered_parents':git('log','-1','--format=%H %P'),
        'github_sha':os.environ.get('GITHUB_SHA'),'github_run_id':os.environ.get('GITHUB_RUN_ID'),
        'python':sys.version,'runner_argv':sys.argv,'browser_first':browser_first,
        'sources':source_files},indent=2).encode()+b'\n')

    def command(name, argv, extra=None):
        folder = output / name
        folder.mkdir()
        env = dict(os.environ, RA4C3_STATE=str(state), RA4C3_PROFILE=str(profile),
                   RA4A_EVIDENCE_DIR=str(folder), RA4A_P2A_EVIDENCE_DIR=str(folder))
        env.update(extra or {})
        before = time.monotonic()
        p = subprocess.run(argv, cwd=lab.ROOT, env=env, capture_output=True)
        for kind, raw in (('stdout',p.stdout),('stderr',p.stderr)):
            (folder / (kind+'.log')).write_bytes(raw)
        records.append({'stage':name,'argv':argv,'returncode':p.returncode,
                        'seconds':time.monotonic()-before,
                        'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),
                        'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()})
        (output/'commands.json').write_bytes(json.dumps(records,indent=2).encode()+b'\n')
        print(json.dumps(records[-1]),flush=True)
        if p.returncode:
            print(p.stdout.decode(errors='replace')[-5000:],flush=True)
            print(p.stderr.decode(errors='replace')[-1500:],flush=True)
            raise RuntimeError('ACTUAL_SUITE_RED_'+name)

    py = [sys.executable,'-B']
    plugin = ['-p','integration.ra4c3.pytest_adapter']
    def pytest(name, args, extra=None):
        command(name,py+['-m','pytest','-q','--import-mode=importlib',*args,
            '--basetemp='+str(output.parent.parent/'runtime'/('temp-'+output.name+'-'+name)),
            '--junitxml='+str(output/name/'tests.xml')],extra)

    try:
        lab.start(state,output/'startup',option_a_local_trial=True)
        value=json.loads(state.read_text())
        # Compatibility key consumed by original real container restart test.
        value['data_volume']=value['volume']
        state.write_text(json.dumps(value),encoding='utf-8')
        pytest('p1-v1',plugin+['integration/ra4a'])
        command('p2a-migration',py+['-m','integration.ra4c3.lab','migrate','--state',str(state),
            '--output',str(output/'migration-failure-cleanup')])
        pytest('p1-v2',plugin+['integration/ra4a'])
        pytest('p2a',plugin+['-p','integration.ra4a.p2a_plugin','--confcutdir=integration/ra4a/p2a',
            'integration/ra4a/p2a/cases.py','integration/ra4a/p2a/security_cases.py'])
        pytest('pure',['tests/persistence'])
        command('c3-seed',py+['-m','integration.ra4c3.lab','seed','--state',str(state),
            '--profile',str(profile),'--output',str(output/'seed-failure-cleanup')])
        pytest('c3',['integration/ra4c3/test_readside.py','integration/ra4c3/test_lab_cleanup.py',
                     'integration/ra4c3/test_restart_read.py'])
        def chromium():
            command('browser',['node','docs/03-engineering/ra4c3-pg-read/browser-test.mjs'],
                    {'RA4C0_PYTHON':sys.executable})
        if browser and browser_first:
            chromium()
        pytest('full',['tests'])
        if browser and not browser_first:
            chromium()
    finally:
        if state.exists():
            held=json.loads(state.read_text())
            lab.stop(state,output/'teardown')
            with socket.socket() as probe:
                probe.settimeout(2)
                code=probe.connect_ex(('127.0.0.1',held['port']))
            assert code != 0, 'REMOVED_PG_STILL_ACCESSIBLE'
            (output/'closed-port.json').write_bytes(json.dumps({'host':'127.0.0.1',
                'port':held['port'],'connect_ex':code,'closed':True}).encode()+b'\n')
        if profile.exists():
            profile.unlink()


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('output')
    p.add_argument('--browser',action='store_true')
    p.add_argument('--browser-first',action='store_true',
                   help='Local: run actual Chromium before the full pure suite')
    a=p.parse_args()
    if a.browser_first and not a.browser:
        p.error('--browser-first requires --browser')
    run(a.output,browser=a.browser,browser_first=a.browser_first)
