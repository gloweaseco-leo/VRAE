"""One Owner-bounded diagnostic, with a RED baseline and explicit BLOCKED negatives."""
from types import SimpleNamespace

import pytest

from .cases import run, database_name, test_partial_restore_never_publishes_success, test_mismatched_independent_source_target_fails_closed
from .lab import RecoveryDenied, encode
from .observation import snapshot, diff
from .restore import Restore

# Imported fixtures and the two corrected new negative tests are deliberately
# executed in this single process/pair, never the original 18-case full matrix.
assert run and test_partial_restore_never_publishes_success and test_mismatched_independent_source_target_fails_closed


@pytest.fixture(scope='session', autouse=True)
def control(run):
    assert run.source_stability['different_objects'] == 0, 'SOURCE_MUTATED_DURING_BACKUP'

    def observe(environment, name, partial):
        label = ('partial-' if partial else 'full-') + name
        actual = snapshot(environment, name, run.private, run.output, label)
        comparison = diff(run.source_observation, actual, run.output, label)
        run.record(label + '-capture-boundary', {'after_real_pg_restore': True,
            'before_original_manifest_gate': True, 'different_objects': comparison['different_objects']})

    run.restorer = Restore(run.destination, run.private, run.output, run.expected, run.fixture['graphs'], observer=observe)
    name = database_name()
    result = SimpleNamespace(database=name, error=None, code=None)
    try:
        run.restorer.perform(run.archive, run.sha, name)
    except RecoveryDenied as exc:
        result.error = exc
        result.code = str(exc)
    run.diagnostic_control = result
    run.record('baseline-control', {'database': name, 'gate_code': result.code,
        'valid_full_manifest_gate': result.error is None, 'status': 'RED' if result.error else 'OBSERVED_CONTROL_PASS_NOT_ACCEPTANCE'})
    return result


def test_unmodified_full_restore_control_must_remain_red_if_gate_fails(control):
    assert control.error is None, control.code


def test_separate_genuine_manifest_mismatch_denial(run, control):
    if control.code != 'RESTORED_MANIFEST_MISMATCH':
        pytest.skip('BLOCKED: no actual manifest-mismatch observation; no invented negative')
    import json
    actual = json.loads((run.output / (control.database + '-actual-original-manifest.json')).read_text())
    assert actual['root_sha256'] != run.expected['root_sha256']
    stages = [r['stage'] for r in run.restorer.stages if r['database'] == control.database]
    assert stages.index('pg_restore_completed') < stages.index('actual_diagnostic_snapshot_saved_before_gate') < stages.index('original_manifest_captured') < stages.index('gate_denied')
    assert 'full_manifest_gate_passed' not in stages
    assert not (run.output / (control.database + '-ready.json')).exists()
    run.output.joinpath('genuine-manifest-negative.json').write_bytes(encode({'status': 'ACTUAL_GATE_DENIAL_OBSERVED_BASELINE_STILL_RED',
        'source_root': run.expected['root_sha256'], 'actual_root': actual['root_sha256'], 'gate_code': control.code}))
