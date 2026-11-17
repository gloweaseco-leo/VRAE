"""Safe classification of ONLY the public, pre-application M1 image build.

No raw log, runtime private data, retry, image/pin change or assertion override.
The original failed job remains failed. UNKNOWN is an actual diagnostic result.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
FILES = {'Dockerfile': 'integration/ra4b/Dockerfile',
         **{p: p for p in ('requirements-ra1a.lock', 'requirements-ra4a.lock', 'requirements-ra4b-p1.lock')}}
KINDS = {'REGISTRY_AUTH_DENIED': r'\b(?:401 Unauthorized|403 Forbidden|unauthorized:|denied:)',
         'REGISTRY_RATE_LIMIT': r'too many requests|toomanyrequests|\b429\b',
         'REGISTRY_SERVER_ERROR': r'\b50[0234]\b|service unavailable|bad gateway',
         'DNS_OR_CONNECTION': r'no such host|connection refused|network is unreachable|could not resolve',
         'TLS_ERROR': r'certificate verify failed|x509:|TLS handshake',
         'TIMEOUT': r'i/o timeout|context deadline exceeded|timed out',
         'MANIFEST_NOT_FOUND': r'manifest unknown|manifest not found',
         'DISK_SPACE': r'no space left on device'}


def diagnose(slug, outcome, root=ROOT):
    if slug not in ('311', '313') or outcome not in ('success', 'failure', 'skipped', 'cancelled'):
        raise ValueError('INVALID_DIAGNOSTIC_SCOPE')
    result = {'diagnostic_only': True, 'original_build_outcome': outcome,
              'private_runtime_logs_published': False, 'raw_build_log_published': False,
              'error_kinds': ['UNKNOWN'], 'context_verified': False}
    if outcome != 'failure':
        result['error_kinds'] = ['BUILD_NOT_FAILED_NO_RUNTIME_DIAGNOSIS']
        return result
    context = root/'docs/03-engineering/ra4b-p1/.runtime'/('m1-build-'+slug)/'build'
    if (not context.is_dir() or {p.name for p in context.iterdir()} != set(FILES)
            or any((context/name).is_symlink() or (context/name).read_bytes() != (root/original).read_bytes()
                   for name, original in FILES.items())):
        return result  # Do not inspect logs from an unverified/private context.
    result['context_verified'] = True
    result['context_sha256'] = {name: hashlib.sha256((context/name).read_bytes()).hexdigest() for name in FILES}
    folder = root/'docs/03-engineering/ra4b-p1/.runtime/owner-review'/('m1-build-'+slug)
    parts = []
    for name in ('build.stdout.log', 'build.stderr.log'):
        path = folder/name
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 2_000_000:
            return result
        raw = path.read_bytes()
        result[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        parts.append(raw.decode('utf-8', errors='replace'))
    text = '\n'.join(parts)
    result['error_kinds'] = [key for key, pattern in KINDS.items() if re.search(pattern, text, re.I)] or ['UNKNOWN']
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('slug', choices=('311', '313'))
    parser.add_argument('outcome', choices=('success', 'failure', 'skipped', 'cancelled'))
    args = parser.parse_args()
    result = diagnose(args.slug, args.outcome)
    public = ROOT/'docs/03-engineering/ra4b-p2/.runtime'/('public-ci-'+args.slug)
    public.mkdir(parents=True, exist_ok=True)
    (public/'public-image-build-diagnostic.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
