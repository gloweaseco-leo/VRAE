"""Original PG/authority/Session on pure controlled input; native Windows egress.

PG transport is an owned Docker exec control pipe to original readers, never
fabricated snapshots. Actual model I/O uses unmodified original NativeTransport.
No key goes to Docker; no original server/Guard/Provider is rewritten.
"""
import argparse
from contextlib import nullcontext
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from vrae.intelligence.common import encode
from integration.qwen_provider.postcommit import InputPins, replay_input
from integration.qwen_provider.committed import Adapter
from integration.qwen_provider import committed
from integration.authorized_targets import current_authority, postcommit
from vrae.industry.l2_v1.pack import load_s2
from vrae.rules.s2 import IndustryPins,evaluate_s2
from vrae.reporting.s2_candidate import BuyerCandidatePins,ObservationPin
from vrae.l2.native import NativeTask
from vrae.intelligence.qwen import Config,Permission,Price,QwenProvider,Quota
from vrae.intelligence.qwen.provider import MODEL_SOURCE,strict_json
from infra.qwen_provider.transport import NativeTransport

ROOT=Path(__file__).parent/'live-batch2'
PG=Path(__file__).parent/'pg-live'
LEDGER=Path(__file__).parent/'live-smoke/quota.sqlite'
runtime=json.loads((PG/'runtime.json').read_bytes())['runtime']
info=json.loads(subprocess.check_output(['docker','inspect',runtime]))[0]
assert info['State']['Running'] and info['Config']['Labels']['vrae.authorized_targets']==runtime.removesuffix('-runtime')

def rpc(action,**data):
    p=subprocess.run(['docker','exec','-i',runtime,'python','/live/remote.py'],input=encode({'action':action,**data}),
                     capture_output=True,timeout=30)
    if p.returncode:
        (ROOT/'pg-control-error-private.txt').write_bytes(p.stderr)
        raise RuntimeError('ORIGINAL_PG_CONTROL_PIPE_REFUSED')
    return json.loads(p.stdout)

# Reuse original authority methods while delegating its PG read to the ORIGINAL
# server-side CurrentCommittedAuthority inside the owned namespace. This is a
# private experiment's control transport, not a new production authority.
current_authority.CurrentCommittedAuthority._read=lambda self:rpc('snapshot')
committed.current_input=lambda binding,job:rpc('base')
class ReceiptConnection:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def transaction(self):return nullcontext()
    def execute(self,sql,args):
        assert sql=='SELECT target_v1.ai_record(%s,%s,%s,%s)'
        assert rpc('record',receipt=args[3].obj)=={'recorded':True}
postcommit.connect=lambda binding:ReceiptConnection()

identity=rpc('identity')
binding={'tenant_id':identity['tenant_id']}
job=identity['job_id']
authority=current_authority.CurrentCommittedAuthority(binding,job)
held=authority.check_current()
assert held['authority_profile']=='AUTHORIZED_TARGET_V2_COMMIT_V3'
d=held['artifact']
assert d['source_authority']['authorization']['document']['source_class']=='CONTROLLED_NON_CUSTOMER'
pack,source=replay_input(encode(d),pins=InputPins(NativeTask(**d['native_document']['native_context']),
    held['commit']['artifact_sha256'],d['version']['content_hash'],d['display_hash']))
scope={k:pack.document[k] for k in ('tenant_id','run_id','policy_id','policy_version')}
config=load_s2(tenant_id=scope['tenant_id'],profile_id='industrial')
industry=IndustryPins(config['industry_ref'],scope['tenant_id'],profile_id='industrial')
projection=evaluate_s2(pack,expected_pack_ref=pack.ref,trusted_scope=scope,
    projection_version='s2-projection-1.2.0',industry_pins=industry)
# One bounded actual observation from the pure synthetic TX10 fixture.
row=next(r for r in projection['industrial_projection']['rows']
         if r['model']=='TX10' and r['observation']['rule_id']=='INFO-02')
buyer=BuyerCandidatePins(**scope,pack_ref=pack.ref,projection_ref=projection['projection_ref'],
    projection_version='s2-projection-1.2.0',industry_pins=industry,subject_model='TX10',
    subject_snapshot_ref=next(s['snapshot_ref'] for s in pack.document['snapshots'] if s['url'].endswith('/products/item')),
    observations=(ObservationPin(row['observation']['observation_id'],row['observation']['rule_id'],
        row['observation']['rule_version'],row['source_version'],
        tuple(sorted(p['snapshot_ref'] for p in row['source_pages']))),))
