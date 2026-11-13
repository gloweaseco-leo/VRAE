"""Actual owned PG process restart while a report response is being rendered."""
import json
import os
import time

from apps.operator_console.interface import ConsoleInterface
from apps.operator_console.pg_read import make_pg_fixture
from apps.operator_console.views import review_url
from integration.ra4c3 import lab


def test_real_restart_mid_render_denies_original_response_then_recovers(monkeypatch):
    state=lab.bounded(os.environ['RA4C3_STATE'])
    profile=lab.bounded(os.environ['RA4C3_PROFILE'])
    s=json.loads(state.read_text())
    assert json.loads(lab.docker('inspect','--format','{{json .Config.Labels}}',s['container']))[lab.LABEL]=='TEST_ONLY'
    service,context=make_pg_fixture(profile,test_only=True,synthetic_fixtures=True)
    native=service.native.load_original
    task=service.repository.metadata.task('task-404')
    restarted=[]

    def during(*args):
        dossier=native(*args)
        result=lab.docker('restart',s['container'])
        restarted.append(result)
        return dossier

    monkeypatch.setattr(service.native,'load_original',during)
    r=ConsoleInterface(service).dispatch(context,'GET',review_url('/',task))
    assert r.status == 503 and b'<blockquote>' not in r.body
    assert restarted == [s['container']]
    port=lab.docker('port',s['container'],'5432/tcp')
    assert port.startswith('127.0.0.1:') and '\n' not in port
    s['port']=int(port.rsplit(':',1)[1])
    state.write_text(json.dumps(s),encoding='utf-8')
    p=json.loads(profile.read_text())
    p['port']=s['port']
    profile.write_text(json.dumps(p),encoding='utf-8')
    original,_=lab.wire(state)
    for i in range(60):
        try:
            with original.connect('ra4a_test_a_app',dbname=p['dbname']) as c:
                assert c.execute('SELECT session_user').fetchone()[0]=='ra4a_test_a_app'
            break
        except Exception:
            if i==59:
                raise
            time.sleep(.25)
    recovered,recovered_context=make_pg_fixture(profile,test_only=True,synthetic_fixtures=True)
    assert ConsoleInterface(recovered).dispatch(recovered_context,'GET',review_url('/',task)).status==200
