"""Fan an owner-facing message out to the configured channel(s) (AD-3).

A :class:`ChannelDispatcher` holds one notifier + recipient per concrete channel
and sends to every concrete channel the configured (possibly ``BOTH``) channel
includes, building the right ``OutboundMessage`` recipient for each.
"""

from __future__ import annotations

from dataclasses import dataclass

from wapp_planner.domain.enums import Channel
from wapp_planner.providers.base import Attachment, Notifier, OutboundMessage

#: Concrete channels, in deterministic send order.
_CONCRETE_CHANNELS: tuple[Channel, ...] = (Channel.EMAIL, Channel.WHATSAPP)


class MissingNotifierError(Exception):
    """Raised when a configured channel has no registered notifier."""


@dataclass(frozen=True)
class ChannelTarget:
    """A notifier paired with the owner's address on that channel."""

    notifier: Notifier
    recipient: str


class ChannelDispatcher:
    """Sends a message to each concrete channel a configured channel includes."""

    def __init__(self, targets: dict[Channel, ChannelTarget]) -> None:
        self._targets = targets

    def send(
        self,
        channel: Channel,
        *,
        body: str,
        subject: str | None = None,
        attachments: list[Attachment] | None = None,
    ) -> dict[Channel, str]:
        """Dispatch to every concrete channel in ``channel``; return per-channel ids."""
        results: dict[Channel, str] = {}
        for concrete in _CONCRETE_CHANNELS:
            if not channel.includes(concrete):
                continue
            target = self._targets.get(concrete)
            if target is None:
                raise MissingNotifierError(f"no notifier registered for {concrete.value!r}")
            message = OutboundMessage(
                recipient=target.recipient,
                subject=subject,
                body=body,
                attachments=attachments or [],
            )
            results[concrete] = target.notifier.send(message)
        return results
