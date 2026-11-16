"""Private durable L2 versions/decisions and controlled directed access.

V1 ReportVersion, ReviewDecision, ShareGrant and original domain gates are reused.
Full presentation hashes additionally bind journey, priority and blueprint text.
No writes to M1, B3, B6 or their protected tables; no external transport exists.
"""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from uuid import uuid4

from vrae.domain.access import require_access
from vrae.domain.contracts import validate_contract
from vrae.domain.reviews import approve_version, check_share
from .identity import Person
from .report import DeepReport, bounded, deny, encoded, sha


def at(value):
    return datetime.fromtimestamp(value,timezone.utc).isoformat()


class Ledger:
    def __init__(self, path, source, directory):
        self.path=Path(path)
        self.source,self.directory=source,directory
        if getattr(source,'controlled_only',False) and directory.mode!='CONTROLLED':
            deny('L2_NATIVE_CONTROLLED_CONTEXT_REQUIRED')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.is_symlink():
            deny('L2_LEDGER_PATH_DENIED')
        with self.connection() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS versions(
                  tenant TEXT NOT NULL,report TEXT NOT NULL,version INTEGER NOT NULL,
                  payload BLOB NOT NULL,display_hash TEXT NOT NULL,source_hash TEXT NOT NULL,
                  PRIMARY KEY(tenant,report,version));
                CREATE TABLE IF NOT EXISTS decisions(
                  seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,
                  tenant TEXT NOT NULL,report TEXT NOT NULL,version INTEGER NOT NULL,
                  receipt BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS grants(
                  id TEXT PRIMARY KEY,tenant TEXT NOT NULL,report TEXT NOT NULL,version INTEGER NOT NULL,
                  decision_id TEXT NOT NULL,recipient TEXT NOT NULL,scope TEXT NOT NULL,issued_by TEXT NOT NULL,
                  display_hash TEXT NOT NULL,grant_json BLOB NOT NULL);
            ''')
        self.path.chmod(0o600)
        initial=source.read()
        d=initial.document['meta']
        with self.transaction() as c:
            row=c.execute('SELECT source_hash FROM versions WHERE tenant=? AND report=? LIMIT 1',
                          (d['tenant_id'],d['report_id'])).fetchone()
            if row is not None and row[0]!=source.expected:
                deny('L2_SOURCE_CHANGED')
            c.execute('INSERT OR IGNORE INTO versions VALUES(?,?,?,?,?,?)',
                (d['tenant_id'],d['report_id'],d['version'],initial.payload,initial.display_hash,source.expected))

    @contextmanager
    def connection(self):
        c=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA synchronous=FULL')
        try:
            yield c
        finally:
            c.close()

    @contextmanager
    def transaction(self):
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    def person(self,sid,report):
        p=self.directory.require(sid,report).person
        if type(p) is not Person:
            deny()
        return p

    def _get(self,c,tenant,report,version=None):
        if version is None:
            row=c.execute('SELECT payload,display_hash,source_hash FROM versions '
                'WHERE tenant=? AND report=? ORDER BY version DESC LIMIT 1',(tenant,report)).fetchone()
        else:
            row=c.execute('SELECT payload,display_hash,source_hash FROM versions '
                'WHERE tenant=? AND report=? AND version=?',(tenant,report,version)).fetchone()
        if row is None or row[2]!=self.source.expected or sha(row[0])!=row[1]:
            deny('L2_VERSION_UNAVAILABLE')
        view=DeepReport(bytes(row[0]),row[2])
        self.source.read()  # current held source and all retained bytes still intact
        self.source.validate(view.document)
        if view.document['meta']['tenant_id']!=tenant or view.document['meta']['report_id']!=report:
            deny('L2_SCOPE_MISMATCH')
        return view

    def read(self,sid,report,version=None):
        with self.directory.lock:
            p=self.person(sid,report)
            if p.role not in ('OWNER','REVIEWER'):
                deny('L2_REVIEWER_REQUIRED')
            with self.connection() as c:
                view=self._get(c,p.tenant_id,report,version)
                self.directory.require(sid,report)
                return view

    def history(self,sid,report):
        with self.directory.lock:
            p=self.person(sid,report)
            if p.role not in ('OWNER','REVIEWER'):
                deny()
            with self.connection() as c:
                versions=c.execute('SELECT version,display_hash FROM versions WHERE tenant=? AND report=? '
                                   'ORDER BY version DESC',(p.tenant_id,report)).fetchall()
                decisions=[json.loads(r[0]) for r in c.execute('SELECT receipt FROM decisions '
                    'WHERE tenant=? AND report=? ORDER BY seq DESC LIMIT 100',(p.tenant_id,report))]
                grants=[json.loads(r[0]) for r in c.execute('SELECT grant_json FROM grants '
                    'WHERE tenant=? AND report=?',(p.tenant_id,report))] if p.role=='OWNER' else []
                return versions,decisions,grants

    def _pins(self,view,version,content_hash,display_hash):
        if (type(version) is not int or view.version['version']!=version
                or view.version['content_hash']!=content_hash or view.display_hash!=display_hash):
            deny('L2_STALE_VERSION')

    def review(self,sid,report,*,version,content_hash,display_hash,action,reason,items,attest=False):
        with self.directory.lock:
            p=self.person(sid,report)
            require_access(p.actor,p.tenant_id,'review')
            now=self.directory.now()
            bounded(reason,2000)
            if attest is not True:
                deny('L2_REVIEW_ATTESTATION_REQUIRED')
            if action not in ('APPROVE','REJECT','REQUEST_CHANGES'):
                deny('L2_INVALID_DECISION')
            with self.transaction() as c:
                view=self._get(c,p.tenant_id,report)
                self._pins(view,version,content_hash,display_hash)
                doc=view.document
                expected={f['id'] for f in doc['findings']}|{b['id'] for b in doc['blueprint']}
                if type(items) is not dict or set(items)!=expected or any(
                        v not in ('ACK','REJECT','REQUEST_CHANGES') for v in items.values()):
                    deny('L2_EVERY_ITEM_REQUIRES_REVIEW')
                if action=='APPROVE' and set(items.values())!={'ACK'}:
                    deny('L2_UNRESOLVED_REVIEW_ITEMS')
                core={'schema_version':'1.0','tenant_id':p.tenant_id,'decision_id':'review-'+uuid4().hex,
                    'report_version_id':view.version['report_version_id'],'version':version,
                    'content_hash':content_hash,'reviewer_id':p.actor_id,'action':action,'reason':reason,
                    'decided_at':at(now)}
                validate_contract('ReviewDecision',core)
                formal=self.directory.mode=='VERIFIED_DIRECTORY' and bool(p.verification_ref)
                if self.directory.mode!='CONTROLLED' and not formal:
                    deny('L2_VERIFIED_RESPONSIBLE_PERSON_REQUIRED')
                if action=='APPROVE':
                    approve_version(view.version,core,p.actor,version,view.findings)
                receipt={'decision':core,'display_hash':display_hash,'source_hash':view.source_digest,
                    'items':items,'reviewer_name':p.name,'reviewer_role':p.role,
                    'identity_verification_ref':p.verification_ref,
                    'identity_issuer':self.directory.issuer,'identity_subject':p.subject,
                    'directory_mode':self.directory.mode,
                    'authentication_key_id':self.directory.require(sid,report).key_id,
                    'scope':'RESPONSIBLE_PERSON_REVIEW' if formal else 'CONTROLLED_REVIEW_SIMULATION',
                    'formal_human_review':formal,'reviewer_attested':True,'external_delivery':False}
                c.execute('INSERT INTO decisions(id,tenant,report,version,receipt) VALUES(?,?,?,?,?)',
                          (core['decision_id'],p.tenant_id,report,version,encoded(receipt)))
                self.directory.require(sid,report)  # before the actual COMMIT
                return receipt

    def revise(self,sid,report,*,version,content_hash,display_hash,changes):
        with self.directory.lock:
            p=self.person(sid,report)
            require_access(p.actor,p.tenant_id,'review')
            with self.transaction() as c:
                previous=self._get(c,p.tenant_id,report)
                self._pins(previous,version,content_hash,display_hash)
                updated=self.source.revision(previous,changes,p.actor_id,at(self.directory.now()))
                c.execute('INSERT INTO versions VALUES(?,?,?,?,?,?)',(p.tenant_id,report,version+1,
                    updated.payload,updated.display_hash,updated.source_digest))
                self.directory.require(sid,report)
                return updated

    def _decision(self,c,p,report,view,*,require_approved=True):
        row=c.execute('SELECT receipt FROM decisions WHERE tenant=? AND report=? AND version=? '
            'ORDER BY seq DESC LIMIT 1',(p.tenant_id,report,view.version['version'])).fetchone()
        if row is None:
            deny('L2_REVIEW_REQUIRED')
        receipt=json.loads(row[0])
        expected='CONTROLLED_REVIEW_SIMULATION' if self.directory.mode=='CONTROLLED' else 'RESPONSIBLE_PERSON_REVIEW'
        if receipt['scope']!=expected or receipt['display_hash']!=view.display_hash:
            deny('L2_REVIEW_REQUIRED')
        reviewer=next((v for v in self.directory.people.values()
                       if v.actor_id==receipt['decision']['reviewer_id']),None)
        if (reviewer is None or not reviewer.active or reviewer.role not in ('OWNER','REVIEWER')
                or reviewer.tenant_id!=p.tenant_id
                or report not in reviewer.report_ids or receipt['identity_issuer']!=self.directory.issuer
                or receipt['identity_subject']!=reviewer.subject
                or receipt['identity_verification_ref']!=reviewer.verification_ref
                or receipt['authentication_key_id'] in self.directory.revoked_keys):
            deny('L2_REVIEWER_REVOKED')
        if self.directory.mode=='VERIFIED_DIRECTORY' and not reviewer.verification_ref:
            deny('L2_VERIFIED_RESPONSIBLE_PERSON_REQUIRED')
        validate_contract('ReviewDecision',receipt['decision'])
        if not require_approved and receipt['decision']['action']!='APPROVE':
            return receipt,view.version
        approved=approve_version(view.version,receipt['decision'],reviewer.actor,
                                  view.version['version'],view.findings)
        return receipt,approved

    def issue(self,sid,report,*,version,content_hash,display_hash,recipient_id,ttl=600):
        with self.directory.lock:
            p=self.person(sid,report)
            require_access(p.actor,p.tenant_id,'share')
            if self.directory.mode!='CONTROLLED':
                deny('L2_EXTERNAL_ACCESS_NOT_ENABLED')
            recipient=next((r for r in self.directory.people.values() if r.actor_id==recipient_id),None)
            if (recipient is None or recipient.role!='READER' or not recipient.active
                    or recipient.tenant_id!=p.tenant_id or report not in recipient.report_ids
                    or type(ttl) is not int or not 1<=ttl<=1800):
                deny('L2_DIRECTED_RECIPIENT_REQUIRED')
            with self.transaction() as c:
                view=self._get(c,p.tenant_id,report)
                self._pins(view,version,content_hash,display_hash)
                receipt,approved=self._decision(c,p,report,view)
                now=self.directory.now()
                token=secrets.token_urlsafe(32)
                grant={'schema_version':'1.0','tenant_id':p.tenant_id,'grant_id':'grant-'+uuid4().hex,
                    'report_version_id':view.version['report_version_id'],'content_hash':content_hash,
                    'subject_ref':recipient_id,'token_hash':hashlib.sha256(token.encode()).hexdigest(),
                    'status':'ACTIVE','issued_at':at(now),
                    'expires_at':(datetime.fromtimestamp(now,timezone.utc)+timedelta(seconds=ttl)).isoformat(),
                    'revoked_at':None}
                validate_contract('ShareGrant',grant)
                check_share(approved,receipt['decision'],grant,p.actor,version,
                            datetime.fromtimestamp(now,timezone.utc),'L2',findings=view.findings)
                c.execute('INSERT INTO grants VALUES(?,?,?,?,?,?,?,?,?,?)',(grant['grant_id'],p.tenant_id,
                    report,version,receipt['decision']['decision_id'],
                    encoded([recipient.actor_id,self.directory.issuer,recipient.subject]).decode(),
                    'CONTROLLED_DIRECTED_ACCESS',encoded([p.actor_id,self.directory.issuer,p.subject]).decode(),
                    display_hash,encoded(grant)))
                self.directory.require(sid,report)
                return grant,token

    def revoke(self,sid,report,grant_id):
        with self.directory.lock:
            p=self.person(sid,report)
            require_access(p.actor,p.tenant_id,'revoke_share')
            with self.transaction() as c:
                row=c.execute('SELECT grant_json FROM grants WHERE id=? AND tenant=? AND report=?',
                              (grant_id,p.tenant_id,report)).fetchone()
                if row is None:
                    deny()
                grant=json.loads(row[0])
                if grant['status']=='ACTIVE':
                    grant.update(status='REVOKED',revoked_at=at(self.directory.now()))
                    c.execute('UPDATE grants SET grant_json=? WHERE id=?',(encoded(grant),grant_id))
                self.directory.require(sid,report)
                return grant

    def access(self,sid,report,grant_id,token_hash):
        with self.directory.lock:
            p=self.person(sid,report)
            if self.directory.mode!='CONTROLLED' or p.role!='READER':
                deny('L2_DIRECTED_ACCESS_DENIED')
            with self.connection() as c:
                row=c.execute('SELECT decision_id,recipient,display_hash,grant_json,issued_by FROM grants '
                    'WHERE id=? AND tenant=? AND report=?',(grant_id,p.tenant_id,report)).fetchone()
                if row is None or row[1]!=encoded([p.actor_id,self.directory.issuer,p.subject]).decode():
                    deny('L2_DIRECTED_ACCESS_DENIED')
                grant=json.loads(row[3])
                if not secrets.compare_digest(grant['token_hash'],token_hash):
                    deny('L2_DIRECTED_ACCESS_DENIED')
                view=self._get(c,p.tenant_id,report)
                receipt,approved=self._decision(c,p,report,view)
                if row[0]!=receipt['decision']['decision_id'] or row[2]!=view.display_hash:
                    deny('L2_STALE_GRANT')
                # The original share predicate requires an Owner actor. That
                # actor is the currently configured grant authority, never the
                # reader role or a fabricated actor supplied in a request.
                owners=[v for v in self.directory.people.values() if v.role=='OWNER'
                        and encoded([v.actor_id,self.directory.issuer,v.subject]).decode()==row[4]
                        and v.tenant_id==p.tenant_id and report in v.report_ids and v.active]
                if len(owners)!=1:
                    deny('L2_GRANT_AUTHORITY_UNAVAILABLE')
                check_share(approved,receipt['decision'],grant,owners[0].actor,view.version['version'],
                    datetime.fromtimestamp(self.directory.now(),timezone.utc),'L2',findings=view.findings)
                self.directory.require(sid,report)
                return view
