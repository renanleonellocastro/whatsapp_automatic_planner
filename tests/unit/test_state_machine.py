"""Unit tests for the request state machine.

Covers REQUIREMENTS TST-04 (no illegal transition is ever allowed; every
terminal state is reachable) and the FR-CNF/FR-DLV transition semantics.
"""

from __future__ import annotations

import itertools

import pytest

from wapp_planner.workflow import (
    TERMINAL_STATES,
    IllegalTransitionError,
    RequestState,
    Trigger,
    is_terminal,
    next_state,
)
from wapp_planner.workflow.state_machine import TRANSITIONS


@pytest.mark.parametrize(("state", "trigger"), list(TRANSITIONS.keys()))
def test_every_declared_edge_is_traversable(state: RequestState, trigger: Trigger) -> None:
    """Each declared edge returns its mapped successor."""
    assert next_state(state, trigger) is TRANSITIONS[(state, trigger)]


def test_happy_path_quote_to_completed() -> None:
    """The canonical end-to-end path reaches COMPLETED (FR-DLV-03)."""
    state = RequestState.RECEIVED
    for trigger in (
        Trigger.START_AGGREGATION,
        Trigger.WINDOW_CLOSED,
        Trigger.MEDIA_PROCESSED,
        Trigger.CLASSIFIED_ACTIONABLE,
        Trigger.OWNER_CONFIRMED,
        Trigger.GENERATED,
        Trigger.RENDERED,
        Trigger.OWNER_APPROVED,
    ):
        state = next_state(state, trigger)
    assert state is RequestState.COMPLETED


def test_revision_loops_back_to_generating() -> None:
    """A revision request re-enters GENERATING (FR-DLV-04)."""
    assert (
        next_state(RequestState.AWAITING_APPROVAL, Trigger.OWNER_REQUESTED_REVISION)
        is RequestState.GENERATING
    )


def test_correction_is_a_self_loop() -> None:
    """Correcting the intent re-notifies but stays awaiting confirmation (FR-CNF-04)."""
    assert (
        next_state(RequestState.AWAITING_CLASSIFICATION, Trigger.OWNER_CORRECTED)
        is RequestState.AWAITING_CLASSIFICATION
    )


def test_classified_none_is_discarded() -> None:
    """NONE classification discards without owner involvement (FR-CLS-03)."""
    assert (
        next_state(RequestState.CLASSIFYING, Trigger.CLASSIFIED_NONE) is RequestState.DISCARDED
    )


@pytest.mark.parametrize("state", [s for s in RequestState if s not in TERMINAL_STATES])
def test_fail_reachable_from_every_non_terminal_state(state: RequestState) -> None:
    """FAIL lands on FAILED from any non-terminal state (NFR-OBS-02)."""
    assert next_state(state, Trigger.FAIL) is RequestState.FAILED


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
@pytest.mark.parametrize("trigger", list(Trigger))
def test_terminal_states_reject_all_triggers(state: RequestState, trigger: Trigger) -> None:
    """No edge leaves a terminal state (TST-04)."""
    assert is_terminal(state)
    with pytest.raises(IllegalTransitionError):
        next_state(state, trigger)


def test_illegal_transition_carries_context() -> None:
    """The exception exposes the offending state/trigger and a readable message."""
    with pytest.raises(IllegalTransitionError) as exc:
        next_state(RequestState.RECEIVED, Trigger.OWNER_APPROVED)
    assert exc.value.state is RequestState.RECEIVED
    assert exc.value.trigger is Trigger.OWNER_APPROVED
    assert "received" in str(exc.value)
    assert "owner_approved" in str(exc.value)


@pytest.mark.parametrize("state", list(RequestState))
def test_is_terminal_matches_terminal_set(state: RequestState) -> None:
    assert is_terminal(state) == (state in TERMINAL_STATES)


def test_every_terminal_state_is_reachable() -> None:
    """Each terminal state is the target of at least one edge (TST-04)."""
    reachable = set(TRANSITIONS.values())
    assert TERMINAL_STATES <= reachable


def test_no_undeclared_edge_is_accepted() -> None:
    """Exhaustively: any (state, trigger) not in the table is rejected."""
    for state, trigger in itertools.product(RequestState, Trigger):
        if (state, trigger) in TRANSITIONS:
            assert next_state(state, trigger) is TRANSITIONS[(state, trigger)]
        else:
            with pytest.raises(IllegalTransitionError):
                next_state(state, trigger)


def test_transition_table_is_read_only() -> None:
    """The exported table cannot be mutated by callers."""
    with pytest.raises(TypeError):
        TRANSITIONS[(RequestState.RECEIVED, Trigger.FAIL)] = RequestState.COMPLETED  # type: ignore[index]
