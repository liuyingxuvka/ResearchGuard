# Diagram Semantics

LogicGuard diagrams begin with one question: what relationship must be made
inspectable?

AI should choose the clearest diagram or table after identifying that
relationship. Do not turn all of these into one generic flowchart. An arrow
may mean support, attack, qualification, production, containment, citation, or
execution order; the selected view must make that meaning explicit.

Useful choices include argument maps, why/proof trees, gap tables, research
processes, document-structure maps, source paths, synthesis routes, comparison
matrices, timelines, and workflow diagrams.

The source graph payload records `recommended_view`,
`recommended_diagram_kind`, and `recommendation_reason`. The project library
viewer renders the single recommended top-level graph. It does not expose graph-mode tabs.
