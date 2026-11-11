# RA-1B B0: minimal containment topology

Baseline: main 8bc460764dedb6a87c2e7806b2d3b382875596de; Issue #5.
This design is frozen for the synthetic experiment; acceptance is separate.

Python controller and resource broker run in a trusted Worker container. Chromium
runs as a different non-root user in a separate container, filesystem and network
namespace. Neither receives production secrets. A per-task Unix control socket
relays Chrome DevTools Protocol (CDP) to Chromium's debugging pipe; no listening
TCP CDP port, Docker socket or host directory is mounted in either workload.
The only shared volume is disposable control IPC, not evidence or credentials.

Browser network: network none, IPv4/IPv6 default DROP, no DNS/UDP exception.
Resource requests are paused by CDP Fetch and fulfilled with bounded bytes by
the trusted Broker using RA-1A SourceAccess, Budget, SafeFetcher and robots.
There is no transparent CONNECT tunnel and no browser-side HTTP client fallback.
Browser routing is auxiliary; direct network attempts must fail in the kernel.
CDP messages and DOM output are untrusted, size-limited and correlated to the
active target/request; they cannot broaden task policy or arbitrary controller commands.

Worker resource namespace permits only explicitly configured synthetic fixture
DNS and web endpoints. The fixture and bait services log actual methods and writes.
They are local test services, never real public destinations. All processes belong
to disposable containers with memory/CPU/PID/tmpfs/time limits and external teardown.
Startup root may configure namespace rules, then drops capabilities and UID;
Chromium itself must retain its user-namespace and seccomp sandbox. No no-sandbox,
privileged container, host networking, host IPC, or seccomp-unconfined fallback.

First hard gate: prove sandbox availability in this actual kernel/container runtime.
If unavailable, stop affected browser work and report SECURITY_BLOCKED with the
actual failure; mocks cannot satisfy B1/B4. Do not introduce an insecure fallback.

L0 is denied browser execution; L1 permits at most three explicitly approved URLs,
each in fixed desktop/mobile viewports and fresh task profile. Default-deny methods,
resource types, navigation, external origins, WebSocket, service workers, download,
popup, upload and WebRTC. Missing/blocked resources prevent a complete observation.
Private DOM/screenshot evidence must bind tenant/run/policy/version/URL/time/viewport/
renderer/resources and hashes; it never implies a Finding or business event.

References: Chromium Linux sandbox documentation and Playwright's Docker guidance
require non-root Chromium and available user namespaces. A narrowly reviewed
seccomp syscall permission for namespace creation may be needed; this is distinct
from disabling Chromium's own sandbox or the container seccomp filter.
