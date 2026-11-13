"""Out-of-HTTP admin test control, fixed actions against one owned C3 DB."""
import argparse
import json
import os

from integration.ra4c3 import lab


def mutate(action):
    profile=json.loads(lab.bounded(os.environ['RA4C3_PROFILE']).read_text())
    original,_=lab.wire(os.environ['RA4C3_STATE'])
    if action=='stop-db':
        s=json.loads(lab.bounded(os.environ['RA4C3_STATE']).read_text())
        assert json.loads(lab.docker('inspect','--format','{{json .Config.Labels}}',s['container']))[lab.LABEL]=='TEST_ONLY'
        lab.docker('stop',s['container'])
        print(json.dumps({'fixed_fixture_action':action,'owned_db_stopped':True}))
        return
    with original.connect(dbname=profile['dbname']) as c:
        if action in ('revoke','restore'):
            c.execute("UPDATE ra4a.policies SET status=%s WHERE tenant_id='tenant-test'",
                      ('REVOKED' if action=='revoke' else 'ALLOWED',))
        elif action in ('login-off','login-on'):
            c.execute('ALTER ROLE ra4a_test_a_app '+('NOLOGIN' if action=='login-off' else 'LOGIN'))
        else:
            raise ValueError('FIXED_SYNTHETIC_ACTION_REQUIRED')
    print(json.dumps({'fixed_fixture_action':action,'private_synthetic_only':True}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('revoke','restore','login-off','login-on','stop-db'))
    mutate(p.parse_args().action)
