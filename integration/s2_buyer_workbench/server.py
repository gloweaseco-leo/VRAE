"""Controlled fixture composition on the original B5B server; public keys only."""
import json
from pathlib import Path
import sys

from apps.operator_console.b5a_http import Application as Base, server
from apps.operator_console.b5a_sessions import SessionStore
from apps.operator_console.b5b_http import Application
from apps.operator_console.b5p0_http import RehearsalApplication
from apps.operator_console.b5p0_journal import Journal
from apps.operator_console.l2_http import DeepConsole
from vrae.b6_p0.reader import PrivateHandoffReader
from vrae.identity.boundary import TrustAnchor
from vrae.l2.identity import Directory, Person
from vrae.l2.ledger import Ledger
from .fixture import source_binding
from .workbench import install


def main():
    profile, ready = [Path(value).resolve() for value in sys.argv[1:]]
    runtime = Path(__file__).resolve().parent / '.runtime'
    if not profile.is_relative_to(runtime) or not ready.is_relative_to(runtime):
        raise ValueError('CONTROLLED_OWNED_PATH_REQUIRED')
    original = profile.read_bytes()
    config = json.loads(original)
    binding = source_binding()
    rid = binding.source.read().version['report_id']
    settings = config['directory']
    settings['people'] = [Person(**{**p, 'report_ids': tuple(p['report_ids'])}) for p in settings['people']]
    directory = Directory(**settings)
    if directory.mode != 'CONTROLLED' or any(p.report_ids != (rid,) for p in directory.people.values()):
        raise ValueError('CONTROLLED_MATCHING_REPORT_REQUIRED')

    def refresh():
        if profile.read_bytes() != original:
            raise ValueError('CONTROLLED_PROFILE_CHANGED')
    deep = DeepConsole(directory, {rid: Ledger(profile.parent/'ledger.sqlite', binding.source, directory)}, refresh)
    anchor = TrustAnchor(directory.issuer, directory.audience, json.dumps(directory.jwks).encode(), directory.expires)
    sessions = SessionStore(anchor=anchor, bindings={}, readers={})
    rehearsal = RehearsalApplication(Base(sessions, {}), {}, Journal(profile.parent/'legacy-empty.sqlite'),
                                      key_secret=b'controlled-unused-legacy-key-00001')
    app = Application(rehearsal, PrivateHandoffReader(sessions, {}), deep=deep)
    install(app, binding)
    http = server(app)
    ready.write_text(json.dumps({'origin': app.origin, 'reportId': rid,
                                'displayHash': binding.source.read().display_hash,
                                'projectionRef': binding.expected_ref,
                                'buyerCandidateRef': binding.expected_buyer_ref}), encoding='utf-8')
    try:
        http.serve_forever()
    finally:
        http.server_close()


if __name__ == '__main__':
    main()
