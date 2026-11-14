"""Non-test persistence probe. Its XML is deliberately NOT a JUnit report."""
import hashlib
import json
import os
from pathlib import Path
import zlib

MARKER = (b'<?xml version="1.0"?><ra4b-output-preflight kind="SYNTHETIC_NOT_PYTEST">'
          + b'<marker>owned-native-output-0123456789</marker>' * 1024 + b'</ra4b-output-preflight>')


def main():
    out = Path('/evidence')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    assert int(status['CapEff'].strip(), 16) == 0 and status['NoNewPrivs'].strip() == '1'
    assert os.getuid() == os.getgid() == 0 and set(os.getgroups()) == {0, 1001}
    assert sorted(p.name for p in Path('/sys/class/net').iterdir()) == ['lo']
    assert len(Path('/proc/net/route').read_text().strip().splitlines()) == 1
    assert not Path('/var/run/docker.sock').exists()
    info = out.stat()
    assert (info.st_uid, info.st_gid, info.st_mode & 0o777) == (1001, 1001, 0o770)
    target = out / 'synthetic-marker.xml'
    with target.open('xb') as stream:
        assert stream.write(MARKER) == len(MARKER)
        stream.flush()
        os.fsync(stream.fileno())
    assert target.read_bytes() == MARKER
    file_info = target.stat()
    record = {'status': 'SYNTHETIC_MARKER_WRITTEN_NOT_PYTEST', 'uid': os.getuid(), 'gid': os.getgid(),
        'groups': os.getgroups(), 'directory_uid': info.st_uid, 'directory_gid': info.st_gid,
        'directory_mode': oct(info.st_mode & 0o777), 'file_uid': file_info.st_uid, 'file_gid': file_info.st_gid,
        'file_mode': oct(file_info.st_mode & 0o777), 'effective_capabilities_zero': True,
        'no_new_privileges': True, 'network_only_loopback': True, 'extra_routes': 0,
        'bytes': len(MARKER), 'sha256': hashlib.sha256(MARKER).hexdigest(),
        'crc32': format(zlib.crc32(MARKER) & 0xffffffff, '08x'), 'bytes_bounded_below': 65536,
        'fsync_completed': True, 'pytest_invocations': 0}
    assert len(MARKER) < 65536
    (out / 'synthetic-marker-proof.json').write_text(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
