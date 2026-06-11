# Traceability Matrix

Maps each requirement to the module that satisfies it and the test that proves
it (REQUIREMENTS §15). Updated as implementation proceeds; rows are added per
phase. `—` = not yet implemented.

| Requirement | Module | Test |
|-------------|--------|------|
| §6 state machine | `workflow/state_machine.py` | `tests/unit/test_state_machine.py` |
| FR-CLS-01 (intent vocabulary) | `workflow/enums.py::Intent` | `tests/unit/test_state_machine.py` |
| FR-CLS-03 (NONE → discard) | `state_machine` `CLASSIFIED_NONE` edge | `test_classified_none_is_discarded` |
| FR-CNF-04 (confirm/correct/reject) | `state_machine` AWAITING_CLASSIFICATION edges | `test_correction_is_a_self_loop`, happy/`OWNER_REJECTED` |
| FR-DLV-03 (approve → completed) | `state_machine` `OWNER_APPROVED` edge | `test_happy_path_quote_to_completed` |
| FR-DLV-04 (revision loop) | `state_machine` `OWNER_REQUESTED_REVISION` edge | `test_revision_loops_back_to_generating` |
| FR-ING-04 (message types) | `workflow/enums.py::MessageType` | covered via import/use |
| NFR-OBS-02 (fail → alertable terminal) | `state_machine` `FAIL` edges | `test_fail_reachable_from_every_non_terminal_state` |
| TST-04 (no illegal transition; terminals reachable) | `state_machine` | `test_no_undeclared_edge_is_accepted`, `test_every_terminal_state_is_reachable`, `test_terminal_states_reject_all_triggers` |
| TST-01 (100% coverage gate) | `pyproject.toml [tool.coverage]` | CI `pytest --cov` |
| _… remaining FR/NFR …_ | — | — |
