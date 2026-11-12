# Separate control preparation exception

The first, uncommitted `prepare_controls.py` attempt was rejected by the accepted
RA3B guard with `GuardError: INPUT_INTEGRITY` when constructing the fully supported
duplicate-target control. RA0 AIInterpretation requires unique strings per prose
array; repeating the same candidate whitelist proposal for two different facts
inside one interpretation violated that contract. This was a QA control-authoring
error, not a production defect and not a failure of a frozen case.

The exact prior generator is preserved as `prepare_controls.v0.py`. No control
fixture had been written and no candidate report call had occurred. The corrected
separate control uses one independently validated/pinned GuardResult bundle per
genuine original fact, keeping each interpretation's text unique. Its second fact
comes from the original duplicate_contact catalog, not an invented citation.

`control-pins.json` is a new Owner-authorized positive/negative control sidecar.
It does not overwrite the frozen 14 scenarios, original guard references or any
of the original 64 assertions. Each original frozen input is still sent unchanged
by the native suite adapter. The separate supported-vocabulary requests are not
counted as passes of those original nodes.
