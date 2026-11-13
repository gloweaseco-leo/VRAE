"""Separate restricted-role HTTP process; never opens bootstrap state."""
import argparse
import json

from apps.operator_console.preview import serve
from integration.ra4c3.lab import bounded


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--audit', required=True)
    args = parser.parse_args()
    audit = bounded(args.audit)
    audit.parent.mkdir(parents=True, exist_ok=True)

    def sink(event):
        with audit.open('ab') as stream:
            stream.write(json.dumps(event).encode() + b'\n')

    # Transparent instrumentation of the actual accepted API, not a fake read.
    from vrae.persistence.private_postgres import TestOnlyPrivateBytes
    original_read = TestOnlyPrivateBytes.read

    def observed_read(self, *a, **kw):
        sink({'event': 'spy_actual_p2a_read_invoked'})
        value = original_read(self, *a, **kw)
        sink({'event': 'spy_actual_p2a_read_returned'})
        return value

    TestOnlyPrivateBytes.read = observed_read

    serve(test_only=True, synthetic_fixtures=True,
          pg_read_profile=str(bounded(args.profile)), audit_sink=sink)
