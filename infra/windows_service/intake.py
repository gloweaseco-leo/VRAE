"""Root-only, bounded enrollment into the ORIGINAL target registry and queue.

No network key or legal authority is accepted from HTTP input. Domain control
is proven by a DNS TXT record plus explicit read-only/AI-data notice consent.
The accepted Collector still performs actual DNS pin, robots and redirect checks.
"""
import base64
from datetime import datetime, UTC, timedelta
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import struct
from urllib.parse import urlsplit
import dns.resolver
import psycopg
from psycopg.types.json import Jsonb
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from contracts.l2_launch.contract import canonical, digest, permission_document, validate
from contracts.l2_launch.vf_b import VERSION, submission_document
from integration.authorized_targets import store
from integration.authorized_targets.source_authority import authorization, verify, DEPLOYMENT, root_document
from integration.authorized_targets.operator import activate
from infra.linux_service.supervisor import INPUT, private, write, clear_chain
from infra.authorized_targets.egress_policy import install
from vrae.collection.policy import canonical_url
from vrae.collection.resolver import public_addresses

SOCKET = "/run/service/target-issuer.sock"
CONSENT = "VRAE-READONLY-DIAGNOSIS-1"
CONSENT_TEXT = "I am authorized to permit read-only diagnosis of the exact proven domain and paths; I understand evidence may be processed by an explicitly enabled model provider. No write or account access is permitted."


class Denied(Exception):
    def __init__(self, reason, status=403):
        self.reason, self.status = reason, status


def admin():
    return psycopg.connect(host="127.0.0.1", dbname="vrae_ra4a_p1", user="postgres",
        password=private(INPUT / "pg-password").decode(), autocommit=True,
        connect_timeout=2, options="-c statement_timeout=5000 -c lock_timeout=1500")


def key(name):
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private(INPUT / (name + "-key")).decode()))


def envelope(name, document):
    return {"key_id": name, "document": document, "signature": key(name).sign(canonical(document)).hex()}


def current_grants(connection=None):
    held = connection is not None
    c = connection or admin()
    try:
        rows = c.execute("""SELECT a.envelope,p.document,
            encode(sha256(convert_to(p.document::text,'UTF8')),'hex')
            FROM target_v1.authorizations a JOIN target_v1.plans p USING(tenant_id,target_id)
            WHERE NOT a.revoked AND NOT p.revoked AND a.expires_at>clock_timestamp()""").fetchall()
        grants = []
        for signed, plan, sha in rows:
            authorization(signed, plan, plan_sha256=sha)
            grants.append(signed)
        return grants
    finally:
        if not held:
            c.close()


def apply_policy(connection=None):
    old = root_document(DEPLOYMENT)
    doc = old["document"]
    grants = current_grants(connection)
    ips = sorted({ip for grant in grants for ip in grant["document"]["destination_ips"]})
    for tool in ("iptables", "ip6tables"):
        clear_chain(tool, "VRAE_TARGET_V2", 65532)
    policy = install(namespace_inode=doc["namespace_inode"], parent_network_mode=doc["parent_network_mode"],
        interfaces=doc["interfaces"], destination_ips=ips, nameservers=doc["nameservers"],
        network_internal=doc["network_internal"], allow_no_targets=not grants)
    doc.update(authorization_hashes=[digest(g) for g in grants], permitted_destination_ips=ips,
               firewall_policy_sha256=policy.pop("policy_sha256"), firewall_policy=policy)
    write(DEPLOYMENT, canonical(envelope("deployment", doc)), mode=0o444)


def scope(body):
    if set(body) != {"url", "paths", "consent"}:
        raise Denied("INVALID_TARGET_APPLICATION")
    consent = body["consent"]
    if (set(consent) != {"version", "read_only_authorized", "model_data_notice"}
        or consent["version"] != CONSENT or consent["read_only_authorized"] is not True
        or consent["model_data_notice"] is not True):
        raise Denied("EXPLICIT_READONLY_CONSENT_REQUIRED")
    url = canonical_url(body["url"])
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.port not in (None, 443) or parts.query or parts.fragment
        or not parts.hostname or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", parts.hostname)
        or parts.hostname.endswith((".local", ".localhost", ".internal", ".test", ".invalid"))):
        raise Denied("PUBLIC_HTTPS_DOMAIN_REQUIRED")
    import ipaddress
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        pass
    else:
        raise Denied("DOMAIN_NAME_REQUIRED")
    origin = "https://" + parts.hostname
    if type(body["paths"]) is not list or len(body["paths"]) > 2:
        raise Denied("BOUNDED_EXACT_PATHS_REQUIRED")
    paths = list(dict.fromkeys(["/robots.txt", "/", parts.path or "/", *body["paths"]]))
    if len(paths) > 5 or any(type(p) is not str or len(p)>256 or urlsplit(canonical_url(origin+p)).path != p
                             or "?" in p or "#" in p for p in paths):
        raise Denied("BOUNDED_EXACT_PATHS_REQUIRED")
    return {"origin": origin, "host": parts.hostname, "paths": paths, "consent": consent}


