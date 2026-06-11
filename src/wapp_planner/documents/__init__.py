"""Document generation and rendering (FR-GEN-*, FR-RND-*)."""

from wapp_planner.documents.branding import Branding
from wapp_planner.documents.content import (
    ExecutionPlanContent,
    LineItem,
    Phase,
    QuoteContent,
)
from wapp_planner.documents.generator import (
    GeneratedDocument,
    GenerationError,
    Generator,
)
from wapp_planner.documents.layout import build_blocks
from wapp_planner.documents.renderer import (
    DOCX_MIME,
    PDF_MIME,
    render_document,
    render_docx,
    render_pdf,
)

__all__ = [
    "Branding",
    "ExecutionPlanContent",
    "LineItem",
    "Phase",
    "QuoteContent",
    "GeneratedDocument",
    "GenerationError",
    "Generator",
    "build_blocks",
    "DOCX_MIME",
    "PDF_MIME",
    "render_docx",
    "render_document",
    "render_pdf",
]
