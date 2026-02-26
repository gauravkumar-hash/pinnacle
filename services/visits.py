from pydantic import BaseModel
from enum import Enum
from utils.integrations.sgimed import get_invoice_html, get_mc_html

class DocumentHtml(BaseModel):
    html: str

class VisitDocType(Enum):
    INVOICE = 'invoice'
    MC = 'mc'

def fetch_sgimed_visit_doc(doc: VisitDocType, html_or_id: str) -> DocumentHtml:
    # New implementation contains invoice_id in invoice_html field. If so, fetch html from SGiMed
    html = html_or_id
    if len(html) < 20:
        if doc == VisitDocType.INVOICE:
            html = get_invoice_html(html_or_id)
        elif doc == VisitDocType.MC:
            html = get_mc_html(html_or_id)

    return DocumentHtml(
        html=html
    )

def get_invoice_document_html(html_or_id: str) -> DocumentHtml:
    return fetch_sgimed_visit_doc(VisitDocType.INVOICE, html_or_id)

def get_mc_document_html(html_or_id: str) -> DocumentHtml:
    return fetch_sgimed_visit_doc(VisitDocType.MC, html_or_id)
