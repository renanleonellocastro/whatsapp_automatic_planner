"""Request repository (NFR-DURAB-01).

Persists a request's state, its messages, its document revisions, and the owner
interactions applied to it. ``record_interaction`` doubles as the idempotency
guard for owner responses (NFR-IDEMP-01): it returns ``False`` for a duplicate.

The in-memory implementation is used in tests and the local harness; a SQL/Dynamo
implementation can be dropped in behind the same interface for production.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from wapp_planner.domain.models import DocumentRevision, Message, OwnerInteraction, Request


class RequestRepository(ABC):
    """Stores and retrieves requests and their associated records."""

    @abstractmethod
    def save_request(self, request: Request) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_request(self, request_id: str) -> Request | None:
        raise NotImplementedError

    @abstractmethod
    def set_messages(self, request_id: str, messages: list[Message]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_messages(self, request_id: str) -> list[Message]:
        raise NotImplementedError

    @abstractmethod
    def add_revision(self, revision: DocumentRevision) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_revisions(self, request_id: str) -> list[DocumentRevision]:
        raise NotImplementedError

    @abstractmethod
    def latest_revision(self, request_id: str) -> DocumentRevision | None:
        raise NotImplementedError

    @abstractmethod
    def record_interaction(self, interaction: OwnerInteraction) -> bool:
        """Record an owner interaction; return ``False`` if its id was already seen."""
        raise NotImplementedError


class InMemoryRequestRepository(RequestRepository):
    """Process-local repository backed by dicts."""

    def __init__(self) -> None:
        self._requests: dict[str, Request] = {}
        self._messages: dict[str, list[Message]] = {}
        self._revisions: dict[str, list[DocumentRevision]] = {}
        self._interactions: dict[str, OwnerInteraction] = {}

    def save_request(self, request: Request) -> None:
        self._requests[request.id] = request

    def get_request(self, request_id: str) -> Request | None:
        return self._requests.get(request_id)

    def set_messages(self, request_id: str, messages: list[Message]) -> None:
        self._messages[request_id] = list(messages)

    def get_messages(self, request_id: str) -> list[Message]:
        return list(self._messages.get(request_id, []))

    def add_revision(self, revision: DocumentRevision) -> None:
        self._revisions.setdefault(revision.request_id, []).append(revision)

    def get_revisions(self, request_id: str) -> list[DocumentRevision]:
        return list(self._revisions.get(request_id, []))

    def latest_revision(self, request_id: str) -> DocumentRevision | None:
        revisions = self._revisions.get(request_id)
        return revisions[-1] if revisions else None

    def record_interaction(self, interaction: OwnerInteraction) -> bool:
        if interaction.id in self._interactions:
            return False
        self._interactions[interaction.id] = interaction
        return True
