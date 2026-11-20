"""Exact original rule projection; no external network or model authority."""
from copy import deepcopy
import socket

import pytest

from integration.authorized_targets.automatic_result import deterministic_diagnosis, TASKS
from integration.s3_offline.fixture import context
from vrae.industry.l2_v1 import diagnose
from vrae.industry.l2_v1.diagnose import SOURCE_VERSIONS
from vrae.rules.patch_execution import execute


@pytest.mark.parametrize('version', ['l2-industrial-1.0.0', 'l2-industrial-1.0.1', 'l2-industrial-1.0.2'])
def test_all_five_tasks_preserve_exact_rule_rows_and_committed_version(version, monkeypatch):
    # The synthetic fixture's event loop uses a local socketpair. Block all
    # sockets after fixture construction to test the actual projection boundary.
    c = context()
    original = diagnose(c.pack, expected_pack_ref=c.pack.ref,
        expected_industry_ref=c.completion.task.industry_ref, diagnostic_version=version)
    def denied(*args, **kwargs):
        pytest.fail('deterministic result attempted network access')
    monkeypatch.setattr(socket, 'socket', denied)
    monkeypatch.setattr(socket, 'getaddrinfo', denied)
    output = deterministic_diagnosis(c.pack, original)
    assert {k: output[k] for k in original} == original
    assert [t['task'] for t in output['buyer_tasks']] == list(TASKS)
    execution = execute(c.pack, expected_pack_ref=c.pack.ref,
                        evaluator_version=SOURCE_VERSIONS[version][0])
    for group in output['buyer_tasks']:
        assert group['rules'] == [r for r in execution['executions'] if r['buyer_task'] == group['task']]
    forged = deepcopy(original)
    forged['native_execution_ref'] = 'rx-' + '0' * 64
    with pytest.raises(ValueError, match='SAME_COMMITTED_RULE_EXECUTION_REQUIRED'):
        deterministic_diagnosis(c.pack, forged)
