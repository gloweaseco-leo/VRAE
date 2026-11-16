"""Controlled launcher for the existing B5B server with L2 mounted.

Receives public JWKS + held sources only. Fixture private signer stays in parent.
This is not a production server or a second workbench implementation.
"""
import argparse
import json
from pathlib import Path

from vrae.identity.boundary import TrustAnchor
from vrae.b6_p0.reader import PrivateHandoffReader
from apps.operator_console.b5a_http import Application as Base, server
from apps.operator_console.b5a_sessions import SessionStore
from apps.operator_console.b5p0_http import RehearsalApplication
from apps.operator_console.b5p0_journal import Journal
from apps.operator_console.b5b_http import Application
from apps.operator_console.l2_profile import load


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',required=True)
    parser.add_argument('--ready',required=True)
    parser.add_argument('--native-component',action='store_true')
    args=parser.parse_args()
    profile=Path(args.profile).resolve()
    root=Path(__file__).resolve().parent/'.runtime'
    if not profile.is_relative_to(root.resolve()) or not Path(args.ready).resolve().is_relative_to(root.resolve()):
        raise ValueError('L2_CONTROLLED_OWNED_FILES_REQUIRED')
    if args.native_component:
        from .native_component import source
        from vrae.l2.identity import Directory, Person
        from vrae.l2.ledger import Ledger
        from apps.operator_console.l2_http import DeepConsole
        profile_raw=profile.read_bytes()
        cfg=json.loads(profile_raw)
        settings=dict(cfg['directory'])
        settings['people']=[Person(**{**p,'report_ids':tuple(p['report_ids'])}) for p in settings['people']]
        directory=Directory(**settings)
        native=source()
        rid=native.read().version['report_id']
        def fresh():
            if profile.read_bytes()!=profile_raw:
                raise ValueError('L2_PROFILE_CHANGED_REAUTH_REQUIRED')
        deep=DeepConsole(directory,{rid:Ledger(cfg['ledger'],native,directory)},fresh)
    else:
        deep=load(profile)
    directory=deep.directory
    if directory.mode!='CONTROLLED':
        raise ValueError('L2_DEMO_CANNOT_ASSERT_FORMAL_HUMAN_REVIEW')
    anchor=TrustAnchor(directory.issuer,directory.audience,json.dumps(directory.jwks).encode(),directory.expires)
    legacy=SessionStore(anchor=anchor,bindings={},readers={})
    base=Base(legacy,{})
    rehearsal=RehearsalApplication(base,{},Journal(profile.parent/'legacy-empty.sqlite'),key_secret=b'controlled-unused-legacy-key-00001')
    app=Application(rehearsal,PrivateHandoffReader(legacy,{}),deep=deep)
    http=server(app)
    ready={'origin':app.origin,'entry':app.origin+'/b5a/l2/','mode':'L2_CONTROLLED_OFFLINE_SAME_B5B_SSR',
        'composition':'apps.operator_console.b5b_http.Application','private_signer_in_ssr':False,
        'external_customer_access':False,'database':'PRIVATE_SQLITE_OFFLINE_REVIEW_NOT_M1_PG'}
    if args.native_component:
        ready['mode']='L2_NATIVE_C1_C2_CONTROLLED_COMPONENT_NOT_APP202_E2E'
    Path(args.ready).write_text(json.dumps(ready),encoding='utf-8')
    print(json.dumps({'ready':True}),flush=True)
    try:
        http.serve_forever()
    finally:
        http.server_close()


if __name__=='__main__':
    main()
