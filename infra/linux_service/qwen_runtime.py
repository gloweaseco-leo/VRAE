"""One signed operator allowance -> original Qwen4/Quota. No browser settings.

Source-network deployment intent remains NOT_GRANTED for models; its original
Worker validator is unchanged. This independent AI allowance is verified at
bootstrap and again before each provider authorization.
"""
from datetime import datetime, UTC
import hashlib
import ipaddress
import os
import re
from pathlib import Path
import socket
import socketserver
import stat
import select
import threading

from contracts.l2_launch.contract import digest
from integration.authorized_targets.source_authority import root_document, verify
from vrae.intelligence.qwen import Config, Permission, Price, QwenProvider, Quota
from vrae.intelligence.qwen.provider import MODEL, MODEL_SOURCE, INPUT_CAP, OUTPUT_RESERVE, fail

PERMIT = Path('/run/service/ai/model-permit.json')
KEY = Path('/run/service/ai/model-key')
PEERS = Path('/run/service/ai/model-peers.json')
LEDGER = Path('/model-ledger/quota.sqlite')
AI_UID = 10008
DATA_SCOPE = 'MINIMIZED_TYPED_EVIDENCE_NO_RAW_HTML_PII'


def validate(envelope, *, source_sha, source_class, now=None):
    now = now or datetime.now(UTC)
    d = verify(envelope, 'DEPLOYMENT_OWNER', source_class, now)
    if (d.get('contract') != 'vrae.qwen-runtime-allowance.v1'
            or d.get('model_fee_go') != 'GRANTED' or d.get('region') != 'cn-beijing'
            or d.get('model') != MODEL or d.get('source_sha') != source_sha
            or d.get('data_scope') != DATA_SCOPE or type(d.get('max_output_tokens')) is not int
            or d.get('max_output_tokens') != 2048 or type(d.get('max_dispatches_per_task')) is not int
            or d.get('max_dispatches_per_task') != 1 or d.get('automatic_retry') is not False
            or type(d.get('daily_cap_micros')) is not int
            or not 1 <= d['daily_cap_micros'] <= 100_000_000
            or type(d.get('authorization_hashes')) is not list
            or (not d['authorization_hashes'] and d.get('allow_signed_model_consent') is not True)
            or len(d['authorization_hashes']) > 1000
            or any(type(v) is not str or not re.fullmatch(r'[0-9a-f]{64}', v) for v in d['authorization_hashes'])
            or type(d.get('approval_ref')) is not str
            or not re.fullmatch(r'[A-Za-z0-9_.-]{3,100}', d['approval_ref'])
            or d.get('price_source') != MODEL_SOURCE
            or type(d.get('input_micros_per_million')) is not int
            or type(d.get('output_micros_per_million')) is not int
            or d['input_micros_per_million'] < 10_000_000
            or d['output_micros_per_million'] < 30_000_000):
        fail('RUNTIME_MODEL_PERMISSION_REQUIRED')
    Config(d['workspace_id'])
    Price('runtime-official-qwen4', MODEL_SOURCE, d['input_micros_per_million'],
          d['output_micros_per_million'], datetime.fromisoformat(d['expires_at'])).check(now)
    return d


def load(now=None):
    try:
        envelope = root_document(PERMIT)
        d = envelope['document']
        checked = validate(envelope,
            source_sha=Path('/work/infra/linux_service/source-sha').read_text().strip(),
            source_class=d['source_class'], now=now)
        return checked, digest(envelope)
    except Exception:
        fail('RUNTIME_MODEL_PERMISSION_REQUIRED')


def check_permission(permission, now):
    d, pin = load(now)
    if (permission.runtime_approval != pin
            or permission.synthetic_only != (d['source_class'] == 'CONTROLLED_NON_CUSTOMER')
            or permission.expires_at != datetime.fromisoformat(d['expires_at'])
            or not permission.approval_ref.startswith('runtime-')):
        fail('RUNTIME_MODEL_PERMISSION_REQUIRED')


def key_bytes():
    try:
        fd = os.open(KEY, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        fail('KEY_REQUIRED')
    try:
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_gid != AI_UID
                or stat.S_IMODE(s.st_mode) != 0o440
                or s.st_size > 256):
            fail('KEY_REQUIRED')
        return os.read(fd, 257).decode('ascii')
    finally:
        os.close(fd)


