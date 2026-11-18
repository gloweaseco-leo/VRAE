"""One passive Linux supervisor around the unchanged original RA4C3 suite.

No preload, ptrace, injected Node hooks, pipe replacement inside the suite,
extra Chrome connection, machine-wide process/port scan, or test retry.
Sampling cannot prove a descendant's exit or pipe close; these stay UNKNOWN.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = 'docs/03-engineering/ra4c3-pg-read/browser-test.mjs'
PIN = '3cf73d4ec0397acdca3d988ac4332ef7dfcf258b'
OUTPUT = ROOT / 'docs/03-engineering/ra4c3-pg-read/evidence/s2-d0-supervised-once'


def snapshot(pid, parent):
    """Read only a verified descendant, never /proc directory listings."""
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        if int(fields[1]) != parent:
            return None
        return {'pid': pid, 'ppid': parent, 'state': fields[0], 'startTicks': fields[19]}
    except (OSError, ValueError, IndexError):
        return None


def descendants(pid, parent, limit=128):
    rows = []

    def visit(current, owner):
        if len(rows) >= limit:
            return
        row = snapshot(current, owner)
        if row is None:
            return
        rows.append(row)
        try:
            children = Path(f'/proc/{current}/task/{current}/children').read_text().split()
        except OSError:
            return
        for child in children:
            visit(int(child), current)
    visit(pid, parent)
    return rows


def expected_args(source, profile):
    literal = re.search(r'chrome=spawn\(chromePath,(\[[^\n]+?\]),\{windowsHide:true', source)[1]
    literal = literal.replace('`--user-data-dir=${profile}`', repr('--user-data-dir=' + profile))
    return ast.literal_eval(literal)


def main():
    if sys.platform != 'linux':
        raise RuntimeError('LINUX_ONLY')
    if OUTPUT.exists():
        raise RuntimeError('SINGLE_ATTEMPT_OUTPUT_ALREADY_EXISTS')
    source = (ROOT / ORIGINAL).read_text()
    blob = subprocess.check_output(['git', 'hash-object', '--path', ORIGINAL, ORIGINAL], cwd=ROOT).decode().strip()
    if blob != PIN or ',20000);chrome.on(\'error\'' not in source:
        raise RuntimeError('FROZEN_CONTRACT_MISMATCH')
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Exclusive receipt claim prevents a second supervisor instance in this workspace.
    claim = output / 'supervisor-claim.json'
    with claim.open('x') as handle:
        json.dump({'pid': os.getpid(), 'attempts': 1}, handle)
    argv = [sys.executable, '-B', '-m', 'integration.ra4c3.run_suite', str(OUTPUT), '--browser']
    started = time.monotonic()
    now = lambda: (time.monotonic() - started) * 1000
    child = subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    streams = {}

    def drain(name, pipe):
        count, digest = 0, hashlib.sha256()
        while chunk := pipe.read(65536):
            count += len(chunk)
            digest.update(chunk)
        streams[name] = {'bytes': count, 'sha256': digest.hexdigest(), 'eofAtMs': now()}
        pipe.close()

    threads = [threading.Thread(target=drain, args=(name, pipe), daemon=True)
               for name, pipe in [('stdout', child.stdout), ('stderr', child.stderr)]]
    for thread in threads:
        thread.start()
    observed = {}
    chrome = {}
    deadline = started + 40 * 60
    expired = False
    while child.poll() is None:
        if time.monotonic() >= deadline:
            expired = True
            child.terminate()
            break
        rows = descendants(child.pid, os.getpid())
        owned_nodes = set()
        for row in rows:
            pid = row['pid']
            try:
                exe = Path(f'/proc/{pid}/exe').resolve(strict=True)
                # Read argv only for the owned Node/Chrome executables; never env.
                if exe.name not in ('node', 'chrome', 'chromium'):
                    continue
                args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
                args = [arg.decode(errors='replace') for arg in args if arg]
            except OSError:
                continue
            key = f"{pid}:{row['startTicks']}"
            if exe.name == 'node' and args[1:] == [ORIGINAL]:
                owned_nodes.add(pid)
                observed.setdefault(key, {**row, 'role': 'original-browser-node', 'firstSeenMs': now()})
                observed[key]['lastSeenMs'] = now()
            if row['ppid'] not in owned_nodes or exe.name not in ('chrome', 'chromium'):
                continue
            profiles = [arg.split('=', 1)[1] for arg in args if arg.startswith('--user-data-dir=')]
            if len(profiles) != 1:
                continue
            profile = Path(profiles[0]).resolve()
            runtime = ROOT / 'docs/03-engineering/ra4c3-pg-read/runtime'
            if profile.parent != runtime or not profile.name.startswith('browser-profile-'):
                continue
            if key not in chrome:
                chrome[key] = {**row, 'firstSeenMs': now(), 'lastSeenMs': now(),
                               'argsMatchOriginal': args[1:] == expected_args(source, str(profile)),
                               'executable': str(exe), 'executableSha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
                               'activePortFileFirstSeenMs': None, 'portFromOwnedFile': None,
                               'chromeExitEvent': None, 'chromeCloseEvent': None,
                               'originalGateEvent': None, 'originalGateDeadlineMs': 20000,
                               'endpointListening': None, 'gateSample': None}
            entry = chrome[key]
            entry['lastSeenMs'] = now()
            entry['lastState'] = row['state']
            try:
                with (profile / 'DevToolsActivePort').open('rb') as handle:
                    port_line = handle.read(4096).splitlines()[0]
                if port_line.isdigit() and 0 < int(port_line) <= 65535:
                    if entry['activePortFileFirstSeenMs'] is None:
                        entry['activePortFileFirstSeenMs'] = now()
                        entry['portFromOwnedFile'] = int(port_line)
            except (OSError, IndexError):
                pass
            if entry['gateSample'] is None and now() - entry['firstSeenMs'] >= 20000:
                entry['gateSample'] = {'observedAliveAtMs': now(), 'basis': 'first-seen plus 20s; NOT original timer event'}
        time.sleep(0.05)
    try:
        code = child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        code = child.wait(timeout=5)
    exit_at = now()
    for thread in threads:
        thread.join(timeout=2)
    receipt = {
        'schema': 1, 'supervisorInstances': 1, 'originalCommand': argv,
        'originalBlob': blob, 'originalDeadlineMs': 20000,
        'supervisorPid': os.getpid(), 'originalSuitePid': child.pid,
        'originalSuiteExitCode': code, 'suiteExitObservedAtMs': exit_at,
        'boundedSuiteExpired': expired, 'outerStreams': streams,
        'requestedChromeExecutable': os.environ['RA4C0_CHROMIUM'],
        'requestedChromeRealpath': str(Path(os.environ['RA4C0_CHROMIUM']).resolve()),
        'observedNodes': list(observed.values()), 'observedChrome': list(chrome.values()),
        'conclusion': '2_VALID_OBSERVATIONS_CAUSE_UNKNOWN' if chrome and all(r['argsMatchOriginal'] for r in chrome.values()) else '3_EQUIVALENCE_UNPROVEN_HOLD',
        'gaps': ['Passive sampling cannot observe descendant exit/close callbacks or original timer callback.',
                 'DevToolsActivePort file is publication evidence, not proof of a listening endpoint.',
                 'Polling adds observation work; no causal equivalence to historical runners is claimed.',
                 'No new Chrome connection, injected hook or modification to original pipes/flags/deadlines.',
                 'The historical three RED jobs remain RED/UNKNOWN.'],
    }
    (output / 'supervised-chain.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'conclusion': receipt['conclusion'], 'suiteExitCode': code, 'ownedChromeObserved': len(chrome)}))
    return code if code >= 0 else 1


if __name__ == '__main__':
    sys.exit(main())
