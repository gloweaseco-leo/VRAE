"""Two owned PG16 environments; credentials/dumps remain private and disposable."""
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
import uuid

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'integration/ra4e/.runtime'
DOCS = ROOT / 'docs/03-engineering/ra4e-b7p0-restore'
LABEL = 'vrae.ra4e.b7p0'
DB = 'vrae_ra4a_p1'
IMAGE = (ROOT / 'infra/ra4a/image.txt').read_text().strip()


class RecoveryDenied(RuntimeError):
    """Only fixed, non-sensitive codes cross the orchestration boundary."""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()


def invoke(*args, data=None, timeout=60):
    return subprocess.run(['docker', *args], input=data, capture_output=True, timeout=timeout)


def docker(*args, data=None, timeout=60):
    p = invoke(*args, data=data, timeout=timeout)
    if p.returncode:
        raise RecoveryDenied('OWNED_DOCKER_COMMAND_FAILED')
    return p.stdout


@dataclass
class Environment:
    tag: str
    private: Path
    proof: Path
    admin_password: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    runtime_passwords: dict = field(default_factory=dict, repr=False)
    port: int | None = None

    def __post_init__(self):
        if self.tag not in ('source', 'destination'):
            raise RecoveryDenied('ENVIRONMENT_TAG_DENIED')
        self.name = 'vrae-ra4e-' + uuid.uuid4().hex[:12] + '-' + self.tag
        self.resources = [('container', self.name), ('network', self.name + '-net'), ('volume', self.name + '-data')]
        self.private.mkdir(parents=True, exist_ok=False)
        self.proof.mkdir(parents=True, exist_ok=False)
        self.state = self.private / 'state.json'
        self.write_state()
        self.proof.joinpath('ownership.json').write_bytes(encode({'label': LABEL, 'name': self.name, 'resources': self.resources, 'image': IMAGE}))

    def write_state(self):
        value = {'host': '127.0.0.1', 'port': self.port, 'dbname': DB,
                 'container': self.name, 'admin_password': self.admin_password,
                 'runtime_passwords': self.runtime_passwords}
        self.state.write_bytes(encode(value))

    def owned(self, kind, name):
        if (kind, name) not in self.resources or not re.fullmatch(r'vrae-ra4e-[0-9a-f]{12}-(source|destination)(-net|-data)?', name):
            raise RecoveryDenied('RESOURCE_NAME_DENIED')
        template = '{{json .Config.Labels}}' if kind == 'container' else '{{json .Labels}}'
        p = invoke(kind, 'inspect', '--format', template, name)
        if p.returncode:
            error = p.stderr.decode(errors='replace').lower()
            if name.lower() not in error or not any(x in error for x in ('no such', 'not found')):
                raise RecoveryDenied('RESOURCE_ABSENCE_UNPROVEN')
            return False
        if json.loads(p.stdout).get(LABEL) != self.name:
            raise RecoveryDenied('RESOURCE_OWNERSHIP_DENIED')
        return True

    def start(self):
        for kind, name in self.resources:
            if self.owned(kind, name):
                raise RecoveryDenied('RESOURCE_ALREADY_PRESENT')
        cfg = self.private / 'postgres.env'
        cfg.write_text('POSTGRES_PASSWORD=' + self.admin_password + '\nPOSTGRES_DB=' + DB + '\nPOSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n')
        try:
            docker('network', 'create', '--label', LABEL + '=' + self.name, self.name + '-net')
            docker('volume', 'create', '--label', LABEL + '=' + self.name, self.name + '-data')
            docker('run', '-d', '--name', self.name, '--network', self.name + '-net', '--label', LABEL + '=' + self.name,
                   '--env-file', str(cfg), '-p', '127.0.0.1::5432', '--mount',
                   'type=volume,src=' + self.name + '-data,dst=/var/lib/postgresql/data',
                   '--memory', '512m', '--cpus', '1', '--pids-limit', '128', IMAGE)
            image_digests = json.loads(docker('image', 'inspect', '--format', '{{json .RepoDigests}}', IMAGE))
            if not any(v.endswith('@' + IMAGE.split('@')[1]) for v in image_digests):
                raise RecoveryDenied('PG_IMAGE_DIGEST_MISMATCH')
            bindings = json.loads(docker('inspect', '--format', '{{json .HostConfig.PortBindings}}', self.name))
            published = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', self.name))
            endpoint = published.get('5432/tcp')
            if (not endpoint or len(endpoint) != 1 or endpoint[0]['HostIp'] != '127.0.0.1'
                    or bindings['5432/tcp'][0]['HostIp'] != '127.0.0.1'):
                raise RecoveryDenied('LOOPBACK_PUBLICATION_REQUIRED')
            self.port = int(endpoint[0]['HostPort'])
            self.runtime_passwords = {r: secrets.token_urlsafe(24) for r in
                ['ra4a_test_a_app', 'ra4a_test_b_app', 'ra4a_test_a_worker', 'ra4a_test_b_worker', 'ra4a_test_unassigned']}
            self.write_state()
            deadline = time.monotonic() + 60
            while True:
                try:
                    with self.connect() as c:
                        row = c.execute("SELECT current_database(),current_setting('server_version_num')::int").fetchone()
                    if row[0] != DB or not 160000 <= row[1] < 170000:
                        raise RecoveryDenied('PG16_DATABASE_REQUIRED')
                    break
                except psycopg.OperationalError:
                    if time.monotonic() >= deadline:
                        raise RecoveryDenied('PG16_READINESS_DEADLINE') from None
                    time.sleep(.25)
            try:
                with self.connect(password=secrets.token_urlsafe(24)):
                    raise RecoveryDenied('WRONG_PASSWORD_ACCEPTED')
            except psycopg.OperationalError as exc:
                if exc.sqlstate not in (None, '28P01') or 'password authentication failed' not in str(exc):
                    raise RecoveryDenied('AUTHENTICATION_DENIAL_UNPROVEN') from None
            addresses = set(socket.gethostbyname_ex(socket.gethostname())[2]) - {'127.0.0.1'}
            if os.name == 'nt':
                p = subprocess.run(['powershell', '-NoProfile', '-Command',
                    "Get-NetIPAddress -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress | ConvertTo-Json -Compress"], capture_output=True, timeout=30)
                if p.returncode:
                    raise RecoveryDenied('HOST_INTERFACES_UNPROVEN')
                values = json.loads(p.stdout.decode())
                addresses.update([values] if isinstance(values, str) else values)
            results = []
            for host in sorted(addresses - {'127.0.0.1', '0.0.0.0'}):
                with socket.socket() as probe:
                    probe.settimeout(.3)
                    code = probe.connect_ex((host, self.port))
                if code == 0:
                    raise RecoveryDenied('NON_LOOPBACK_EXPOSURE')
                results.append({'address_sha256': digest(host.encode()), 'connect_ex': code})
            self.proof.joinpath('transport.json').write_bytes(encode({'authenticated_host_pg16': row,
                'binding': bindings, 'published': published, 'wrong_password_denied': True,
                'non_loopback_probes': results, 'kernel_egress_isolation': False}))
        except BaseException:
            self.stop()
            raise
        finally:
            cfg.unlink(missing_ok=True)

    def connect(self, role='postgres', *, dbname=DB, password=None, application_name='ra4e-b7p0'):
        return psycopg.connect(host='127.0.0.1', port=self.port, dbname=dbname, user=role,
            password=password if password is not None else (self.admin_password if role == 'postgres' else self.runtime_passwords[role]),
            autocommit=True, connect_timeout=3, application_name=application_name)

    def database(self, name, *, create=False, template='template0', drop=False):
        if not re.fullmatch(r'vrae_p2b1_[0-9a-f]{12}', name):
            raise RecoveryDenied('RESTORE_DATABASE_NAME_DENIED')
        with self.connect(dbname='postgres') as c:
            if create:
                c.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(name), sql.Identifier(template)))
                with self.connect(dbname=name) as target:
                    target.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
                    target.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO ra4a_app,ra4a_worker,p2a_fixture_writer,p2b1_review').format(sql.Identifier(name)))
            elif drop:
                c.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(name)))

    def stop(self):
        rows = []
        for kind, name in self.resources:
            before = self.owned(kind, name)
            if before:
                docker(*(['rm', '-f', name] if kind == 'container' else [kind, 'rm', name]))
            rows.append({'kind': kind, 'name': name, 'present_before': before, 'absent_after': not self.owned(kind, name)})
        closed = True
        if self.port:
            with socket.socket() as probe:
                probe.settimeout(1)
                closed = probe.connect_ex(('127.0.0.1', self.port)) != 0
        self.proof.joinpath('cleanup.json').write_bytes(encode({'owned_only': True, 'resources': rows, 'closed_port': closed}))
        if not closed or not all(r['absent_after'] for r in rows):
            raise RecoveryDenied('OWNED_CLEANUP_FAILED')
        self.state.unlink(missing_ok=True)
