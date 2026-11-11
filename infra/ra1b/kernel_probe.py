"""Direct syscall probe, independent of CDP/routes. No public target is contacted."""
import errno
import json
import os
from pathlib import Path
import socket
import sys

assert os.getuid() == 10001
assert set(os.listdir('/sys/class/net')) == {'lo'}
assert 'CapEff:\t0000000000000000' in Path('/proc/self/status').read_text()
control = '--control' in sys.argv
results = []
for family in (socket.AF_INET, socket.AF_INET6):
    for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
        try:
            probe = socket.socket(family, kind)
        except OSError as exc:
            results.append({'family': family, 'kind': kind, 'errno': exc.errno})
            assert not control and exc.errno == errno.EPERM
        else:
            probe.close()
            results.append({'family': family, 'kind': kind, 'created': True})
            assert control, 'SECURITY_NO_GO: direct network socket bypassed kernel policy'
print(json.dumps({'probe': 'direct-kernel-syscalls', 'positive_control': control,
                  'uid': os.getuid(), 'results': results}), flush=True)
if not control:
    try:
        Path('/opt/forbidden-write').write_bytes(b'probe')
    except OSError as exc:
        assert exc.errno in (errno.EROFS, errno.EACCES)
        print('ROOT_WRITE_DENIED errno=' + str(exc.errno), flush=True)
    else:
        raise AssertionError('SECURITY_NO_GO: writable root')
    written = 0
    try:
        with Path('/tmp/disk-limit-probe').open('wb', buffering=0) as stream:
            for _ in range(300):
                written += stream.write(b'x' * 1048576)
    except OSError as exc:
        assert exc.errno == errno.ENOSPC
        print(json.dumps({'tmpfs_limit_hit': True, 'written_bytes': written}), flush=True)
    else:
        raise AssertionError('SECURITY_NO_GO: tmpfs disk limit not enforced')
