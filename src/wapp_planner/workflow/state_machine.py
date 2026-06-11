"""Request lifecycle state machine (REQUIREMENTS §6, FR-CNF-04, FR-DLV-03/04).

The state machine is the heart of the system: it guarantees that a Request can
only ever move along an explicitly allowed edge. Any other transition is a bug
and raises :class:`IllegalTransitionError` rather than silently corrupting state.

The transition table is a pure mapping of ``(state, trigger) -> next_state``.
``FAIL`` is allowed from every non-terminal state and always lands on
``FAILED`` (REQUIREMENTS NFR-OBS-02).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

from wapp_planner.workflow.enums import RequestState, Trigger

#: States from which no further transition is allowed.
TERMINAL_STATES: Final[frozenset[RequestState]] = frozenset(
    {RequestState.COMPLETED, RequestState.DISCARDED, RequestState.FAILED}
)

# Explicit, exhaustive edge list. Read as: in <state>, the <trigger> event moves
# the request to <next_state>. Anything not listed here is illegal.
_EDGES: Final[dict[tuple[RequestState, Trigger], RequestState]] = {
    (RequestState.RECEIVED, Trigger.START_AGGREGATION): RequestState.AGGREGATING,
    (RequestState.AGGREGATING, Trigger.WINDOW_CLOSED): RequestState.PROCESSING_MEDIA,
    (RequestState.PROCESSING_MEDIA, Trigger.MEDIA_PROCESSED): RequestState.CLASSIFYING,
    (RequestState.CLASSIFYING, Trigger.CLASSIFIED_ACTIONABLE): RequestState.AWAITING_CLASSIFICATION,
    (RequestState.CLASSIFYING, Trigger.CLASSIFIED_NONE): RequestState.DISCARDED,
    # HITL #1 — classification confirmation (FR-CNF-02/04)
    (RequestState.AWAITING_CLASSIFICATION, Trigger.OWNER_CONFIRMED): RequestState.GENERATING,
    # Correction re-notifies the owner; the request stays awaiting confirmation.
    (RequestState.AWAITING_CLASSIFICATION, Trigger.OWNER_CORRECTED): (
        RequestState.AWAITING_CLASSIFICATION
    ),
    (RequestState.AWAITING_CLASSIFICATION, Trigger.OWNER_REJECTED): RequestState.DISCARDED,
    (RequestState.GENERATING, Trigger.GENERATED): RequestState.RENDERING,
    (RequestState.RENDERING, Trigger.RENDERED): RequestState.AWAITING_APPROVAL,
    # HITL #2 — document approval (FR-DLV-03/04)
    (RequestState.AWAITING_APPROVAL, Trigger.OWNER_APPROVED): RequestState.COMPLETED,
    (RequestState.AWAITING_APPROVAL, Trigger.OWNER_REQUESTED_REVISION): RequestState.GENERATING,
}

# FAIL is reachable from every non-terminal state (REQUIREMENTS NFR-OBS-02).
_EDGES.update(
    {
        (state, Trigger.FAIL): RequestState.FAILED
        for state in RequestState
        if state not in TERMINAL_STATES
    }
)

#: Read-only view of the full transition table.
TRANSITIONS: Final[MappingProxyType[tuple[RequestState, Trigger], RequestState]] = MappingProxyType(
    dict(_EDGES)
)


class IllegalTransitionError(RuntimeError):
    """Raised when a ``(state, trigger)`` pair is not an allowed edge."""

    def __init__(self, state: RequestState, trigger: Trigger) -> None:
        self.state = state
        self.trigger = trigger
        super().__init__(f"Illegal transition: {state.value} cannot handle {trigger.value!r}")


def is_terminal(state: RequestState) -> bool:
    """Return ``True`` if ``state`` is terminal (no outgoing transitions)."""

    return state in TERMINAL_STATES


def next_state(state: RequestState, trigger: Trigger) -> RequestState:
    """Return the state reached by applying ``trigger`` in ``state``.

    Raises :class:`IllegalTransitionError` if the edge is not allowed — this
    includes every trigger from a terminal state.
    """

    try:
        return TRANSITIONS[(state, trigger)]
    except KeyError:
        raise IllegalTransitionError(state, trigger) from None
