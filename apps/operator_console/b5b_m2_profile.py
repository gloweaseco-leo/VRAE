"""Private launcher provisioning of the generated lane on the EXISTING SSR.

Reviewer credentials, public issuer keys and a separate private HTTP API bearer
enter this process. No APP/Worker DB config, signing key, DSN, arbitrary URL,
fixture/report bytes or fallback.
The caller owns private-file permissions and issuer/challenge lifecycle.
"""

import json
from pathlib import Path
import psycopg

from vrae.identity.boundary import TrustAnchor
from vrae.application.ra4b_p2.m1.reader import SignedGeneratedReader, JobAssignment
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, TaskClient
from .b5b_m2_sessions import GeneratedSessions
from .b5b_m2_http import GeneratedConsole
from .b5b_m2_tasks import TaskWorkflow

ROLES = frozenset({'p2b1_test_a_reviewer', 'p2b1_test_a_peer', 'p2b1_test_b_reviewer'})


def provision(cfg):
    keys = {'version', 'anchor', 'assignments', 'reviewers', 'tasks'}
    if (type(cfg) is not dict or set(cfg) not in (keys, keys | {'task_endpoint', 'task_journal'}, keys | {'task_endpoint', 'task_journal', 'task_sources'})
            or cfg['version'] != 'M2_SYNTHETIC_REVIEWER_1'
            or type(cfg['reviewers']) is not dict or not 1 <= len(cfg['reviewers']) <= 3
            or set(cfg['reviewers']) - ROLES):
        raise ValueError('M2_REVIEWER_ONLY_PROFILE_REQUIRED')
    anchor = dict(cfg['anchor'])
    if set(anchor) != {'issuer', 'audience', 'jwks', 'expires'}:
        raise ValueError('M2_PUBLIC_TRUST_ANCHOR_REQUIRED')
    jwks = anchor['jwks']
    if (type(jwks) is not dict or set(jwks) != {'keys'} or type(jwks['keys']) is not list
            or any(set(k) != {'kty', 'crv', 'alg', 'use', 'kid', 'x'} for k in jwks['keys'])):
        raise ValueError('M2_PUBLIC_TRUST_ANCHOR_REQUIRED')
    anchor['jwks'] = json.dumps(jwks, separators=(',', ':')).encode()
    held = {}
    for role, value in cfg['reviewers'].items():
        if (type(value) is not dict or set(value) != {'password'}
                or type(value['password']) is not str or not 16 <= len(value['password']) <= 256):
            raise ValueError('M2_REVIEWER_ONLY_PROFILE_REQUIRED')
        held[role] = value['password']
    assignments = [JobAssignment(**a) for a in cfg['assignments']]
    if len(assignments) > 40 or any(a.db_role not in held for a in assignments):
        raise ValueError('M2_BOUNDED_ASSIGNMENTS_REQUIRED')

    def connect(role):
        if role not in held:
            raise ValueError('M2_REVIEWER_ONLY_PROFILE_REQUIRED')
        return psycopg.connect(host='127.0.0.1', port=5432, dbname='vrae_ra4a_p1',
            user=role, password=held[role], autocommit=True, connect_timeout=3,
            options='-c statement_timeout=2000 -c lock_timeout=2000')

    reader = SignedGeneratedReader(anchor=TrustAnchor(**anchor), assignments=assignments, connect=connect)
    workflow = None
    if 'task_endpoint' in cfg:
        endpoint = dict(cfg['task_endpoint'])
        if set(endpoint) != {'bearer', 'tenant_id', 'source_refs'} or type(endpoint['source_refs']) is not list:
            raise ValueError('M2_HTTP_ONLY_TASK_ENDPOINT_REQUIRED')
        endpoint['source_refs'] = frozenset(endpoint['source_refs'])
        workflow = TaskWorkflow(TaskClient(AppEndpoint(**endpoint)), cfg['task_journal'], sources=cfg.get('task_sources'))
    return GeneratedConsole(GeneratedSessions(reader), cfg['tasks'], workflow=workflow)


def load(path):
    raw = Path(path).read_bytes()
    if not 1 <= len(raw) <= 131072:
        raise ValueError('M2_PRIVATE_PROFILE_BOUND')

    def unique(items):
        d = {}
        for key, value in items:
            if key in d:
                raise ValueError('M2_DUPLICATE_PROFILE_KEY')
            d[key] = value
        return d

    console = provision(json.loads(raw, object_pairs_hook=unique))

    def fresh():
        if Path(path).read_bytes() != raw:
            raise ValueError('M2_PRIVATE_PROFILE_CHANGED')

    console.sessions.refresh = fresh
    return console
