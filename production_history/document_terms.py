"""Default wording for NEW Custom U documents. Does not alter historical terms."""
PAYMENT_TERMS = (
    'Payment is due on the date shown. Approved credit accounts have 30-day terms unless otherwise agreed in writing. '
    'Overdue balances are subject to a late fee of 1.5% per month after the due date. '
    'Where a deposit is required, work begins only after the required deposit is received.'
)
QUOTE_TERMS = 'Subject to final artwork approval and availability. ' + PAYMENT_TERMS.replace(
    'Payment is due on the date shown.', 'Payment is due on the due date shown on your invoice.')
INVOICE_TERMS = PAYMENT_TERMS + ' Please reference your invoice number with payment.'

def update_profile(profile):
    """Explicit migration of document defaults; other profile values are preserved."""
    if not isinstance(profile, dict):
        raise ValueError('Business profile must be a JSON object')
    return {**profile, 'quote_terms': QUOTE_TERMS, 'invoice_terms': INVOICE_TERMS}

def terms_for_document(kind, existing=None):
    """Preserve saved terms, including an intentional blank, on existing documents."""
    if kind not in ('quote','invoice'):
        raise ValueError('Unsupported document type')
    if existing is not None:
        if not isinstance(existing,dict) or 'terms_text' not in existing:
            raise ValueError('Existing document must supply its saved terms_text')
        return existing['terms_text']
    return QUOTE_TERMS if kind=='quote' else INVOICE_TERMS