def provider_for(binding, job, held, now=None):
    now = now or datetime.now(UTC)
    d, pin = load(now)
    try:
        authorization = held['artifact']['source_authority']['authorization']
        consent = held['source_plan'].get('model_processing', {})
        scoped_consent = (d.get('allow_signed_model_consent') is True
            and consent.get('provider') == 'aliyun-bailian-beijing'
            and consent.get('region') == 'cn-beijing' and consent.get('data_scope') == DATA_SCOPE
            and consent.get('consent') == 'EXPLICITLY_ACKNOWLEDGED'
            and type(consent.get('consent_reference')) is str
            and 8 <= len(consent['consent_reference']) <= 128)
        # Original current_input verifies the SOURCE_ADMIN signature and exact
        # current plan_sha256, which includes the consent fields. A browser flag
        # or unsigned source/consent document cannot reach this held input.
        if ((digest(authorization) not in d['authorization_hashes'] and not scoped_consent)
                or authorization['document']['source_class'] != d['source_class']
                or held['task']['tenant_id'] != binding['tenant_id']
                or held['task']['job_id'] != str(job)):
            fail('MODEL_SOURCE_NOT_AUTHORIZED')
    except (KeyError, TypeError):
        fail('MODEL_SOURCE_NOT_AUTHORIZED')
    task = hashlib.sha256((binding['tenant_id'] + '/' + str(job)).encode()).hexdigest()
    expiry = datetime.fromisoformat(d['expires_at'])
    price = Price('runtime-official-qwen4', MODEL_SOURCE, d['input_micros_per_million'],
                  d['output_micros_per_million'], expiry)
    from infra.qwen_provider.transport import NativeTransport
    return QwenProvider(Config(d['workspace_id']),
        Quota(LEDGER, batch='runtime-' + task, daily_cap_micros=d['daily_cap_micros']),
        permission=Permission('runtime-' + task, expiry, 1, price.cost(INPUT_CAP, OUTPUT_RESERVE),
                              synthetic_only=d['source_class'] == 'CONTROLLED_NON_CUSTOMER',
                              runtime_approval=pin), price=price, key=key_bytes(),
        _transport=NativeTransport(peer_pins=PEERS))


def addresses(document):
    host = Config(document['workspace_id']).host
    values = sorted({r[4][0] for r in socket.getaddrinfo(host, 443, family=socket.AF_INET,
                                                       type=socket.SOCK_STREAM)})
    if not values or len(values) > 32 or any(not ipaddress.ip_address(v).is_global for v in values):
        fail('MODEL_DNS_REFUSED')
    return values


def pg_forward(listen, port, target, target_port):
    """Bounded PG wire transport only, never an authority snapshot or SQL RPC."""
    slots = threading.BoundedSemaphore(16)
    class Forward(socketserver.BaseRequestHandler):
        def handle(self):
            if not slots.acquire(blocking=False):
                return
            try:
                with socket.create_connection((target, target_port), timeout=2) as upstream:
                    self.request.settimeout(4)
                    upstream.settimeout(4)
                    while True:
                        ready, _, _ = select.select([self.request, upstream], [], [], 5)
                        if not ready:
                            return
                        for s in ready:
                            data = s.recv(65536)
                            if not data:
                                return
                            (upstream if s is self.request else self.request).sendall(data)
            except OSError:
                pass
            finally:
                slots.release()
    server = socketserver.ThreadingTCPServer((listen, port), Forward)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def model_fence(command, document):
    """AI10008 IP443 only. Root-private DNS pins; AI needs no DNS egress."""
    peers = addresses(document)
    from infra.linux_service.supervisor import write
    from contracts.l2_launch.contract import canonical
    write(PEERS, canonical({'host': Config(document['workspace_id']).host, 'addresses': peers}), mode=0o440)
    os.chown(PEERS, 0, AI_UID)
    chain = 'VRAE_SERVICE_' + str(AI_UID)
    for peer in peers:
        command('iptables', '-w', '3', '-I', chain, '1', '-p', 'tcp', '-d', peer,
                '--dport', '443', '-j', 'ACCEPT')
    return {'uid': AI_UID, 'provider_ip_count': len(peers), 'dns_count': 0,
            'allowed_https_port': 443, 'default': 'REJECT'}
