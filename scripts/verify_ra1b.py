"""Host-only disposable lab supervisor. Never mounted into either workload."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import threading
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
parser.add_argument('--cases', nargs='+', default=['readonly', 'writes', 'private', 'resources',
    'channels', 'escape', 'storage', 'redirect', 'redirect_private', 'rebinding',
    'infinite', 'memory', 'revocation', 'crash', 'sigkill', 'worker_kill'])
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
root = Path(__file__).resolve().parents[1]
profile = str(root / 'infra/ra1b/seccomp.json')
browser = 'vrae-ra1b-browser:local'
worker = 'vrae-ra1b-worker:local'
common = ['--network', 'none', '--read-only', '--security-opt', 'no-new-privileges',
          '--memory', '512m', '--cpus', '1', '--pids-limit', '256',
          '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m']
results = []


def run(name, command, timeout=50, required=True):
    started = time.time()
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=timeout)
        code, output = result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        output = str(exc)
    (args.output / (name + '.log')).write_text(
        'COMMAND=' + repr(command) + '\n' + output + f'\nEXIT_CODE={code}\n', encoding='utf-8')
    results.append({'name': name, 'command': command, 'exit_code': code, 'seconds': time.time() - started})
    print(name, 'EXIT_CODE', code, flush=True)
    if code and required:
        raise RuntimeError('SECURITY_BLOCKED: ' + name)
    return code, output


def inspect(name, label):
    run(label, ['docker', 'inspect', name])


try:
    for suffix, extra in [('control', []), ('deny', ['--security-opt', 'seccomp=' + profile])]:
        run('kernel-' + suffix, ['docker', 'run', '--rm', *common, '--cap-drop', 'ALL', *extra,
            '--entrypoint', 'python', browser, '/opt/kernel_probe.py', *(['--control'] if suffix == 'control' else [])])
    run('sandbox', ['docker', 'run', '--rm', *common, '--cap-drop', 'ALL',
        '--security-opt', 'seccomp=' + profile, '--entrypoint', 'python', browser, '/opt/preflight.py'], timeout=40)
    for case in args.cases:
        task = 'vrae-b1-' + uuid.uuid4().hex[:12]
        bname, wname, volume = task + '-browser', task + '-worker', task + '-ipc'
        try:
            run(case + '-volume', ['docker', 'volume', 'create', '--driver', 'local',
                '--opt', 'type=tmpfs', '--opt', 'device=tmpfs', '--opt',
                'o=size=1m,uid=10001,gid=10003,mode=0770', volume])
            run(case + '-volume-config', ['docker', 'volume', 'inspect', volume])
            run(case + '-browser-start', ['docker', 'run', '-d', '--name', bname, *common,
                '--cap-drop', 'ALL', '--security-opt', 'seccomp=' + profile,
                '--mount', f'type=volume,src={volume},dst=/ipc', browser])
            inspect(bname, case + '-browser-config')
            # Readiness is bounded and does not connect to the control socket.
            run(case + '-ready', ['docker', 'exec', bname, 'python', '-c',
                "import pathlib,time\np=pathlib.Path('/ipc/cdp.sock')\n"
                "for _ in range(100):\n if p.exists(): break\n time.sleep(.05)\n"
                "assert p.exists()"], timeout=10)
            killer = None
            if case in ('sigkill', 'worker_kill'):
                def kill_after_ready():
                    for _ in range(100):
                        logs = subprocess.run(['docker', 'logs', wname], capture_output=True, text=True)
                        if 'KILL_READY' in logs.stdout:
                            run(case + '-kill', ['docker', 'kill', '--signal', 'KILL',
                                                wname if case == 'worker_kill' else bname])
                            return
                        time.sleep(0.2)
                killer = threading.Thread(target=kill_after_ready)
                killer.start()
            code, _ = run(case + '-worker', ['docker', 'run', '--name', wname, *common,
                '--cap-add', 'NET_ADMIN', '--env', 'VRAE_BROWSER_CASE=' + case,
                '--mount', f'type=volume,src={volume},dst=/ipc', worker], timeout=40, required=False)
            if killer:
                killer.join(timeout=5)
                if killer.is_alive():
                    raise RuntimeError('SECURITY_BLOCKED: kill supervisor did not finish')
            inspect(wname, case + '-worker-config')
            run(case + '-browser-log', ['docker', 'logs', bname], required=False)
            _, final_state = run(case + '-browser-final-state', ['docker', 'inspect', bname])
            if json.loads(final_state)[0]['State']['Running']:
                raise RuntimeError('SECURITY_BLOCKED: browser did not exit after control disconnect')
            if code != (137 if case == 'worker_kill' else 0):
                raise RuntimeError('SECURITY_BLOCKED: ' + case)
        finally:
            run(case + '-remove', ['docker', 'rm', '-f', bname, wname], required=False)
            run(case + '-volume-remove', ['docker', 'volume', 'rm', volume])
            code, _ = run(case + '-cleanup-proof', ['docker', 'inspect', bname, wname], required=False)
            if code == 0:
                raise RuntimeError('SECURITY_NO_GO: workload remains')
finally:
    (args.output / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
