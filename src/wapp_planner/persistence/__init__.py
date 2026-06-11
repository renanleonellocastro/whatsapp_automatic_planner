"""Persistence: request/message/revision/interaction repository (NFR-DURAB-01)."""

from wapp_planner.persistence.repository import InMemoryRequestRepository, RequestRepository

__all__ = ["InMemoryRequestRepository", "RequestRepository"]
