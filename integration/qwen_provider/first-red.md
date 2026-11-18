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
