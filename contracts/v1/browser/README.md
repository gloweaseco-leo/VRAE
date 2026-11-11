# BrowserObservation v1

Private, additive observation bundle. Existing RA-0 and RA-1A schemas are unchanged.
The enclosing tenant/run/policy/version and renderer apply to every observation;
each observation binds its approved URL, fixed viewport, time, artifact hashes and
resource trace. BrowserBundle.verify checks structure, scope, artifact hashes,
unique URL/viewport pairs and successful-document prerequisites for OBSERVED.

UNKNOWN and ACCESS_BLOCKED may retain partial private artifacts. Neither is a
Finding. Hashes are not signatures or proof of remote truth. URLs, screenshots and
DOM can contain identifying data. No automatic upload or public sharing is provided.
See docs/03-engineering/RA1B_IMPLEMENTATION_AND_ACCEPTANCE.md for measured limits.
