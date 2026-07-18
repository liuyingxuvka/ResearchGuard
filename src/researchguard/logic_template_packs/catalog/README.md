# LogicGuard validated template-pack catalog

This catalog is an additive adapter over current LogicGuard semantic owners. It
does not replace the argument, structured-artifact, source-library, deepening,
synthesis, or execution-depth implementations.

`manifest.json` is the sole catalog inventory. Every profile and callable is
content-addressed. Loading fails closed on unknown fields, inventory drift,
stale content digests, missing or changed native owners, undeclared
composition, and ambiguous selection.

The base profile is available only when a request explicitly sets
`allow_base=True`. Multiple matching profiles require either one complete
declared dominator or pairwise symmetric, field-disjoint composition. Priority
order and filename order are never selection authority.
