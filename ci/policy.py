"""Closed path allowlist, conservative safety closure, explicit unexecuted suites."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = '4a227f1b58afc97d8af1778a066f37b80ff0f399'


def inventory():
    return json.loads((ROOT / 'ci/workflows.json').read_text(encoding='utf-8'))


ALL_FAMILIES = tuple(row['family'] for row in inventory()['workflows'])
OLD_COMMON_FAMILIES = tuple(row['family'] for row in inventory()['workflows'] if row['old_unconditional_pr'])
SECURITY_SMOKE = ['tests/evidence/test_site_coherence.py', 'tests/collection/test_security.py',
    'tests/interpretation/test_guard.py', 'tests/interpretation/test_fixed_replay.py',
    'tests/reviewing/test_strict_metadata.py', 'tests/evidence_perf/freeze_cases.py']
FAST_S2 = {'vrae/reporting/s2_candidate.py', 'vrae/rules/s2/static.py', 'vrae/rules/s2/industrial.py',
    'vrae/industry/l2_v1/s2_sources.py', 'industry-packs/l2-industrial-v1/s2-1.1.0.json',
    'tests/s2_contract/p1_static_cases.py', 'tests/s2_contract/p1_industrial_cases.py',
    'tests/s2_contract/buyer_candidate_cases.py', 'tests/s2_contract/batch2_fixtures.py'}
SECURITY_PREFIXES = ('vrae/evidence/', 'vrae/interpretation/', 'vrae/findings/', 'vrae/collection/',
    'vrae/browser/', 'vrae/reviewing/', 'vrae/application/', 'vrae/reporting/', 'vrae/industry/',
    'vrae/rules/', 'contracts/', 'worker/', 'db/', 'apps/', 'tests/evidence/', 'tests/interpretation/',
    'tests/reviewing/', 'tests/collection/', 'integration/')


def classify(paths):
    tier, families, reasons = 'FAST', set(), []
    if not paths:
        return 'FULL', set(ALL_FAMILIES), ['NO_RELIABLE_CHANGED_PATHS']
    for path in paths:
        if not isinstance(path, str) or not path or '\\' in path or path.startswith('/') or '..' in path.split('/'):
            tier = 'FULL'
            reasons.append('UNSUPPORTED_PATH')
        elif path in FAST_S2:
            families.add('s2_rule_contract')
            if 'industrial' in path or 'industry' in path:
                families.add('l2_industrial')
        elif path.startswith('integration/s2_buyer_workbench/'):
            families.update(('s2_rule_contract', 's2_buyer_workbench'))
        elif path == 'vrae/rules/s2_ux.py' or path.startswith('integration/s2_ux/'):
            families.update(('s2_rule_contract', 's2_ux'))
        elif path.startswith(('.github/', 'ci/', 'infra/')) or path.startswith('requirements') or path in ('pyproject.toml', '.python-version'):
            tier = 'FULL'
            reasons.append('CI_DEPENDENCY_OR_RUNTIME_CONTRACT')
        elif path.startswith(SECURITY_PREFIXES):
            if tier != 'FULL':
                tier = 'SECURITY'
            reasons.append('SAFETY_OR_NATIVE_AUTHORITY_BOUNDARY')
        else:
            tier = 'FULL'
            reasons.append('UNMAPPED_IMPACT_STRICT_FULL')
    if tier != 'FAST':
        families = set(ALL_FAMILIES)
    return tier, families, sorted(set(reasons)) or ['KNOWN_READ_ONLY_CANDIDATE_PATHS']


def make_plan(paths, *, event='pull_request', mode='auto', legacy_311=False):
    if event == 'pull_request' and mode not in ('', 'auto'):
        raise ValueError('PR_CANNOT_USE_MANUAL_COMPARISON_OR_DOWNGRADE')
    actual = sorted(set(paths))
    comparison = mode.startswith('compare-')
    effective = actual
    if comparison:
        if event != 'workflow_dispatch':
            raise ValueError('COMPARISON_REQUIRES_MANUAL_DISPATCH')
        if mode == 'compare-readonly':
            effective = ['vrae/reporting/s2_candidate.py']
        elif mode in ('compare-security', 'compare-baseline'):
            effective = ['vrae/evidence/pack.py']
        else:
            raise ValueError('UNKNOWN_COMPARISON')
    tier, families, reasons = classify(effective)
    migration = any(p.startswith(('.github/', 'ci/')) or p.startswith('requirements')
                    or p in ('pyproject.toml', '.python-version') for p in actual)
    legacy = bool(legacy_311 or event == 'schedule' or mode in ('compatibility', 'compare-baseline')
                  or event == 'pull_request' and migration)
    if event == 'schedule' or mode in ('full', 'compatibility'):
        tier, families = 'FULL', set(ALL_FAMILIES)
        reasons.append('EXPLICIT_FULL_OR_PERIODIC_COMPATIBILITY')
    elif mode == 'security':
        tier, families = 'SECURITY', set(ALL_FAMILIES)
        reasons.append('EXPLICIT_SECURITY')
    elif mode == 'compare-baseline':
        tier, families = 'FULL', set(OLD_COMMON_FAMILIES)
        reasons.append('OLD_COMMON_PR_SELECTION_AND_BOTH_PYTHONS_REPLAY')
    elif mode not in ('', 'auto', 'compare-readonly', 'compare-security'):
        raise ValueError('UNKNOWN_MODE')
    if comparison and mode != 'compare-baseline':
        legacy = bool(legacy_311)
    return {'schema_version': 'ci-tier-1.0.0', 'tier': tier, 'event': event, 'mode': mode,
        'actual_paths': actual, 'effective_paths': effective, 'reasons': sorted(set(reasons)),
        'families': sorted(families), 'legacy_311': legacy,
        'core_tests': SECURITY_SMOKE if tier == 'FAST' else ['tests'],
        'isolated_http': tier != 'FAST', 'isolated_browser': tier != 'FAST',
        'comparison_only': comparison, 'current_code_unchanged': True,
        'business_full_pass_claim': False,
        'not_executed_families': sorted(set(ALL_FAMILIES) - families),
        'target_status': 'PYTHON313_CANDIDATE_NOT_PRODUCTION_LOCKED',
        'legacy_isolation_image_exception': 'ORIGINAL_PINNED_HTTP_BROWSER_LABS_REMAIN_311'}


def changed_paths(base, head):
    if not all(type(ref) is str and re.fullmatch(r'[0-9a-f]{40}', ref) for ref in (base, head)):
        raise ValueError('EXPECTED_IMMUTABLE_REFS')
    # --no-renames includes both deleted old and added new paths, preventing a
    # security file renamed into a read-only directory from escaping selection.
    raw = subprocess.check_output(['git', 'diff', '--no-renames', '--name-only', '-z', base, head, '--'], cwd=ROOT)
    return [p.decode('utf-8', errors='strict') for p in raw.split(b'\0') if p]


def event_plan():
    event = os.environ.get('GITHUB_EVENT_NAME', 'workflow_dispatch')
    data = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
    inputs = data.get('inputs') or {}
    paths = []
    if event == 'pull_request':
        pr = data['pull_request']
        try:
            paths = changed_paths(pr['base']['sha'], pr['head']['sha'])
        except (ValueError, subprocess.CalledProcessError, UnicodeError):
            paths = ['__DIFF_UNAVAILABLE_STRICT_FULL__']
    mode = 'auto' if event == 'pull_request' else inputs.get('mode', 'full')
    legacy = inputs.get('legacy_311', False) in (True, 'true')
    return make_plan(paths, event=event, mode=mode, legacy_311=legacy)


def verify_results(plan, results):
    expected = make_plan(plan['actual_paths'], event=plan['event'], mode=plan['mode'], legacy_311=plan['legacy_311'])
    if plan != expected:
        raise ValueError('PLAN_RECOMPUTATION_MISMATCH')
    required = {'plan', 'contracts-domain', *plan['families']}
    if plan['isolated_http']:
        required.add('isolated-http')
    if plan['isolated_browser']:
        required.add('isolated-browser')
    if any(results.get(name) != 'success' for name in required):
        raise ValueError('REQUIRED_SELECTED_JOB_NOT_SUCCESS')
    if any(results.get(name, 'skipped') != 'skipped' for name in plan['not_executed_families']):
        raise ValueError('UNPLANNED_SUITE_EXECUTED')
    return {'selected_jobs': sorted(required), 'not_executed_families': plan['not_executed_families'],
            'scope': plan['tier'], 'business_full_pass_claim': False}


def load_yaml(raw):
    import yaml
    class Loader(yaml.SafeLoader):
        pass
    Loader.yaml_implicit_resolvers = {k: [(tag, rx) for tag, rx in values
        if tag != 'tag:yaml.org,2002:bool'] for k, values in Loader.yaml_implicit_resolvers.items()}
    return yaml.load(raw, Loader=Loader)


def verify_workflow_parity():
    for row in inventory()['workflows']:
        old = load_yaml(subprocess.check_output(['git', 'show', BASE + ':' + row['path']], cwd=ROOT))
        current = load_yaml((ROOT / row['path']).read_text(encoding='utf-8'))
        if 'pull_request' in current['on'] or not {'workflow_call', 'workflow_dispatch'} <= set(current['on']):
            raise ValueError('CALLEE_TRIGGER_OR_MANUAL_ENTRY_CHANGED')
        if set(old['jobs']) != set(current['jobs']):
            raise ValueError('ORIGINAL_CALLEE_JOB_IDENTITIES_CHANGED')
        for name, job in old['jobs'].items():
            if current['jobs'][name]['steps'] != job['steps']:
                raise ValueError('ORIGINAL_EXECUTABLE_STEPS_CHANGED')
            if current['jobs'][name].get('timeout-minutes') != job.get('timeout-minutes'):
                raise ValueError('ORIGINAL_TIMEOUT_CHANGED')
    path = '.github/workflows/ra0-ci.yml'
    old = load_yaml(subprocess.check_output(['git', 'show', BASE + ':' + path], cwd=ROOT))
    current = load_yaml((ROOT / path).read_text(encoding='utf-8'))
    for name in ('isolated-http', 'isolated-browser'):
        if old['jobs'][name]['steps'] != current['jobs'][name]['steps']:
            raise ValueError('ORIGINAL_KERNEL_LAB_CHANGED')
    workflows = list((ROOT / '.github/workflows').glob('*.yml'))
    if len(workflows) != len(inventory()['workflows']) + 1:
        raise ValueError('UNREVIEWED_WORKFLOW_INVENTORY')
    if sum('pull_request' in load_yaml(p.read_text(encoding='utf-8'))['on'] for p in workflows) != 1:
        raise ValueError('EXTRA_PR_WORKFLOW')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('plan', 'result', 'parity'))
    args = parser.parse_args()
    if args.command == 'parity':
        verify_workflow_parity()
        print('Original executable steps, job IDs and timeouts unchanged.')
        return
    plan = event_plan()
    if args.command == 'result':
        supplied = json.loads(os.environ['PLAN_JSON'])
        if supplied != plan:
            raise ValueError('CURRENT_EVENT_PLAN_CHANGED')
        needs = json.loads(os.environ['NEEDS_JSON'])
        proof = verify_results(plan, {key: value['result'] for key, value in needs.items()})
        print(json.dumps(proof))
    else:
        print(json.dumps(plan))
        if 'GITHUB_OUTPUT' in os.environ:
            output = {'plan': json.dumps(plan, separators=(',', ':')), 'tier': plan['tier'],
                      'legacy_311': json.dumps(plan['legacy_311']),
                      'contracts_matrix': json.dumps({'python-version': ['3.11', '3.13'] if plan['legacy_311'] else ['3.13']})}
            output.update({family: json.dumps(family in plan['families']) for family in ALL_FAMILIES})
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as handle:
                handle.write(''.join(key + '=' + value + '\n' for key, value in output.items()))
    if 'GITHUB_STEP_SUMMARY' in os.environ:
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            handle.write('CI scope: **' + plan['tier'] + '**. Unexecuted suites are NOT_RUN, not business PASS.\n\n')
            handle.write('```json\n' + json.dumps(plan, ensure_ascii=True, indent=2).replace('`', '\\u0060') + '\n```\n')


if __name__ == '__main__':
    main()
