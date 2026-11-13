"""Remove the successful diagnostic lab before final regression labs."""
import json
import socket
from integration.ra4c3 import lab

state=lab.OWN/'runtime/option-a-state.json'
profile=lab.OWN/'runtime/option-a-app-profile.json'
s=json.loads(state.read_text())
lab.stop(state,lab.OWN/'evidence/option-a-02/teardown')
with socket.socket() as probe:
    probe.settimeout(2)
    code=probe.connect_ex(('127.0.0.1',s['port']))
assert code != 0
profile.unlink()
(lab.OWN/'evidence/option-a-02/closed-port.json').write_bytes(json.dumps({
    'host':'127.0.0.1','port':s['port'],'connect_ex':code,'closed':True,
    'state_and_profile_removed':True}).encode()+b'\n')
