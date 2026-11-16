"""Private operator-provisioned public keys/directory and held offline inputs."""
from pathlib import Path

from vrae.identity.boundary import document
from vrae.l2.identity import Directory, Person
from vrae.l2.ledger import Ledger
from vrae.l2.report import OfflineSource
from .l2_http import DeepConsole


def load(path):
    path=Path(path)
    raw=path.read_bytes()
    if not 1<=len(raw)<=131072:
        raise ValueError('L2_PROFILE_BOUND')
    cfg=document(raw)

    def refresh():
        if path.read_bytes()!=raw:
            raise ValueError('L2_PROFILE_CHANGED_REAUTH_REQUIRED')

    return provision(cfg,refresh=refresh)


def provision(cfg,*,refresh=lambda:None):
    """Trusted launcher input only; never a browser upload or self-issued role."""
    if set(cfg)!={'version','directory','sources','ledger'} or cfg['version']!='L2_PRIVATE_PROFILE_1':
        raise ValueError('L2_PROFILE_SHAPE')
    settings=dict(cfg['directory'])
    settings['people']=[Person(**{**p,'report_ids':tuple(p['report_ids'])}) for p in settings['people']]
    directory=Directory(**settings)
    ledgers={}
    for item in cfg['sources']:
        source=OfflineSource(item['root'],item['bundle_sha256'])
        rid=source.read().document['meta']['report_id']
        if rid in ledgers:
            raise ValueError('L2_PROFILE_DUPLICATE_REPORT')
        ledgers[rid]=Ledger(cfg['ledger'],source,directory)

    return DeepConsole(directory,ledgers,refresh)