adapter=Adapter(binding,job,projection=projection,buyer_pins=buyer,timeout_ms=120000)
parser=argparse.ArgumentParser()
parser.add_argument('--prepare-only',action='store_true')
args=parser.parse_args()
if args.prepare_only:
    receipt=postcommit.run(binding,job,adapter,operation_id='owner-7000206811-pg-preflight-nomodel')
    assert receipt['reason']=='PROVIDER_GO_NOT_GRANTED' and adapter._session is not None
    result={'prepared':True,'authority_profile':held['authority_profile'],'task':held['task'],
        'commit':held['commit'],'pack_ref':pack.ref,'report_content_hash':d['version']['content_hash'],
        'source_class':'CONTROLLED_NON_CUSTOMER','model_calls':0}
    (ROOT/'pg-prepared.json').write_bytes(encode(result))
    print(encode(result).decode())
    sys.exit(0)

assert not (ROOT/'pg-result.json').exists()
first=json.loads((ROOT/'probe-result.json').read_bytes())
assert first['first_success'] and first['http_status']==200 and first['reported_model']=='qwen4-max'
credentials=json.loads(sys.stdin.read())
key,workspace=credentials['key'],credentials['workspace_id']
grant=json.loads((ROOT/'grant.json').read_bytes())
expiry=datetime.fromisoformat(grant['expires_at'])
provider=QwenProvider(Config(workspace),Quota(LEDGER,batch=grant['batch']),
    permission=Permission('OWNER_ISSUE156_COMMENT7000206811_QWEN4_2_CNY6',expiry,2,6000000),
    price=Price('official-beijing-qwen4-20261119',MODEL_SOURCE,10000000,30000000,expiry),key=key)
provider.authorize(datetime.now().astimezone())
assert not provider.protocol_fake
adapter._provider=provider
observed={}
original=NativeTransport.post
async def observe(self,config,secret,body,timeout_ms):
    request=encode(body)
    assert key.encode() not in request
    with (ROOT/'pg-request.json').open('xb') as f:f.write(request)
    observed['request_sha256']=hashlib.sha256(request).hexdigest()
    status,raw=await original(self,config,secret,body,timeout_ms)
    assert key.encode() not in raw
    with (ROOT/'pg-response.bin').open('xb') as f:f.write(raw)
    observed.update(http_status=status,response_sha256=hashlib.sha256(raw).hexdigest(),response_bytes=len(raw))
    try:
        response=strict_json(raw)
        observed.update(reported_model=response.get('model'),reported_usage=response.get('usage'),
                        vendor_error_code=(response.get('error') or {}).get('code'))
    except Exception:observed['response_json_valid']=False
    return status,raw
NativeTransport.post=observe
try:
    receipt=postcommit.run(binding,job,adapter,operation_id='owner-7000206811-qwen4-pg-002')
    (ROOT/'pg-receipt.json').write_bytes(encode(receipt))
    after=authority.check_current()
    result={'code_head':subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
        'state':receipt['state'],'reason':receipt.get('reason'),'usage':receipt['usage'],
        'claims':len(receipt.get('claims',[])),'task':receipt['task'],
        'artifact_sha256':receipt['artifact_sha256'],'report_content_hash':receipt['report_content_hash'],
        'display_hash':receipt['display_hash'],'pack_ref':pack.ref,
        'authority_profile':held['authority_profile'],'pg_transport':'ORIGINAL_READERS_OVER_OWNED_DOCKER_CONTROL_PIPE',
        'model_transport':'ORIGINAL_NATIVE_TRANSPORT_WINDOWS_DPAPI_TERMINAL','protocol_fake':False,
        'same_current_source':encode(after)==encode(held),'grants_report_access':receipt['grants_report_access'],
        'report_unchanged':source.read().version['content_hash']==d['version']['content_hash'],
        'actual_invoice_cost':'UNKNOWN',**observed}
    assert key.encode() not in encode(result)
    with (ROOT/'pg-result.json').open('xb') as f:f.write(encode(result))
    print(encode(result).decode())
finally:
    NativeTransport.post=original
    rpc('done')
