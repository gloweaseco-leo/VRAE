"""No migration/seed after an actual PG16 restart; native durable receipts."""
import json
from pathlib import Path
import pytest
from integration.ra4a import support
from integration.ra4b_p2.m1.native_cases import reader
from apps.operator_console.b5b_m2_report import ReportView, a4


@pytest.fixture(scope='module')
def restored():
    folder = Path('/tmp/m2-recovered')
    folder.mkdir(mode=0o700)
    support.STATE = folder / 'state.json'
    support.STATE.write_bytes(Path('/run/m1-state.json').read_bytes())
    support.STATE.chmod(0o600)
    return json.loads(Path('/run/m2-before.json').read_bytes())


@pytest.mark.parametrize('case', ['404', '200'])
def test_actual_pg_restart_preserves_report_and_all_internal_receipts(restored, case):
    item = restored[case]
    held = {'runtime': {'held': {}}}
    port, bearer, nonce = reader(held, item['result'])
    view = ReportView(port.read(bearer, 'tenant-test', item['result']['job_id'], nonce=nonce))
    assert view.pins['report_sha256'] == item['report_sha256']
    with support.connect('p2b1_test_a_reviewer') as c:
        history = c.execute('SELECT b5b_m2.list_receipts(%s,%s)',
            ('tenant-test', item['result']['job_id'])).fetchone()[0]
        assert {r['command_id'] for r in history} >= {r['command_id'] for r in item['records']}
        for record in item['records']:
            receipt = c.execute('SELECT b5b_m2.read_receipt(%s,%s,%s)',
                ('tenant-test', item['result']['job_id'], record['command_id'])).fetchone()[0]
            assert receipt == record['receipt']
            assert '合成样本' in a4(view, receipt=receipt)
