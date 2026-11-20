"""Offline authority amplification regression; signed synthetic targets only."""
from datetime import datetime, UTC, timedelta

import pytest

from integration.authorized_targets import egress
from integration.authorized_targets.checks.test_source_authority import grant as grant
from integration.l2_launch.security.adapter import TaskPins, OfflinePermit, fingerprint
from tests.collection.test_security import fixture
from vrae.collection.discovery import inventory, select_next
from vrae.collection.policy import SourceAccess


@pytest.fixture
def scoped(grant):
    plan, doc, registry, sign = grant
    audit, policy = fixture('AuditRequest'), fixture('SourcePolicy')
    policy['authorization_reference'] = doc['reference']
    plan.update(origin='https://example.org', tenant_id=audit['tenant_id'],
                policy=policy, path_scope='PUBLIC_SAME_ORIGIN')
    doc.update(origin=plan['origin'], tenant_id=plan['tenant_id'], path_scope=plan['path_scope'])
    envelope = sign(doc)
    counts = {'pg': 0, 'current': 0}

    def current():
        counts['pg'] += 1
        counts['current'] += 1
        return {'source_authorization': envelope, 'plan_sha256': '1' * 64}

    def provider():
        counts['pg'] += 1
        return policy

    original = SourceAccess(audit, provider, terms_reference=plan['terms_reference'])
    held = TaskPins(audit['tenant_id'], audit['request_id'], 'run-inventory-test',
                    policy['policy_id'], policy['policy_version'], fingerprint(policy))
    now = datetime.now(UTC)
    permit = OfflinePermit(plan['origin'], tuple(plan['exact_paths']),
                           now - timedelta(minutes=1), now + timedelta(minutes=5), True)
    access = egress.CurrentAccess(original, held, permit, current, plan)
    counts.update(pg=0, current=0)
    return access, counts, policy, registry


def markup(count):
    return ('<html><body>' + ''.join(f'<a href="/products/p{i}">Item</a>' for i in range(count))
            + '<a href="/login">Login</a><a href="/api/delete">Action</a>'
            + '<a href="https://other.example/">Other</a>'
            + '<a href="/?token=private">Query</a></body></html>').encode()


def test_hundred_links_use_two_current_authority_checks_and_preserve_scope(scoped, monkeypatch):
    access, counts, _, _ = scoped
    items, overflow = inventory(markup(154), access.start_url, access)
    assert len(items) == 154 and not overflow
    assert counts == {'pg': 7, 'current': 2}
    assert all(i['role'] == 'PRODUCT' for i in items)
    # Discovery is not a fetch permission cache. Every later check reloads PG.
    before = counts['current']
    access.check(items[0]['url'])
    assert counts['current'] == before + 1
    counts.update(pg=0, current=0)
    # Replay the former per-href path with identical signed inputs and markup.
    monkeypatch.setattr(access, 'inventory_scope', lambda: SourceAccess.inventory_scope(access))
    old_items, old_overflow = inventory(markup(154), access.start_url, access)
    assert (old_items, old_overflow) == (items, overflow)
    assert counts == {'pg': 470, 'current': 158}


@pytest.mark.parametrize('change', ['policy', 'signing_key', 'expiry', 'envelope'])
def test_mid_batch_revocation_or_change_cannot_return_inventory(scoped, change):
    access, _, policy, registry = scoped
    with pytest.raises(Exception):
        with access.inventory_scope() as local:
            assert local.check('https://example.org/products/item')
            if change == 'policy':
                policy['revoked_at'] = datetime.now(UTC).isoformat()
            elif change == 'signing_key':
                registry['keys']['admin']['revoked'] = True
            elif change == 'expiry':
                access.now = lambda: datetime.now(UTC) + timedelta(days=1)
            else:
                access.envelope = {'tampered': True}


def test_exact_path_grant_stays_exact(scoped):
    access, _, _, _ = scoped
    # The signed public grant cannot be relabeled as an exact grant.
    access.plan.pop('path_scope')
    with pytest.raises(Exception):
        access.check('https://example.org/products/item')


def test_existing_selection_covers_distinct_roles_before_repeat_catalogs():
    items = [{'url': 'https://example.org' + path, 'role': role}
             for path, role in [('/', 'HOME'), ('/catalog', 'CATALOG'),
                ('/products', 'CATALOG'), ('/products/item', 'PRODUCT'), ('/contact', 'CONTACT')]]
    attempted, covered, order = set(), set(), []
    for _ in range(4):
        item = select_next(items, attempted, covered)
        order.append(item['role'])
        attempted.add(item['url'])
        covered.add(item['role'])
    assert order == ['HOME', 'CATALOG', 'PRODUCT', 'CONTACT']
