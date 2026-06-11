"""Client registry: resolve a WhatsApp phone number to a client (FR-CFG-01).

Unknown numbers still resolve (the phone becomes the client id and name) so a
request is created and can be flagged ``unknown_client`` (FR-ING-08).
"""

from __future__ import annotations

from wapp_planner.domain.models import Client


class ClientRegistry:
    """Maps phone numbers and ids to known clients."""

    def __init__(self, clients: list[Client]) -> None:
        self._by_phone: dict[str, Client] = {}
        self._by_id: dict[str, Client] = {}
        for client in clients:
            self._by_id[client.id] = client
            for phone in client.phone_numbers:
                self._by_phone[phone] = client

    def resolve(self, phone: str) -> tuple[str, str, bool]:
        """Return ``(client_id, client_name, known)`` for a sender phone number."""
        client = self._by_phone.get(phone)
        if client is not None:
            return client.id, client.name, True
        return phone, phone, False

    def name_for(self, client_id: str) -> str:
        """Return the display name for a client id (the id itself if unknown)."""
        client = self._by_id.get(client_id)
        return client.name if client is not None else client_id
