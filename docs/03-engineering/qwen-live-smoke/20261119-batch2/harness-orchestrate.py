"""Original owned internal-network runner; inject only the paused C1 test hook."""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
root=Path(__file__).parent
original=subprocess.run
def run(argv,*args,**kwargs):
    items=list(argv)
    if items[:2]==['docker','create'] and items[-1]=='integration.authorized_targets.lab':
        runtime=items[items.index('--name')+1]
        (root/'runtime.json').write_text(json.dumps({'runtime':runtime}))
        items[2:2]=['--mount','type=bind,src='+str(root)+',dst=/live,readonly']
        items[-3:]=['python','/live/start.py']
    return original(items,*args,**kwargs)
subprocess.run=run
from infra.authorized_targets import runner
sys.argv=['runner','--label','c1-live-batch2-pg-v3','--delivery-bridge','--image','vrae-g1:313']
runner.main()
