"""Human-in-the-loop: signed action links, owner notification & response (AD-8).

Implements the two approval gates (REQUIREMENTS FR-NOT-*, FR-CNF-*, FR-DLV-*):
notifications carry HMAC-signed, expiring action links; clicking one resolves to
a validated :class:`OwnerAction` the orchestrator applies to the state machine.
"""

from wapp_planner.hitl.dispatcher import ChannelDispatcher, ChannelTarget, MissingNotifierError
from wapp_planner.hitl.service import NotificationService, OwnerAction
from wapp_planner.hitl.tokens import (
    ActionToken,
    ExpiredTokenError,
    InvalidTokenError,
    TokenError,
    TokenSigner,
)

__all__ = [
    "ChannelDispatcher",
    "ChannelTarget",
    "MissingNotifierError",
    "NotificationService",
    "OwnerAction",
    "ActionToken",
    "ExpiredTokenError",
    "InvalidTokenError",
    "TokenError",
    "TokenSigner",
]
