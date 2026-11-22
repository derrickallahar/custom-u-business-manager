"""Custom U's current bank instructions, shared by print views and email PDFs.

Display-only information supplied by the business owner. Rendering must not
change saved quote/invoice snapshots or previously retained email attachments.
"""
from html import escape

HEADING = 'Bank payment information'
BANK_DETAILS = (
    ('Bank', 'Scotiabank'),
    ('Account name', 'Custom U'),
    ('Account type', 'Checking'),
    ('Transit', '50385 (Bay St. East Branch)'),
    ('Account number', '3337316'),
)

PAYMENT_STYLE = '''
.payment-summary{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:26px;align-items:start;margin-top:20px;break-inside:avoid}
.bank-payment{border-left:3px solid #b72030;background:#f7f8fa;padding:14px 16px;font-size:12px;line-height:1.6;overflow-wrap:anywhere;break-inside:avoid}
.bank-payment .label{color:#b72030;margin-bottom:8px}.bank-payment p{margin:9px 0 0;font-size:11px;line-height:1.4}
.payment-summary .totals{width:100%;margin:0}.payment-summary>div{min-width:0}
@media(max-width:650px){.payment-summary{grid-template-columns:1fr}}
@media print{.payment-summary{grid-template-columns:minmax(0,1fr) 270px;gap:20px;margin-top:14px}.bank-payment{padding:10px 12px;font-size:11px}.bank-payment p{font-size:10px}}
'''


def payment_reference(number):
    return 'Please use '+str(number)+' as your payment reference.'


def html_payment_information(number):
    rows = ''.join('<div><strong>'+escape(label)+':</strong> '+escape(value)+'</div>'
                   for label, value in BANK_DETAILS)
    return ('<aside class="bank-payment" aria-label="'+HEADING+'">'
            '<div class="label">'+HEADING+'</div>'+rows+
            '<p>'+escape(payment_reference(number))+'</p></aside>')
