# Workflow test fixtures

These files contain deterministic, fictional data created only for automated
connector tests. They are not exports from Teamworks AMS and do not contain
credentials, real athlete information, tenant identifiers, or operational
Smartabase data.

Workflow tests pass these paths explicitly to
`load_example_event_workflow_input()`. The ignored `use_case_examples/`
directory remains reserved for local operational examples and must not be used
as a test dependency.
