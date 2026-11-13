"""One Owner-approved ordinary-bridge trial; no HTTP or live data.

Secrets stay in ignored bootstrap state. HTTP profile has only restricted role.
"""
import hashlib
import json
import socket
import subprocess

from integration.ra4c3 import lab


def run(output, state, profile):
    output, state, profile = map(lab.bounded, (output, state, profile))
    output.mkdir(parents=True, exist_ok=False)
    events = []

    def capture(name, command):
        p = subprocess.run(command, capture_output=True, timeout=30)
        raw = p.stdout + p.stderr
        (output / (name + '.log')).write_bytes(raw)
        events.append({'name': name, 'returncode': p.returncode,
                       'sha256': hashlib.sha256(raw).hexdigest()})
        assert p.returncode == 0, name
        return p.stdout.decode('utf-8-sig').strip()

    passed = False
    try:
        lab.start(state, output / 'startup', option_a_local_trial=True)
        s = json.loads(state.read_text())
        name, port = s['container'], s['port']
        capture('engine', ['docker', 'version', '--format', '{{json .}}'])
        net = json.loads(capture('network', ['docker', 'network', 'inspect', s['network']]))[0]
        assert net['Internal'] is False and net['Labels'][lab.LABEL] == 'TEST_ONLY'
        binding = json.loads(capture('host-bindings', ['docker', 'inspect', '--format',
            '{{json .HostConfig.PortBindings}}', name]))
        effective = json.loads(capture('effective-ports', ['docker', 'inspect', '--format',
            '{{json .NetworkSettings.Ports}}', name]))
        # Docker retains the empty allocation request in HostConfig, while the
        # effective map must contain exactly the assigned loopback endpoint.
        assert binding == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': ''}]}
        assert effective == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(port)}]}
        assert capture('docker-port', ['docker', 'port', name, '5432/tcp']) == f'127.0.0.1:{port}'
        listeners = json.loads(capture('host-listeners', ['powershell', '-NoProfile', '-Command',
            f'ConvertTo-Json -InputObject @(Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction Stop | Select-Object LocalAddress,LocalPort,OwningProcess)']))
        assert listeners and all(r['LocalAddress'] == '127.0.0.1' and r['LocalPort'] == port for r in listeners)
        interfaces = json.loads(capture('host-interfaces', ['powershell', '-NoProfile', '-Command',
            'ConvertTo-Json -InputObject @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop | Select-Object IPAddress,InterfaceAlias)']))
        nonloop = sorted({r['IPAddress'] for r in interfaces if not r['IPAddress'].startswith('127.') and r['IPAddress'] != '0.0.0.0'})
        assert nonloop, 'NO_NONLOOPBACK_INTERFACE_PROOF'
        checks = []
        for address in nonloop:
            with socket.socket() as probe:
                probe.settimeout(1)
                code = probe.connect_ex((address, port))
            checks.append({'local_host_interface': address, 'port': port, 'connect_ex': code})
            assert code != 0, 'NONLOOPBACK_EXPOSURE'
        (output / 'nonloopback-denials.json').write_bytes(json.dumps(checks, indent=2).encode() + b'\n')
        import psycopg
        original, _ = lab.wire(state)
        with original.connect() as c:
            ready = c.execute("SELECT current_database(),current_setting('server_version_num')::int,session_user,inet_client_addr()::text").fetchone()
            assert ready[:3] == ('vrae_ra4a_p1', 160015, 'postgres') or (ready[0] == 'vrae_ra4a_p1' and 160000 <= ready[1] < 170000 and ready[2] == 'postgres')
        (output / 'host-authenticated-sql.json').write_bytes(json.dumps(ready).encode() + b'\n')
        try:
            psycopg.connect(host='127.0.0.1', port=port, dbname='vrae_ra4a_p1', user='postgres', password='deliberately-wrong-password', connect_timeout=3)
        except psycopg.OperationalError as exc:
            assert 'password authentication failed' in str(exc)
        else:
            raise AssertionError('WRONG_PASSWORD_ACCEPTED')
        db = lab.seed(state, profile)
        original, p2a = lab.wire(state)
        from vrae.persistence.private_postgres import TestOnlyPrivateBytes
        from vrae.persistence.private_bytes import locator
        graph = p2a.graph('404')
        roles = []
        for role in ('ra4a_test_a_app', 'ra4a_test_b_app', 'ra4a_test_unassigned'):
            with original.connect(role, dbname=db) as c:
                attrs = c.execute('SELECT session_user,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=session_user').fetchone()
                assert attrs[0] == role and not any(attrs[1:])
                tenants = c.execute('SELECT tenant_id FROM ra4a.tenants ORDER BY tenant_id').fetchall()
                expected = [('tenant-test',)] if role == 'ra4a_test_a_app' else [('tenant-beta',)] if role == 'ra4a_test_b_app' else []
                assert tenants == expected
                try:
                    c.execute('SELECT raw FROM ra4a_bytes.objects')
                except psycopg.Error as exc:
                    assert exc.sqlstate == '42501'
                else:
                    raise AssertionError('RAW_TABLE_PRIVILEGE_LEAK')
                api = TestOnlyPrivateBytes(c, mode='TEST_ONLY_PRIVATE_BYTES_PG16')
                if role == 'ra4a_test_a_app':
                    assert api.read(locator(graph), provenance=graph) == graph
                    g200 = p2a.graph('200')
                    assert api.read(locator(g200), provenance=g200) == g200
                else:
                    try:
                        api.read(locator(graph), provenance=graph)
                    except psycopg.Error as exc:
                        assert exc.sqlstate == '42501'
                    else:
                        raise AssertionError('CROSS_TENANT_OR_ASSIGNMENT_LEAK')
                roles.append({'role': role, 'privileged': False, 'visible_tenants': tenants,
                              'raw_table_select': 'DENY', 'graph_read': 'READ' if role == 'ra4a_test_a_app' else 'DENY'})
        (output / 'actual-restricted-roles.json').write_bytes(json.dumps(roles, indent=2).encode() + b'\n')
        passed = True
    finally:
        if not passed and state.exists():
            lab.stop(state, output / 'failure-cleanup')
        receipt = {'authority': 'Owner comment 6843166796', 'transport_role_gate_passed': passed,
                   'kernel_egress_denial': False, 'production_safe_claim': False,
                   'events': events, 'http_started': False, 'real_human_approvals': 0}
        (output / 'gate.json').write_bytes(json.dumps(receipt, indent=2).encode() + b'\n')
        print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True)
    p.add_argument('--state', required=True)
    p.add_argument('--profile', required=True)
    a = p.parse_args()
    run(a.output, a.state, a.profile)
