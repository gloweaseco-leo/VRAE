# Development history retained separately from final acceptance

No accepted P1/P2A SQL, frozen native reviewing/reporting/Guard/evidence or old QA
oracle was changed. These are new P2B1 implementation/harness iterations.

| Evidence directory | Actual observation | Resolution / interpretation |
| --- | --- | --- |
| `dev-migration-01` | Fresh v1→v2→v3 migration exited 0 | SQL compilation alone did not prove executable transaction correctness. |
| `dev-b01-01` | 1 call FAIL; SQLSTATE 42702, PL/pgSQL `x` ambiguous in `validate_command` | Rename the new SQL table aliases; dispose cluster and rerun fresh migrations. No accepted SQL change. |
| `dev-full-02` | CLI failed before command-record initialization: `ModuleNotFoundError: No module named 'integration'` | Add repository root to the new runner's Python import path. This setup failure has no committed raw stderr file; original tool transcript recorded the traceback. No test PASS is claimed. |
| `dev-full-03` | Accepted prelude stopped at Ruff E701 in the new pure test file | Format only the new test source; original failure stdout/stderr and stage records retained. No database/business PASS is claimed for this run. |
| `dev-full-04` | P1 v1 54, v2 54, pure 35 and P2A 86 passed; new P2B1 first 3 passed, next 1 failed | The new test incorrectly equated zero findings with zero Claims. Native 200 has scope/limitation literal Claims. Preserve those Claims/acknowledgments and assert zero issue count/native fields instead. This was an unfrozen engineering test assumption, not a production source change. |
| `dev-p2b1-05` | 98/98 new calls passed: 95 live DB cases plus 3 pure production-denial checks | Development partial phase only. Actual dump/restore/restart/races/kill/retry passed; original JUnit, calls and snapshots retained. This is not called 98 independent live-PG cases. |
| `dev-strengthened-06` | 7/7 selected calls passed, 91 deselected | Strengthen B01 exact one-finding assertion, B24 all three checks now also exercise SQL/native refusal and empty ledgers, B26 require the deferred commit error context. Partial check only, no final full-suite claim. |

`FROZEN_MATRIX.json` and its exact executed source snapshot are retained as V1.
`FROZEN_MATRIX_V2.json`, `MATRIX_V1_TO_V2.diff` and `MATRIX_VERSION_CHAIN.json`
record the same 98 node IDs with additional assertions. No oracle was removed,
skipped or xfailed. All 98 V2 cases use actual isolated PostgreSQL databases.
The shared collection stdout filename was regenerated for V2; it is not claimed
as original V1 raw collection output. Complete V1 executed source/JUnit remain.

Development `dev-full-04` source files were edited during the accepted prelude;
its early source manifest is a development snapshot, not the final freeze.
Only final fresh full runs whose complete runtime manifest matches committed
`SOURCE_SCOPE.json` count toward final acceptance. Final runs use no `-k` filter.

Raw evidence retains original Windows CRLF bytes via the new local `.gitattributes`.
Whole-evidence `git diff --check` therefore reports CR whitespace in raw files;
the scoped production/integration/test/infra/SQL/workflow whitespace check passes.
Raw bytes were not rewritten to suppress these diagnostics.

Final dual-Python results, verified cleanup and six hosted CI gates are separate
from this development log. CI/source/identity/approval boundaries are never
inferred from the number of tests or a migration-only success.
