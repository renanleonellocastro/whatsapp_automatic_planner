"""Company branding for rendered documents — configurable placeholders (AD-10).

All fields default to blank placeholders so rendering works before assets are
supplied; the owner fills these via config (FR-RND-02).
"""

from __future__ import annotations

from pydantic import BaseModel


class Branding(BaseModel):
    """Branding/letterhead details applied to generated documents."""

    company_name: str = "[Company Name]"
    address: str | None = None
    contact: str | None = None
    quote_terms: str | None = None
