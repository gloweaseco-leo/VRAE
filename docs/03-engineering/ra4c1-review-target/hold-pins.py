"""One-time extraction from Owner-accepted Git objects, not supplied requests."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from vrae.reviewing.canonical import canonical, sha, SOURCE_LIMIT

BASE='9d138ba57e0b442b9dace1a2247d7aaa46ca38ac'


def accepted(path):
    return json.loads(subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT))


records=accepted('docs/03-engineering/ra3d-d1d2-offline/runs/190c17d3651e5de9070df0709b2177a6ea3c345b/py11/scenarios.json')
other=accepted('docs/03-engineering/ra3d-d1d2-offline/runs/190c17d3651e5de9070df0709b2177a6ea3c345b/py13/scenarios.json')
result={'accepted_main':BASE,'authority':'TEST_ONLY_ACCEPTED_SYNTHETIC_SOURCE','cases':{}}
for case in ('404','200'):
    fixture=accepted('tests/reviewing/fixtures/'+case+'.json')
    original=next(p for p in records['paths'] if p['case']==case)
    alternate=next(p for p in other['paths'] if p['case']==case)
    assert original['target']==alternate['target'] and original['target_digest']==alternate['target_digest']
    held=fixture['held']
    held['expected_source_sha256']=sha(canonical(fixture['source'],limit=SOURCE_LIMIT))
    policy={'kind':'TEST_ONLY_POLICY_SNAPSHOT','scope':held['pins']['expected_scope'],
            'allowed_purpose':'OFFLINE_REVIEW_SIMULATION','current_authorization':'NOT_IMPLEMENTED'}
    assert sha(canonical(policy))==original['target']['policy_snapshot_sha256']
    result['cases'][case]={'held':held,'policy':policy,'artifact_ref':original['target']['artifact_ref'],
        'expected_target':original['target'],'expected_target_digest':original['target_digest']}
path=ROOT/'apps/operator_console/review-target-pins.json'
assert not path.exists(),'Never repin existing holds'
path.write_bytes(json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8')+b'\n')
print({c:r['expected_target_digest'] for c,r in result['cases'].items()})