def resolver():
    doc = root_document(DEPLOYMENT)["document"]
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = list(public_addresses(doc["nameservers"]))
    r.cache = None
    r.lifetime = 3
    r.timeout = 2
    return r


def resolve_public(host):
    r = resolver()
    ips = []
    for kind in ("A", "AAAA"):
        answer = r.resolve(host + ".", kind, search=False, raise_on_no_answer=False)
        ips.extend(str(record) for record in answer)
    return list(public_addresses(ips))


def caller(role, cookie, csrf):
    cfg = json.loads(private(INPUT / "api.json"))
    entries = [b for b in cfg["bindings"] if b["role"] == role and not b.get("port")]
    if len(entries) != 1:
        raise Denied("CURRENT_INVITED_SUBJECT_REQUIRED")
    b = entries[0]
    return b, store.invoke(b, "session", b["tenant_id"], cookie, csrf)


def delegation():
    source_class = json.loads(private(INPUT / "manifest.json"))["source_class"]
    doc = verify(json.loads(private(INPUT / "enrollment-delegation.json")), "DEPLOYMENT_OWNER", source_class)
    if (doc["contract"] != "vrae.dns-target-enrollment.v1" or doc["proof"] != "DNS_TXT_OR_OPERATOR_OWNED_SOURCE_AND_EXPLICIT_CONSENT"
        or doc["purpose"] != "READONLY_DIAGNOSIS" or doc["max_pages"] != 4):
        raise Denied("OPERATOR_DELEGATION_REQUIRED")
    return doc


def operator_owned(origin):
    path=INPUT/"source-ownership.json"
    if not path.exists():
        return None
    records=json.loads(private(path))
    signed=records.get(origin)
    if signed is None:
        return None
    source_class=json.loads(private(INPUT/"manifest.json"))["source_class"]
    doc=verify(signed,"SOURCE_ADMIN",source_class)
    if (doc["contract"]!="vrae.operator-owned-source.v1" or doc["origin"]!=origin
        or doc["control_proof"]!="TAILSCALE_AUTHENTICATED_OPERATOR_NODE"
        or not doc["reference"] or not doc["node_id"] or len(doc["server_certificate_sha256"])!=64):
        raise Denied("ACTUAL_OPERATOR_ORIGIN_CONTROL_REQUIRED")
    return doc


