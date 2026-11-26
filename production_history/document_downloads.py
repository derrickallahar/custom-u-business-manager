"""Authenticated document routes call this only after checking saved-record access."""
import re
from document_pdf import render_document

def pdf_response(app, kind, record, payment_summary=None):
    raw = render_document(kind, record, payment_summary)
    number = re.sub(r'[^A-Za-z0-9_.-]', '_', str(record['number']))[:80]
    name = f"CustomU_{kind.title()}_{number}_r{record['version']}.pdf"
    response = app.response_class(raw, mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename="{name}"'
    response.headers['Cache-Control'] = 'private, no-store'
    return response
