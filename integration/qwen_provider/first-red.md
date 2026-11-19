First local verification (Python 3.13): 41 failed, 6 passed. The offline test
tripwire patched raw socket.connect and blocked Windows asyncio's own wakeup
socketpair before any provider dispatch. It now patches create_connection,
getaddrinfo, BaseEventLoop.sock_connect and subprocess creation. No external
DNS, real model call or secret was involved. This is a harness failure, not a
live provider result. Initial static checks also found type annotations and
three lint errors; corrected before CI. No CI run was rerun to hide this RED.

Second local run: 46 passed, one failed. The after-response expiry test advanced
its clock one checkpoint too early and therefore correctly refused before dispatch;
the fixture now advances at the fifth checkpoint (after receiving usage).

First demo attempt also found the original fixture's synchronous asyncio.run
cannot be nested in the demo's event loop. Context preparation was moved before
that loop; no provider was dispatched in that failed demo.

First natural CI at `47a1d93c9d45cb28be5c234234d2e4ba96f650e7`:
Qwen protocol job attempt 1 passed 307 tests on each Python (run 44380137810),
but the original full-tree domain ban caught network/process infrastructure
inside vrae (tests/test_domain.py:392), and both B5A jobs refused the six-line
gateway source change with ACCEPTED_SOURCE_CHANGED (run 44380137249).
Ordinary fix: moved native transport/process to infra/qwen_provider, restored
the original gateway bytes and reused its existing NO_MODEL replay/minimization
path before bounded native dispatch. No old verifier, freeze exception or test
was weakened. Original RED runs remain; new code gets a new natural CI run.

Local relocation verification: both Python versions passed all 64 provider
cases. The original full-tree test's default read_text hit Windows GBK decoding;
running that unchanged test with the repository's UTF8 source encoding
(`python -X utf8`) passed on both. The infra namespace also requires explicit
package bases when listed alongside vrae for mypy; only the new own workflow's
command was corrected. Old `mypy vrae` continues to pass unchanged.
