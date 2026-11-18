"""Independent disposable receiver process. Private key never enters the SSR."""
import json
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from vrae.reviewing.canonical import canonical


def main():
    key = Ed25519PrivateKey.generate()
    print(json.dumps({'public_key': key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()}), flush=True)
    for line in sys.stdin:
        doc = json.loads(line)
        if set(doc) != {'scope_sha256', 'brief_sha256', 'attempt', 'nonce', 'state'} or doc['state'] not in ('ACKNOWLEDGED', 'REJECTED', 'RETRYABLE_FAILED'):
            raise ValueError('bounded synthetic receipt required')
        print(json.dumps({'signature': key.sign(canonical(doc)).hex()}), flush=True)


if __name__ == '__main__':
    main()
