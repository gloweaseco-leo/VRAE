"""Three independently owned PG16 clusters; private credentials never leave fixture."""
from dataclasses import dataclass
import json
import secrets
import socket
import time
import uuid

import psycopg

from integration.ra4e.lab import Environment as AcceptedEnvironment
from integration.ra4e.lab import DB, IMAGE, RecoveryDenied, docker, encode, invoke
from .loopback import Loopback

LABEL = 'vrae.beta.b7restore.v1'


@dataclass
class Environment(AcceptedEnvironment):
    def __post_init__(self):
        if self.tag not in ('source', 'verification', 'target'):
            raise RecoveryDenied('STAGE_DENIED')
        self.name = 'vrae-b7rv1-' + uuid.uuid4().hex[:12] + '-' + self.tag
        self.resources = [('container', self.name), ('network', self.name + '-net'),
                          ('volume', self.name + '-data')]
        self.private.mkdir(parents=True, exist_ok=False)
        self.proof.mkdir(parents=True, exist_ok=False)
        self.state = self.private / 'state.json'
        self.state_path = self.state  # Original B3 bootstrap's explicit fixture interface.
        self.graphs = {}
        self.relay = None
        self.write_state()
        (self.proof / 'ownership.json').write_bytes(encode({
            'name': self.name, 'label': LABEL, 'resources': self.resources, 'image': IMAGE}))

    def owned(self, kind, name):
        if (kind, name) not in self.resources:
            raise RecoveryDenied('UNOWNED_RESOURCE_DENIED')
        template = '{{json .Config.Labels}}' if kind == 'container' else '{{json .Labels}}'
        p = invoke(kind, 'inspect', '--format', template, name)
        if p.returncode:
            error = p.stderr.decode(errors='replace').lower()
            if name.lower() not in error or not any(s in error for s in ('no such', 'not found')):
                raise RecoveryDenied('ABSENCE_UNPROVEN')
            return False
        if json.loads(p.stdout).get(LABEL) != self.name:
            raise RecoveryDenied('OWNERSHIP_DENIED')
        return True

    def start(self):
        for kind, name in self.resources:
            if self.owned(kind, name):
                raise RecoveryDenied('RESOURCE_ALREADY_PRESENT')
        cfg = self.private / 'postgres.env'
        cfg.write_text('POSTGRES_PASSWORD=' + self.admin_password + '\nPOSTGRES_DB=' + DB +
                       '\nPOSTGRES_INITDB_ARGS=--auth-host=scram-sha-256\n')
        try:
            docker('volume', 'create', '--label', LABEL + '=' + self.name, self.name + '-data')
            docker('run', '-d', '--name', self.name, '--network', 'none',
                   '--label', LABEL + '=' + self.name, '--env-file', str(cfg),
                   '--mount',
                   'type=volume,src=' + self.name + '-data,dst=/var/lib/postgresql/data',
                   '--memory', '512m', '--cpus', '1', '--pids-limit', '128', IMAGE)
            network_mode = docker('inspect', '--format', '{{.HostConfig.NetworkMode}}', self.name).decode().strip()
            assert network_mode == 'none'
            bindings = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', self.name))
            assert not bindings
            self.relay = Loopback(self.name)
            self.port = self.relay.port
            self.runtime_passwords = {r: secrets.token_urlsafe(32) for r in (
                'ra4a_test_a_app', 'ra4a_test_b_app', 'ra4a_test_a_worker',
                'ra4a_test_b_worker', 'ra4a_test_unassigned')}
            self.write_state()
            end = time.monotonic() + 60
            while True:
                try:
                    with self.connect() as c:
                        actual = c.execute("SELECT current_database(),current_setting('server_version_num')::int").fetchone()
                    assert actual[0] == DB and 160000 <= actual[1] < 170000
                    break
                except psycopg.OperationalError:
                    if time.monotonic() >= end:
                        raise RecoveryDenied('PG16_LOOPBACK_READINESS_FAILED') from None
                    time.sleep(.25)
            try:
                with self.connect(password=secrets.token_urlsafe(32)):
                    raise RecoveryDenied('BAD_PASSWORD_ACCEPTED')
            except psycopg.OperationalError as exc:
                assert 'password authentication failed' in str(exc)
            with self.connect() as c:
                cluster_id = str(c.execute('SELECT system_identifier FROM pg_control_system()').fetchone()[0])
            routes = docker('exec', self.name, 'cat', '/proc/net/route').decode()
            # An internal Docker network must provide no default IPv4 route.
            assert not any(line.split()[1] == '00000000' for line in routes.splitlines()[1:] if line.split())
            ips = set(socket.gethostbyname_ex(socket.gethostname())[2]) - {'127.0.0.1', '0.0.0.0'}
            probes = []
            for ip in sorted(ips):
                with socket.socket() as probe:
                    probe.settimeout(.3)
                    code = probe.connect_ex((ip, self.port))
                assert code != 0
                probes.append(code)
            (self.proof / 'transport.json').write_bytes(encode({
                'actual_pg16': actual, 'cluster_system_identifier': cluster_id, 'binding': '127.0.0.1', 'network_mode': network_mode,
                'host_transport': 'byte-only docker-exec busybox nc; original PG SCRAM auth',
                'no_default_route': True, 'wrong_password_denied': True,
                'non_loopback_connect_ex': probes}))
        finally:
            cfg.unlink(missing_ok=True)

    def initialize(self):
        from integration.ra4e.fixtures import wire
        from integration.ra4b import support as b4
        from integration.b3_p0.support import bootstrap
        with wire(self):
            b4.migrate()
            b4.seed()
        self.runtime_passwords = json.loads(self.state.read_bytes())['runtime_passwords']
        bootstrap(self)

    def config(self, kind='APP', suffix='a'):
        from integration.ra4e.fixtures import wire
        from integration.ra4b.support import config
        with wire(self):
            return config(kind, suffix)

    def empty_for_restore(self):
        # Initial accepted hooks established cluster roles. No seeded rows survive:
        # pg_restore --create alone will recreate the entire database from archive.
        with self.connect(dbname='postgres') as c:
            c.execute('DROP DATABASE vrae_ra4a_p1 WITH (FORCE)')
            assert c.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (DB,)).fetchone()[0] == 0

    def stop(self):
        if self.relay is not None:
            self.relay.close()
        super().stop()
