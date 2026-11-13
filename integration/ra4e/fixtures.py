"""Use accepted public fixture builders and ports; change only owned STATE wiring."""
from contextlib import contextmanager
import json
import uuid

from integration.ra4a import support, p2a_support, p2b1_support
from tests.identity.issuer import Issuer, ISSUER, AUDIENCE, NONCE, NOW
from vrae.identity.boundary import IdentityBoundary, TrustAnchor, Assignment
from vrae.persistence.postgres import TestOnlyPostgres
from vrae.persistence.private_bytes import locator
from vrae.persistence.review_cas import TestOnlyReviewCAS

from .lab import DB


@contextmanager
def wire(environment):
    modules = (support, p2a_support, p2b1_support)
    previous = [m.STATE for m in modules]
    for module in modules:
        module.STATE = environment.state
    try:
        yield
    finally:
        for module, value in zip(modules, previous, strict=True):
            module.STATE = value


def initialize(environment):
    with wire(environment):
        p2b1_support.migrate_p2b1()
        p2b1_support.seed_base()
    state = json.loads(environment.state.read_text())
    environment.runtime_passwords = state['runtime_passwords']


def build_source(environment):
    graphs = {case: p2a_support.graph(case) for case in ['404', '200']}
    with environment.connect('ra4a_test_a_app') as c:
        app = TestOnlyPostgres(c, mode='TEST_ONLY_PG16')
        first = app.admit('tenant-test', 'b7p0-completed-0001')
    with environment.connect('ra4a_test_a_worker') as c:
        worker = TestOnlyPostgres(c, mode='TEST_ONLY_PG16')
        done = worker.claim('tenant-test', seconds=30)
        worker.finish('tenant-test', done[0], done[2], done[3])
    with environment.connect('ra4a_test_a_app') as c:
        app = TestOnlyPostgres(c, mode='TEST_ONLY_PG16')
        app.admit('tenant-test', 'b7p0-inflight-0002')
    with environment.connect('ra4a_test_a_worker') as c:
        leased = TestOnlyPostgres(c, mode='TEST_ONLY_PG16').claim('tenant-test', seconds=1)
    with environment.connect('ra4a_test_b_app') as c:
        TestOnlyPostgres(c, mode='TEST_ONLY_PG16').admit('tenant-beta', 'b7p0-queued-beta-0003')
    name = 'vrae_p2b1_' + uuid.uuid4().hex[:12]
    environment.database(name, create=True, template=DB)
    commands, receipts = {}, {}
    with wire(environment):
        for case, graph in graphs.items():
            p2b1_support.register_graph(name, graph)
            commands[case] = p2b1_support.proposal(graph, key='b7p0-review-' + case + '-0001')
            with environment.connect('p2b1_test_a_reviewer', dbname=name) as c:
                receipts[case] = TestOnlyReviewCAS(c, mode='TEST_ONLY_P2B1_REVIEW_CAS').submit(
                    locator(graph), commands[case], provenance=graph).payload
    return {'dbname': name, 'graphs': graphs, 'commands': commands, 'receipts': receipts,
            'admitted': first, 'expired_lease': leased}


def identity(environment, dbname, graph, *, issuer=None):
    issuer = issuer or Issuer()
    assignment = Assignment(ISSUER, 'synthetic-reviewer-1', 'p2b1_test_a_reviewer', locator(graph), NOW + 90)
    boundary = IdentityBoundary(anchor=TrustAnchor(ISSUER, AUDIENCE, issuer.jwks(), NOW + 90),
        assignments=[assignment], connect=lambda role: environment.connect(role, dbname=dbname), clock=lambda: NOW)
    token = issuer.token()
    result = boundary.check(token, locator(graph), nonce=NONCE)
    assert result.authority == 'TEST_ONLY_IDENTITY_OBSERVATION'
    assert result.native_decision is result.native_approval is result.share_grant is None
    return issuer, token, boundary


def all_private_credentials(environments):
    values = []
    for environment in environments:
        values.extend([environment.admin_password, *environment.runtime_passwords.values()])
    return values
