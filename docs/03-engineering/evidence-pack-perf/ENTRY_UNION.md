# All original ENTRY files: HEAD/worktree union

Authority: [Owner final remaining safety correction](https://github.com/gloweaseco-leo/VRAE/pull/114#issuecomment-6921662144),
following [the earlier exact authorization](https://github.com/gloweaseco-leo/VRAE/pull/114#issuecomment-6920780725).
The prior 9ab0535 36/36 and performance evidence remain historical, not acceptance
of this correction. No performance or L2 implementation is repeated.

The only implementation delta from 9ab0535 is one line in publication.py:

```python
changed += git("diff", "--name-only", ENTRY, "HEAD").splitlines()
```

The existing worktree-versus-ENTRY list and this HEAD-versus-ENTRY list pass
through the existing set intersection with original ENTRY paths. Thus the
original-file change set is their union, regardless of restoration to original
bytes in the index or worktree. The existing rejection and audit logic consume
that same set. No allowed path or blob is added. Original ENTRY, five document
pins, nine protected runtime/identity/SQL paths, the exact pack blob and its
clean-worktree checks all remain intact.

Four added cases extend the same isolated actual-Git fixture: identity and SQL
paths, each with unstaged and staged restoration. Each commits unauthorized
bytes, restores the exact temporary ENTRY bytes, proves worktree diff omits the
path while HEAD diff contains it, then requires ACCEPTED_SOURCE_CHANGED. Before
the one-line correction all four deterministically failed DID NOT RAISE; native
RED JUnit is retained privately with its hash in entry-union-local.json.

The local dual-minor scope is the complete 35-case freeze suite plus six
unchanged original freeze cases. Accepted performance/instance evidence is
reused; pack.py stays blob 8d45d5882103323e62bc4bd61a4379899e759966. The unchanged
17-workflow/36-job natural CI must execute once on the actual new source HEAD,
including B5A PG/security/HTTP/browser/publication. Earlier green HEADs cannot
substitute for that run. All old RED and raw JUnit hashes remain preserved.

No Worker/PG/SQL/identity/Guard/lease/timeout or other core change belongs to this
increment. PR114 remains Draft for Owner independent verification and merge.
C3 must wait for that merge and normal main sync before formal real P40 work;
no unmerged source is copied and no live COMMIT is claimed here.
