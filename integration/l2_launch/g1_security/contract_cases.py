"""Independent negative consumers of the frozen G0 functions. NOT HTTP tests."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

from contracts.l2_launch.contract import Refused, digest, simulate_report_read
from contracts.l2_launch.fixture_stub import FixtureJournal
from contracts.l2_launch.vf_b import (
    safe_error,
    safe_log_record,
    submission_document,
    validate_free_view,
)
from tests.l2_launch.fixtures import CALLER, NOW, PRINCIPAL, sign, verifier
from tests.l2_launch.vf_b_fixtures import (
    RETURN_TOKEN,
    facade_fixture,
    free_publication_fixture,
    return_fixture,
)
from vrae.domain.reviews import report_content_hash

SUBMIT_CASES = ('forged-service', 'wrong-version', 'invitation-revoked', 'invitation-expired',
                'invitation-tenant', 'different-consent-version', 'different-consent-text',
                'expired-policy', 'absent-policy', 'forged-signature', 'revoked-signing-key')
VIEW_CASES = ('lost-counter', 'changed-counter', 'changed-citation', 'four-priorities', 'historical-hash')
READ_CASES = ('bare-audit-ref', 'unpublished-report', 'expired-return', 'withdrawn-return', 'cross-tenant')


def submit_attack(path, kind):
    control = FixtureJournal(path/'valid-control.sqlite')
    try:
        adapter, submission, policy, _ = facade_fixture(control)
        assert adapter.submit(submission, CALLER, policy, verifier(), NOW)['status'] == 202
    finally:
        control.close()
    journal = FixtureJournal(path/'contract-only.sqlite')
    try:
        adapter, submission, policy, _ = facade_fixture(journal)
        caller, check, now = dict(CALLER), verifier(), NOW
        if kind == 'forged-service':
            caller['actor_id'] = 'forged-service'
        elif kind == 'wrong-version':
            submission['contract_version'] = 'unnegotiated-v999'
        elif kind.startswith('invitation-'):
            invitation = adapter.invitations['invitation-fixture']
            if kind == 'invitation-revoked':
                invitation['revoked'] = True
            elif kind == 'invitation-expired':
                invitation['expires_at'] = (NOW-timedelta(seconds=1)).isoformat()
            else:
                invitation['tenant_id'] = 'tenant-other'
        elif kind == 'different-consent-version':
            submission['diagnosis_consent']['consent_version'] = 'different-consent'
        elif kind == 'different-consent-text':
            submission['diagnosis_consent']['text_sha256'] = digest('different legal text')
        elif kind == 'expired-policy':
            policy['expires_at'] = (NOW-timedelta(seconds=1)).isoformat()
            adapter.invitations['invitation-fixture']['policy_sha256'] = digest(policy)
        elif kind == 'absent-policy':
            policy = None
        elif kind == 'forged-signature':
            submission['submission_proof']['signature'] = '00'*64
        elif kind == 'revoked-signing-key':
            check.keys['key-permission'] = replace(check.keys['key-permission'], revoked=True)
        if kind in ('different-consent-version', 'different-consent-text'):
            # Valid envelope signature cannot excuse a mismatch to approved consent.
            submission['submission_proof'] = sign('permission', 'permission', submission_document(submission))
        reply = adapter.submit(submission, caller, policy, check, now)
        assert reply['status'] == 403
        assert reply['body']['code'] == 'ACCESS_DENIED' and reply['headers']['Cache-Control'] == 'no-store'
        assert journal.db.execute('SELECT count(*) FROM items').fetchone()[0] == 0
        return {'case': kind, 'verdict': 'PASS', 'realm': 'FROZEN_G0_FUNCTION_NOT_HTTP', 'denial': 403}
    finally:
        journal.close()


def view_attack(kind):
    record = free_publication_fixture('aref-security-fixture', 'run-security-fixture')
    view, bundle = deepcopy(record['free_view']), record['bundle']
    validate_free_view(view, bundle)  # positive control: valid input is accepted
    facts = view['results']['UNDERSTAND']
    if kind == 'historical-hash':
        def current_read():
            return simulate_report_read(bundle, record['principal'], record['server_bearer'], verifier(), NOW,
                                        current_grant=record['current_grant'])
        current_read()  # Positive control with the independently held current grant.
        bundle['report']['content_hash'] = '0'*64
        try:
            current_read()
        except Refused as error:
            return {'case': kind, 'verdict': 'PASS', 'realm': 'FROZEN_G0_FUNCTION_NOT_HTTP', 'code': error.code}
        raise AssertionError('HISTORICAL_OR_FORGED_REPORT_HASH_ACCEPTED')
    if kind == 'lost-counter':
        facts[:] = [f for f in facts if f['kind'] != 'COUNTER_EVIDENCE']
    elif kind == 'changed-counter':
        next(f for f in facts if f['kind'] == 'COUNTER_EVIDENCE')['statement']['en'] = 'Suitability is proven.'
    elif kind == 'changed-citation':
        view['citations'][0]['excerpt'] = 'Source text was changed.'
    elif kind == 'four-priorities':
        eligible = ['projected-0']
        for index in range(3):
            original = {**deepcopy(bundle['findings'][0]), 'finding_id': 'finding-extra-'+str(index)}
            bundle['findings'].append(original)
            projected = {**deepcopy(facts[0]), 'fact_id': 'projected-extra-'+str(index),
                         'original_fact_ref': original['finding_id']}
            facts.append(projected)
            eligible.append(projected['fact_id'])
        bundle['report']['finding_ids'] = [f['finding_id'] for f in bundle['findings']]
        content_hash = report_content_hash(bundle['report'], bundle['findings'])
        for document in (bundle['report'], bundle['view'], bundle['decision'], bundle['grant']):
            document['content_hash'] = content_hash
        view['priority'] = eligible[:3]
        validate_free_view(view, bundle)  # Three otherwise valid ISSUE priorities pass.
        view['priority'] = eligible  # The fourth is the ONLY invalid condition.
    try:
        validate_free_view(view, bundle)
    except Refused as error:
        return {'case': kind, 'verdict': 'PASS', 'realm': 'FROZEN_G0_FUNCTION_NOT_HTTP', 'code': error.code}
    raise AssertionError('TAMPERED_PROJECTION_ACCEPTED')


def session_attack(path, kind):
    journal = FixtureJournal(path/'read-only-contract.sqlite')
    try:
        adapter, submission, policy, _ = facade_fixture(journal)
        check = verifier()
        accepted = adapter.submit(submission, CALLER, policy, check, NOW)
        assert accepted['status'] == 202  # fixture acceptance, NOT actual HTTP/PG acceptance
        ref = accepted['body']['audit_ref']
        grant = return_fixture(ref, policy)
        if kind == 'expired-return':
            grant['expires_at'] = (NOW+timedelta(seconds=1)).isoformat()
        adapter.install_return_fixture(grant, sign('owner', 'share', grant), check, NOW)
        exchanged = adapter.exchange(ref, PRINCIPAL['subject_ref'], RETURN_TOKEN, CALLER, policy, check, NOW)
        assert exchanged['status'] == 200
        cookie = exchanged['set_cookie']['value']
        for stage in ('FETCHING', 'EVIDENCE_READY', 'RULED', 'DRAFT_READY', 'REVIEW_REQUIRED'):
            journal.advance_fixture(CALLER['tenant_id'], submission['command']['request']['audit_id'], stage)
        record = free_publication_fixture(ref, accepted['body']['run_id'])
        adapter.publication_resolver = lambda audit: record
        assert adapter.read('report', ref, cookie, CALLER, policy, check, NOW)['status'] == 200
        caller, now = dict(CALLER), NOW
        if kind == 'bare-audit-ref':
            cookie = ref
        elif kind == 'expired-return':
            now = NOW+timedelta(seconds=2)  # Policy, invitation and signing keys remain valid.
        elif kind == 'withdrawn-return':
            adapter.revoke_return_fixture(ref, sign('owner', 'share', {'audit_ref': ref, 'action': 'REVOKE_RETURN'}), check, NOW)
        elif kind == 'cross-tenant':
            caller['tenant_id'] = 'tenant-other'
        elif kind == 'unpublished-report':
            adapter.publication_resolver = lambda audit: None
        reply = adapter.read('report', ref, cookie, caller, policy, check, now)
        assert reply['status'] == 403 and reply['body']['code'] == 'ACCESS_DENIED'
        return {'case': kind, 'verdict': 'PASS', 'realm': 'FROZEN_G0_FUNCTION_NOT_HTTP', 'denial': 403}
    finally:
        journal.close()


def idempotency_attack(path):
    journal = FixtureJournal(path/'idem-contract.sqlite')
    try:
        adapter, submission, policy, _ = facade_fixture(journal)
        check = verifier()
        assert adapter.submit(submission, CALLER, policy, check, NOW)['status'] == 202
        changed = deepcopy(submission)
        changed['language'] = 'en' if changed['language'] == 'zh' else 'zh'
        changed['submission_proof'] = sign('permission', 'permission', submission_document(changed))
        response = adapter.submit(changed, CALLER, policy, check, NOW)
        assert response['status'] == 409 and response['body']['code'] == 'CONFLICT'
        return {'case': 'same-key-different-intent', 'verdict': 'PASS', 'realm': 'FROZEN_G0_FUNCTION_NOT_HTTP', 'denial': 409}
    finally:
        journal.close()


def log_attack():
    assert safe_log_record('submit', 'ACCESS_DENIED') == {'operation': 'submit', 'code': 'ACCESS_DENIED'}
    sentinel = 'Bearer SYNTHETIC-DO-NOT-LOG https://legacy.example/?token=synthetic user@example.test'
    reply = safe_error(Refused(sentinel))
    assert sentinel not in str(reply) and reply['code'] == 'ACCESS_DENIED'
    for operation, code in [('submit', sentinel), (sentinel, 'ACCESS_DENIED')]:
        try:
            safe_log_record(operation, code)
        except Refused:
            continue
        raise AssertionError('SENSITIVE_LOG_LABEL_ACCEPTED')
    return {'case': 'log-field-injection', 'verdict': 'PASS', 'realm': 'FROZEN_G0_FUNCTION_NOT_HTTP', 'synthetic_sentinel_reflected': False}
