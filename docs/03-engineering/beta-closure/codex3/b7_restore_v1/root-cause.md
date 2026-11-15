# Confirmed first hosted RED root cause

Owner: https://github.com/gloweaseco-leo/VRAE/pull/102#issuecomment-6893257876

Both focused native causal pairs used source e039918d2221401f7acba731155a8a5b9cf240cc,
with the unmodified first-RED C3 observer SHA256
138f0206bf67ab057bf8b645be4afb35294735f6ebcc04a204fdd23f0f501390.
The private reproduced stderr hashes exactly equal both original hosted hashes:

- 311: bf357c05cf11ca8da54866388252bc05e251c1def225fca90f89f95586ab9c76
- 313: 053eda5874346b8a4d2cc7e3c6fc2b3c8a18f24d8191e227c9473bed29ffd48c

This byte equality confirms PermissionError errno13 while opening
/evidence/worker-0.log inside accepted.spawn, before original Worker Popen.
The new fixture omitted accepted B4 output preparation: a Linux runner-owned
0755 bind directory is not writable by the root supervisor after CAP_DAC_OVERRIDE
has been dropped. A real Linux volume with UID/GID1001, mode0755 and a root
supervisor without that group reproduces the original failure exactly.
The failed attempt leaves the complete PG byte/catalog fingerprint unchanged.

In each pair, only the new output access configuration changed to mode0770 and
supplementary group1001, matching the accepted B4 test-output mechanism. The
same untouched database then completed through the original Worker, UID10002,
native exit0. No DAC capability, role/GRANT/RLS/SQL, worker code, lease/epoch/source
semantics, config0600 ownership or network route changed. Worker spawn still
clears supplementary groups. Catalog, B3 and sealed-byte state remained unchanged.
All owned PG/container/volume/loopback resources were destroyed.

The minimum implementation repair prepares only a fresh directory under this
package's .private root, checks current runner ownership and allowed GID, removes
other-user directory access and passes its group only to the supervisor.
The original accepted helper is not modified or given a fake evidence root.
A bounded output access probe exposes actual UID/GID/groups/mode on success.
A closed failure record exports only stage/exception enum, errno and native child
exit. Raw stderr, exception messages, credentials and DB rows stay private.

The original official hosted RED artifacts and four earlier local fixture REDs
remain intact. Historical replay loads only the old C3 observer from fa35b8f;
accepted Worker source is never overwritten. Old A1 remains PAUSED/MAX3 0/3,
zero new UUID ordering experiments. This proof is not B7-P1 or full B7 EXIT PASS.
The next gate is a normal accepted-main merge, new-source native validation and
one Owner-authorized new-head hosted CI, followed by independent review.
