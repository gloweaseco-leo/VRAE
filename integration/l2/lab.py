"""Real same-SSR/SQLite/Chrome controlled acceptance; signer outside SSR.

Use a unique label. --interactive keeps a dedicated controlled browser open for
Owner to operate; it never shares with a real customer or starts another app.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
import subprocess
import sys
import time

from .support import ROOT, PIN, Issuer, people


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('--interactive',action='store_true')
    parser.add_argument('--native-component',action='store_true')
    args=parser.parse_args()
    if not args.label.replace('-','').isalnum() or not 3<=len(args.label)<=(60 if args.native_component else 50):
        raise ValueError('L2_UNIQUE_LABEL_REQUIRED')
    out=ROOT/'integration/l2/.runtime'/args.label
    out.mkdir(parents=True,exist_ok=False)
    issuer=None
    child=node=None
    streams=[]
    restarts=[]
    native=None
    browser_config={}
    persons=people()
    if args.native_component:
        from .native_component import source
        native=source()
        d=native.read().document
        rid=d['meta']['report_id']
        persons=[replace(p,report_ids=(rid,)) for p in persons]
        browser_config={'native':True,'reportId':rid,'findingCount':len(d['findings']),
            'blueprintCount':len(d['blueprint']),
            'customId':next(b['id'] for b in d['blueprint'] if b['service_fit']=='CUSTOM_ASSESSMENT'),
            'reviseId':next(b['id'] for b in d['blueprint'] if '询价准备' in b['title'])}

    def start():
        nonlocal issuer,child
        issuer=Issuer()
        profile={'version':'L2_PRIVATE_PROFILE_1','directory':{
            'issuer':issuer.issuer,'audience':issuer.audience,'jwks':issuer.jwks,
            'people':[asdict(p) for p in persons],'expires':int(time.time())+3600,'mode':'CONTROLLED'},
            'sources':[{'root':str(ROOT/'fixtures/l2/pump-maker-v1'),'bundle_sha256':PIN}],
            'ledger':str(out/'l2.sqlite')}
        if args.native_component:
            profile['sources']=[]  # native fixture is constructed only on the trusted test server
        profile_file=out/'private-profile.json'
        profile_file.write_text(json.dumps(profile),encoding='utf-8')
        profile_file.chmod(0o600)
        ready=out/('private-ready-'+str(len(restarts))+'.json')
        stderr=(out/('private-server-'+str(len(restarts))+'.stderr.log')).open('wb')
        streams.append(stderr)
        child=subprocess.Popen([sys.executable,'-B','-m','integration.l2.server','--profile',str(profile_file),
            '--ready',str(ready)]+(['--native-component'] if args.native_component else []),cwd=ROOT,stdout=subprocess.PIPE,stderr=stderr)
        deadline=time.monotonic()+(300 if args.native_component else 30)
        while not ready.exists():
            if child.poll() is not None or time.monotonic()>deadline:
                raise RuntimeError('L2_SAME_SSR_START_FAILED')
            time.sleep(.1)
        return json.loads(ready.read_bytes())

    def stop():
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=15)

    try:
        ready=start()
        errors=(out/'private-browser.stderr.log').open('wb')
        streams.append(errors)
        node=subprocess.Popen(['node','integration/l2/browser.mjs'],cwd=ROOT,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,text=True,encoding='utf-8',env=dict(os.environ))
        node.stdin.write(json.dumps({'type':'init','base':ready['entry'],'out':str(out),
            'interactive':args.interactive,**browser_config})+'\n')
        node.stdin.flush()
        done=None
        for line in node.stdout:
            msg=json.loads(line)
            if msg.get('kind')=='done':
                done=msg
                break
            if msg.get('kind')=='interactive-ready':
                print(json.dumps({'entry':ready['entry'],'mode':'CONTROLLED_FICTITIOUS_OWNER_ONLY',
                    'instruction':'Use the dedicated browser. Ctrl+C stops it. No formal human review or customer sharing.'}),flush=True)
                continue
            if msg['kind']=='sign':
                if msg['subject'] not in {p.subject for p in people()}:
                    raise ValueError('L2_CONTROLLED_SUBJECT_REQUIRED')
                result=issuer.token(msg['subject'],msg['nonce'])
            elif msg['kind']=='restart':
                stop()
                restarts.append({'actual_ssr_process_exit':child.poll() is not None,
                    'same_sqlite_file_preserved':(out/'l2.sqlite').is_file(),'new_issuer_key':True})
                ready=start()
                result={'base':ready['entry'],**restarts[-1]}
            else:
                raise ValueError('L2_UNKNOWN_FIXTURE_RPC')
            node.stdin.write(json.dumps({'id':msg['id'],'result':result})+'\n')
            node.stdin.flush()
        node.wait(timeout=15)
        if done is None or not done['pass'] or node.returncode!=0:
            raise RuntimeError('L2_REAL_BROWSER_RED')
        source_files=[
            'vrae/l2/report.py','vrae/l2/identity.py','vrae/l2/ledger.py',
            'apps/operator_console/l2_http.py','apps/operator_console/l2_views.py','apps/operator_console/l2.css']
        if args.native_component:
            source_files+=['vrae/l2/native.py','vrae/l2/native_business.py']
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files}
        (out/'run.json').write_text(json.dumps({'kind':'L2_REAL_SAME_SSR_CONTROLLED_BROWSER',
            'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'runtime':ready,'source_hashes':source_hashes,'source_bundle_sha256':native.expected if native else PIN,
            'restarts':restarts,'private_signer_outside_ssr':True,'formal_human_reviews_claimed':0,
            'actual_external_customers':0,'result':done},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'pass':True,'output':str(out.relative_to(ROOT)),'restarts':len(restarts)}),flush=True)
    finally:
        if node is not None and node.poll() is None:
            node.terminate()
            node.wait(timeout=15)
        stop()
        for stream in streams:
            stream.close()
        (out/'process-cleanup.json').write_text(json.dumps({'ssr_exited':child is None or child.poll() is not None,
            'browser_controller_exited':node is None or node.poll() is not None}),encoding='utf-8')
    if not args.native_component and not args.interactive:
        subprocess.run([sys.executable,'-B','-m','integration.l2.lab',args.label+'-native','--native-component'],
                       cwd=ROOT,check=True)


if __name__=='__main__':
    main()
