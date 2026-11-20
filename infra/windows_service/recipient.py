"""Reader-only exchange of ORIGINAL invited session + directed grant.

Never issues a fake MFA assertion or an Owner/Reviewer identity. All report
decisions, source facts and permission/version checks remain in the accepted Ledger.
"""
from datetime import datetime, UTC
import hashlib
import secrets
from contracts.l2_launch.contract import Refused, digest
from integration.authorized_targets import store
from vrae.l2.identity import Person, Session
from vrae.l2.verified import CURRENT_REPORTS

ASSURANCE="PG_INVITED_SUBJECT_AND_DIRECTED_GRANT_V1"


def session(app,sid):
    return app.directory.sessions.get(hashlib.sha256(sid.encode()).digest()) if type(sid) is str else None


def authorized(app):
    if not app.verified or app.authority.document.get("recipient_authority")!=ASSURANCE:
        raise Refused("FORBIDDEN_ROLE")


def current(connection,binding,claims):
    result=connection.execute("SELECT target_v1.recipient_context(%s,%s,%s,%s)",
        (binding["tenant_id"],claims["audit_ref"],claims["cookie_sha256"],claims["csrf_sha256"])).fetchone()[0]
    if "scope" in claims and result!=claims["scope"]:
        raise Refused("FORBIDDEN_ROLE")
    return result


def guard_scope(stack,app,binding,sid,job):
    held=session(app,sid)
    if held is None or not held.grant_claims.get("recipient_bridge"):
        return
    authorized(app)
    claims=held.grant_claims
    if held.person.role!="READER" or claims["scope"]["job_id"]!=job:
        raise Refused("FORBIDDEN_ROLE")
    connection=stack.enter_context(store.connect(binding))
    stack.enter_context(connection.transaction())
    current(connection,binding,claims)
    # Locks on current PG session/invitation/source remain held through HTTP send.


def exchange(app,binding,body):
    authorized(app)
    if set(body)!={"audit_ref","task_cookie","task_csrf","grant_id","grant_token"}:
        raise Refused("FORBIDDEN_ROLE")
    if any(type(body[k]) is not str or not 16<=len(body[k])<=128
           for k in ("task_cookie","task_csrf","grant_id","grant_token")):
        raise Refused("FORBIDDEN_ROLE")
    claims={"recipient_bridge":True,"audit_ref":body["audit_ref"],
        "cookie_sha256":hashlib.sha256(body["task_cookie"].encode()).hexdigest(),
        "csrf_sha256":hashlib.sha256(body["task_csrf"].encode()).hexdigest(),
        "grant_id":body["grant_id"],"grant_token_sha256":hashlib.sha256(body["grant_token"].encode()).hexdigest()}
    with app.directory.lock,store.connect(binding) as c,c.transaction():
        scope=current(c,binding,claims)
        person=register(app,scope["tenant_id"],scope["subject_ref"],scope)
        now=app.directory.now()
        if len(app.directory.sessions)>=64:
            raise Refused("FORBIDDEN_ROLE")
        sid=secrets.token_urlsafe(32)
        sid_hash=hashlib.sha256(sid.encode()).digest()
        expiry=min(now+300,datetime.fromisoformat(scope["expires_at"]).timestamp(),app.directory.expires)
        claims["scope"]=scope
        app.directory.sessions[sid_hash]=Session(person,expiry,"pg-invited-recipient",app.directory.generation(),claims)
        try:
            path=app.root/(binding["tenant_id"]+"-"+scope["job_id"]+".sqlite")
            with app.authority.current(binding,scope["job_id"],path,app.directory) as (ledger,rid):
                view=ledger.access(sid,rid,body["grant_id"],claims["grant_token_sha256"])
                result={"contract":"vrae.report-recipient-session.v1","report_session":sid,
                    "expires_at":datetime.fromtimestamp(expiry,UTC).isoformat(),"assurance":ASSURANCE,
                    "report_version":view.version,"display_hash":view.display_hash,
                    "grants_review_or_owner_role":False}
        except Exception:
            app.directory.sessions.pop(sid_hash,None)
            raise
        return result



def register(app,tenant,subject,scope):
    authorized(app)
    person=app.directory.people.get(subject)
    if person is None:
        person=Person("recipient-"+digest([tenant,subject])[:20],subject,
            "Current invited report recipient",tenant,"READER",(CURRENT_REPORTS,),
            verification_ref="PG_INVITED_RECIPIENT-"+digest(scope))
        app.directory.people[subject]=person
    if person.role!="READER" or not person.active or person.tenant_id!=tenant:
        raise Refused("FORBIDDEN_ROLE")
    return person


def for_current_owner_view(app,person):
    if (not app.verified or person.role not in ("OWNER","REVIEWER")
        or app.authority.document.get("recipient_authority")!=ASSURANCE):
        return None
    scope=app.authority.scope.get()
    if not scope or scope["tenant_id"]!=person.tenant_id:
        raise Refused("FORBIDDEN_ROLE")
    recipient=register(app,scope["tenant_id"],scope["recipient_subject"],scope)
    return {"recipient_id":recipient.actor_id,"subject_ref":recipient.subject,
            "assurance":ASSURANCE,"grants_review_or_owner_role":False}


def check_grant(app,sid,headers):
    held=session(app,sid)
    if held is None or not held.grant_claims.get("recipient_bridge"):
        return
    claims=held.grant_claims
    if (headers.get("X-Report-Grant")!=claims["grant_id"]
        or hashlib.sha256(headers.get("X-Report-Token","").encode()).hexdigest()!=claims["grant_token_sha256"]):
        raise Refused("FORBIDDEN_ROLE")
