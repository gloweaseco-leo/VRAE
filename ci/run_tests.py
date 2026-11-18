"""Run the selected original pytest entry, retaining true scope and CPU/wall data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .policy import make_plan


def main():
    plan = json.loads(os.environ['PLAN_JSON'])
    expected = make_plan(plan['actual_paths'], event=plan['event'], mode=plan['mode'], legacy_311=plan['legacy_311'])
    if expected != plan:
        raise ValueError('PLAN_MISMATCH')
    out = Path('ci/.runtime')
    out.mkdir(parents=True, exist_ok=True)
    version = os.environ.get('CI_PYTHON', 'local')
    command = [sys.executable, '-m', 'pytest', '-q', *plan['core_tests'],
               '--junitxml=' + str(out / ('core-' + version + '.xml'))]
    try:
        import resource
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
    except ImportError:
        before = None
    start = time.monotonic()
    completed = subprocess.run(command)
    wall = time.monotonic() - start
    cpu = None
    if before is not None:
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = {'user_seconds': after.ru_utime - before.ru_utime,
               'system_seconds': after.ru_stime - before.ru_stime,
               'scope': 'PYTEST_CHILDREN_ONLY_NOT_DOCKER_OR_WHOLE_RUNNER_CPU'}
    record = {'python': sys.version, 'tier': plan['tier'], 'mode': plan['mode'],
        'command': command, 'exit_code': completed.returncode, 'wall_seconds': wall,
        'cpu': cpu, 'unexecuted_suites': plan['not_executed_families'],
        'business_full_pass_claim': False, 'test_scope': plan['core_tests']}
    (out / ('timing-' + version + '.json')).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record))
    raise SystemExit(completed.returncode)


if __name__ == '__main__':
    main()
