"""Trusted CONTROLLED fixture, using accepted C1 saved sources and original ledger."""
from dataclasses import replace
import hashlib
import json

from tests.s2_contract.batch2_fixtures import fixture as saved_sources
from integration.l2.support import create, people
from apps.operator_console.l2_http import DeepConsole
from vrae.industry.l2_v1 import load, diagnose
from vrae.industry.l2_v1.pack import load_s2
from vrae.l2.ledger import Ledger
from vrae.l2.native import NativeTask, NativeSource
from vrae.rules.s2 import IndustryPins
from .workbench import SourceBinding, install


def source_binding(profile_id='industrial'):
    pack = saved_sources()
    scope = {'tenant_id': 'tenant-example', 'run_id': 'run-synthetic',
             'policy_id': 'pol-001', 'policy_version': 1}
    industry = load(tenant_id=scope['tenant_id'])
    data = diagnose(pack, expected_pack_ref=pack.ref, expected_industry_ref=industry['industry_ref'])
    bundle = hashlib.sha256(json.dumps(pack.document, sort_keys=True).encode()).hexdigest()
    task = NativeTask(scope['tenant_id'], 'controlled-source-reading-not-app202', scope['run_id'],
                      'controlled-component-not-worker', 'controlled-component', 'controlled-source',
                      pack.ref, industry['industry_ref'], data['diagnosis_ref'], bundle,
                      'OFFLINE_SYNTHETIC', '2026-11-18T00:00:00+00:00')
    source = NativeSource(pack, data, held=task)
    current = load_s2(tenant_id=scope['tenant_id'], profile_id=profile_id)
    pins = IndustryPins(current['industry_ref'], scope['tenant_id'], profile_id=profile_id)
    binding = SourceBinding(source, pack, trusted_scope=scope, industry_pins=pins)
    anchor = next(snapshot['snapshot_ref'] for snapshot in pack.document['snapshots']
                  if snapshot['url']=='https://example.org/products/p40')
    binding.enable_buyer_cards(model='P40', snapshot_ref=anchor)
    return binding


def application(folder, *, clock=None):
    issuer, directory, _, app = create(folder, **({'clock': clock} if clock else {}))
    binding = source_binding()
    rid = binding.source.read().document['meta']['report_id']
    directory.people = {person.actor_id: replace(person, report_ids=(rid,)) for person in people()}
    ledger = Ledger(folder / 'source-reading.sqlite', binding.source, directory)
    app.deep = DeepConsole(directory, {rid: ledger})
    install(app, binding)
    app.origin = 'http://127.0.0.1:9876'  # unit transport; real server assigns its own loopback origin
    return issuer, directory, ledger, app, binding, rid
