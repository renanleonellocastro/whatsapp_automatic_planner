"""WhatsApp Service Planner Automation.

Ingest WhatsApp job requests (text/audio/video/image), classify the intent
(quote vs execution plan), generate the document via an LLM, and deliver it
back to the owner with two human-in-the-loop approval gates.

See ``docs/REQUIREMENTS.md`` for the authoritative requirements.
"""

__version__ = "0.1.0"