def challenge(binding, actor, body):
    target = scope(body)
    resolve_public(target["host"])
    delegation()
    doc = {**target, "tenant": binding["tenant_id"], "subject": actor["subject_ref"],
           "invitation": actor["invitation_ref"], "expires": int(datetime.now(UTC).timestamp()) + 600,
           "nonce": secrets.token_hex(16)}
    raw = canonical(doc)
    mac = hmac.new(private(INPUT / "enrollment-hmac-key"), raw, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(raw + mac).decode()
    owned=operator_owned(target["origin"])
    return {"contract": "vrae.target-application.v1", "application_token": token,
        "proof": ({"type":"OPERATOR_OWNED_PUBLIC_ORIGIN","reference":owned["reference"]} if owned else
                  {"type": "DNS_TXT", "name": "_vrae-authorization." + target["host"],
                   "value": "vrae-" + doc["nonce"] + "-" + digest(target)}),
        "expires_at": datetime.fromtimestamp(doc["expires"], UTC).isoformat(),
        "consent_version": CONSENT, "consent_text_sha256": digest(CONSENT_TEXT),
        "legal_ownership_asserted_by_server": False}


def authorize(binding, actor, body):
    if set(body) != {"application_token"}:
        raise Denied("INVALID_TARGET_APPLICATION")
    raw = base64.urlsafe_b64decode(body["application_token"])
    if len(raw) > 8192 or len(raw) < 33:
        raise Denied("INVALID_TARGET_APPLICATION")
    value, mac = raw[:-32], raw[-32:]
    if not hmac.compare_digest(hmac.new(private(INPUT / "enrollment-hmac-key"), value, hashlib.sha256).digest(), mac):
        raise Denied("APPLICATION_TAMPERED")
    doc = json.loads(value)
    if (doc["tenant"], doc["subject"], doc["invitation"]) != (
        binding["tenant_id"], actor["subject_ref"], actor["invitation_ref"]
    ) or doc["expires"] <= datetime.now(UTC).timestamp():
        raise Denied("APPLICATION_SCOPE_OR_EXPIRY_DENIED")
    delegate = delegation()
    target = {k: doc[k] for k in ("origin", "host", "paths", "consent")}
    expected = "vrae-" + doc["nonce"] + "-" + digest(target)
    owned=operator_owned(doc["origin"])
    if owned is None:
        answers = resolver().resolve("_vrae-authorization." + doc["host"] + ".", "TXT", search=False)
        if expected not in [b"".join(record.strings).decode() for record in answers]:
            raise Denied("DNS_DOMAIN_CONTROL_PROOF_REQUIRED")
    ips = resolve_public(doc["host"])
    now = datetime.now(UTC)
    end = min(datetime.fromisoformat(delegate["expires_at"]),
              datetime.fromisoformat(actor["invitation"]["expires_at"]), now + timedelta(hours=2))
    target_id = "url-" + digest(doc["origin"])[:32]
    tenant = binding["tenant_id"]
    with admin() as c, c.transaction():
        # No in-flight capture may see its signed kernel proof change.
        c.execute("LOCK TABLE ra4a.jobs IN SHARE ROW EXCLUSIVE MODE")
        if c.execute("SELECT 1 FROM ra4a.jobs WHERE state='LEASED' AND lease_until>clock_timestamp() LIMIT 1").fetchone():
            raise Denied("DIAGNOSIS_BUSY_RETRY_TARGET_AUTHORIZATION", 429)
        row = c.execute("SELECT document,revoked FROM target_v1.plans WHERE tenant_id=%s AND target_id=%s FOR UPDATE",
                        (tenant,target_id)).fetchone()
        if row:
            plan, revoked = row
            if revoked or plan["exact_paths"] != doc["paths"] or datetime.fromisoformat(plan["expires_at"]) <= now:
                raise Denied("SOURCE_SCOPE_REQUIRES_NEW_OPERATOR_AUTHORIZATION",409)
        else:
            policy = {"schema_version":"1.0","tenant_id":tenant,"policy_id":"policy-"+target_id,
                "policy_version":1,"mode":"OWNER_AUTHORIZED_DEEP","permitted_hosts":[doc["host"]],
                "scope_paths":doc["paths"],"authorization_reference":"auth-"+target_id,
                "expires_at":end.isoformat(),"revoked_at":None,"created_at":now.isoformat()}
            plan = {"tenant_id":tenant,"target_id":target_id,"origin":doc["origin"],"exact_paths":doc["paths"],
                "terms_reference":"customer-readonly-consent-v1","retain_raw_html":True,
                "authorization_kind":"ADMIN_AUTHORIZED_READONLY","execution_profile":"ADMIN_TARGET_V2",
                "source_class":delegate["source_class"],"expires_at":end.isoformat(),"revoked":False,
                "policy":policy,"limits":{"max_pages":4,"max_bytes":500000,"max_total_bytes":2000000,
                "max_requests":12,"max_redirects":2,"request_seconds":4,"task_seconds":18,"interval_seconds":1}}
            c.execute("INSERT INTO ra4a.policies VALUES(%s,%s,1,'ALLOWED',%s,'AUTHORIZED_READONLY')",
                      (tenant,policy["policy_id"],end))
            c.execute("INSERT INTO target_v1.plans VALUES(%s,%s,%s,%s,false)",
                      (tenant,target_id,doc["origin"],Jsonb(plan)))
            sha = c.execute("SELECT encode(sha256(convert_to(document::text,'UTF8')),'hex') FROM target_v1.plans WHERE tenant_id=%s AND target_id=%s",
                            (tenant,target_id)).fetchone()[0]
            grant = {k:plan[k] for k in ("tenant_id","target_id","source_class","origin","exact_paths","limits")}
            grant.update(contract="vrae.target-authorization.v2",reference=policy["authorization_reference"],
                plan_sha256=sha,purpose="READONLY_DIAGNOSIS",methods=["GET","HEAD"],
                legal_reference=("OPERATOR_OWNED_PUBLIC_SOURCE-" if owned else "INVITED_ATTESTATION_AND_DNS_CONTROL-")+digest(doc),
                terms_reference=plan["terms_reference"],robots="ENFORCE",not_before=now.isoformat(),
                expires_at=end.isoformat(),retention_until=(end+timedelta(hours=1)).isoformat(),destination_ips=ips)
            activate(c,envelope("source",grant))
        inv = c.execute("SELECT document FROM target_v1.invitations WHERE tenant_id=%s AND reference=%s AND NOT revoked AND (document->>'expires_at')::timestamptz>clock_timestamp() FOR UPDATE",
                        (tenant,actor["invitation_ref"])).fetchone()
        if not inv:
            raise Denied("CURRENT_INVITED_SUBJECT_REQUIRED")
        value = inv[0]
        if target_id not in value["target_ids"]:
            value["target_ids"].append(target_id)
            c.execute("UPDATE target_v1.invitations SET document=%s WHERE tenant_id=%s AND reference=%s",
                      (Jsonb(value),tenant,actor["invitation_ref"]))
        apply_policy(c)
    return {"contract":"vrae.target-application.v1","state":"AUTHORIZED_FOR_READONLY_DIAGNOSIS",
            "target_id":target_id,"expires_at":plan["expires_at"],"legal_reference_kind":"OPERATOR_OWNED_PUBLIC_SOURCE" if owned else "INVITED_ATTESTATION_AND_DNS_CONTROL"}


def signed_submission(binding, actor, body, cookie, csrf):
    if set(body) != {"url","idempotency_key","accepted_at","consent_version","language"}:
        raise Denied("INVALID_DIAGNOSIS_REQUEST")
    if body["consent_version"] != CONSENT or body["language"] not in ("zh","en"):
        raise Denied("EXPLICIT_READONLY_CONSENT_REQUIRED")
    accepted = datetime.fromisoformat(body["accepted_at"])
    if not datetime.now(UTC)-timedelta(minutes=30) <= accepted <= datetime.now(UTC):
        raise Denied("CURRENT_DIAGNOSIS_CONSENT_REQUIRED")
    url = canonical_url(body["url"])
    if not re.fullmatch(r"[A-Za-z0-9_.-]{8,128}",body["idempotency_key"]):
        raise Denied("IDEMPOTENCY_KEY_REQUIRED")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.port not in (None,443) or parts.query or parts.fragment:
        raise Denied("PUBLIC_HTTPS_DOMAIN_REQUIRED")
    site = "https://" + parts.hostname + "/"
    resolved = store.invoke(binding,"plan",binding["tenant_id"],cookie,csrf,site)
    plan = resolved["plan"]
    if (parts.path or "/") not in plan["exact_paths"]:
        raise Denied("EXACT_PATH_AUTHORIZATION_REQUIRED")
    authorization(resolved["source_authorization"],plan,plan_sha256=resolved["plan_sha256"])
    if accepted < datetime.fromisoformat(plan["policy"]["created_at"]):
        raise Denied("CURRENT_DIAGNOSIS_CONSENT_REQUIRED")
    uid = digest({"tenant":binding["tenant_id"],"subject":actor["subject_ref"],"key":body["idempotency_key"]})[:32]
    request = {"schema_version":"1.0","tenant_id":binding["tenant_id"],"request_id":"url-request-"+uid,
        "audit_id":"url-audit-"+uid,"site_url":site,"audit_mode":"L1",
        "source_policy_ref":plan["policy"]["policy_id"],"source_policy_version":plan["policy"]["policy_version"],
        "source_system":"vrae","source_reference":actor["invitation_ref"],
        "idempotency_key":body["idempotency_key"],"requested_at":body["accepted_at"]}
    command = {"contract_version":"vf-vrae-r0.1","request":request,"permission_reference":{
        "reference":plan["policy"]["authorization_reference"],"consent_version":CONSENT,"consent_sha256":digest(CONSENT_TEXT)}}

    def proof(document):
        value = {"alg":"Ed25519","key_id":"permission","claim":{
            "audience":"vrae-launch-r0-contract","purpose":"permission","tenant_id":binding["tenant_id"],
            "subject_ref":"vrae-operator-permission","document_sha256":digest(document),
            "issued_at":body["accepted_at"],"expires_at":plan["expires_at"]}}
        return {**value,"signature":key("permission").sign(canonical(value)).hex()}
    command["permission_reference"]["proof"] = proof(permission_document(command,plan["policy"]))
    value = {"contract_version":VERSION,"command":command,"normalized_host":parts.hostname,
        "language":body["language"],"subject_ref":actor["subject_ref"],"invitation_ref":actor["invitation_ref"],
        "diagnosis_consent":{"consent_version":CONSENT,"accepted_at":body["accepted_at"],"text_sha256":digest(CONSENT_TEXT)}}
    value["submission_proof"] = proof(submission_document(value))
    validate("VFSubmit",value)
    return value


def contract():
    return {"contract":"vrae.target-intake.v1","consent_version":CONSENT,
        "consent_text":CONSENT_TEXT,"consent_text_sha256":digest(CONSENT_TEXT),
        "identity":"Current original invited subject cookie/CSRF plus certificate-bound service bearer",
        "application":{"method":"POST","path":"/v1/target-applications",
            "body":{"url":"https://owned-domain.example/","paths":["/products","/contact"],
                    "consent":{"version":CONSENT,"read_only_authorized":True,"model_data_notice":True}}},
        "authorization":{"method":"POST","path":"/v1/target-applications/authorize",
            "body":{"application_token":"<returned opaque token>"}},
        "diagnosis":{"method":"POST","path":"/v1/diagnoses","success":202,
            "body":{"url":"https://owned-domain.example/","idempotency_key":"<stable unique intent key>",
                    "accepted_at":"<current UTC ISO timestamp, retained for retries>",
                    "consent_version":CONSENT,"language":"zh"}},
        "report_path":"/v1/report-authority/audits/{audit_ref}/report",
        "report_profile":"VERIFIED_HUMAN_CUSTOMER_REPORT","report_port":8443,
        "limits":{"concurrent_worker":1,"max_pages":4,"request_seconds":4,
                  "capture_seconds":18,"original_worker_lease_seconds":30},
        "ownership":"DNS TXT control and explicit permission, or separately operator-signed owned source",
        "rejection":"Private or mixed DNS, wrong subject, missing permission, expiry and revoked sources are denied",
        "report_release":"Actual verified Reviewer decision and current directed ShareGrant required"}


def rpc(action, role, cookie, csrf, body):
    raw = canonical({"action":action,"role":role,"cookie":cookie,"csrf":csrf,"body":body})
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(12)
        sock.connect(SOCKET)
        sock.sendall(raw+b"\n")
        response = sock.makefile("rb").readline(65537)
    if len(response)>65536:
        raise PermissionError("BOUNDED_ISSUER_RESPONSE_REQUIRED")
    return json.loads(response)


def main():
    p=__import__("argparse").ArgumentParser()
    p.add_argument("--config",required=True)
    p.parse_args()
    delegation()
    if os.path.exists(SOCKET):
        os.unlink(SOCKET)
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(SOCKET)
        os.chmod(SOCKET,0o600)
        os.chown(SOCKET,10001,10001)
        server.listen(4)
        while True:
            connection,_=server.accept()
            with connection:
                try:
                    uid=struct.unpack("3i",connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]
                    if uid!=10001:
                        raise Denied("TRUSTED_APP_PEER_REQUIRED")
                    connection.settimeout(5)
                    raw=connection.makefile("rb").readline(16385)
                    if len(raw)>16384:
                        raise Denied("BOUNDED_APPLICATION_REQUIRED")
                    request=json.loads(raw)
                    b,actor=caller(request["role"],request["cookie"],request["csrf"])
                    if request["action"]=="challenge":
                        data=challenge(b,actor,request["body"])
                    elif request["action"]=="authorize":
                        data=authorize(b,actor,request["body"])
                    elif request["action"]=="submission":
                        data=signed_submission(b,actor,request["body"],request["cookie"],request["csrf"])
                    else:
                        raise Denied("UNKNOWN_ISSUER_OPERATION")
                    response={"status":200 if request["action"]=="submission" else 201,"data":data}
                except Denied as error:
                    response={"status":error.status,"data":{"contract":"vrae.target-application.v1","state":"DENIED","reason":error.reason}}
                except Exception:
                    response={"status":403,"data":{"contract":"vrae.target-application.v1","state":"DENIED","reason":"CURRENT_SOURCE_AUTHORITY_REQUIRED"}}
                connection.sendall(canonical(response)+b"\n")


if __name__=="__main__":
    main()

