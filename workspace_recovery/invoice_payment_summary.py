"""Validate the current ledger view without altering the saved invoice snapshot."""
from datetime import date
import re

FIELDS={'invoice_id','invoice_version','ledger_version','total_cents','paid_cents','credit_cents','refund_cents','balance_cents','refund_due_cents','payments'}
MONTHS=('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')

def payment_view(record, summary):
    def invalid():raise ValueError('INVOICE_PAYMENT_SUMMARY_INVALID')
    if not isinstance(summary,dict) or set(summary)!=FIELDS:invalid()
    if summary['invoice_id']!=record['id'] or summary['invoice_version']!=record['version']:invalid()
    for key in FIELDS-{'invoice_id','payments'}:
        if type(summary[key]) is not int or not 0<=summary[key]<=10**14:invalid()
    total=record['quote_snapshot']['data']['total_cents']
    paid=summary['paid_cents'];credit=summary['credit_cents'];refund=summary['refund_cents']
    if summary['total_cents']!=total or credit>total or refund>min(paid,credit):invalid()
    if summary['balance_cents']!=max(total-credit-paid+refund,0) or summary['refund_due_cents']!=max(paid-refund-total+credit,0):invalid()
    entries=summary['payments']
    if not isinstance(entries,list) or len(entries)>500:invalid()
    rows=[];seen=set();previous=None
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={'number','date','amount_cents'}:invalid()
        number=entry['number'];raw=entry['date'];cents=entry['amount_cents']
        if not isinstance(number,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',number) or number in seen:invalid()
        if type(cents) is not int or not 0<cents<=10**14:invalid()
        if not isinstance(raw,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',raw):invalid()
        try:day=date.fromisoformat(raw)
        except ValueError:invalid()
        key=(raw,number)
        if previous is not None and key<previous:invalid()
        previous=key;seen.add(number)
        rows.append({**entry,'date_label':f'{day.day} {MONTHS[day.month-1]} {day.year}'})
    if sum(p['amount_cents'] for p in rows)!=paid:invalid()
    if record['status']!='issued':
        if paid or credit or refund:invalid()
        return None
    due=summary['balance_cents'];net=paid-refund
    if summary['refund_due_cents']:status='Refund due'
    elif total==0:status='No amount due'
    elif credit==total:status='Credited in full'
    elif due==0 and credit:status='Settled — payments and credits'
    elif due==0:status='Paid in full'
    elif net:status='Partially paid'
    else:status='Unpaid'
    date_paid=rows[-1]['date_label'] if status=='Paid in full' and rows else ''
    last_payment=rows[-1]['date_label'] if rows else ''
    totals=[{'label':'Payments recorded','amount_cents':paid}]
    if credit:totals.append({'label':'Credits applied','amount_cents':credit})
    if refund:totals.append({'label':'Payments refunded','amount_cents':refund})
    totals.append({'label':'Balance due','amount_cents':due})
    if summary['refund_due_cents']:totals.append({'label':'Refund due','amount_cents':summary['refund_due_cents']})
    return {'invoice_id':record['id'],'invoice_version':record['version'],'ledger_version':summary['ledger_version'],
            'status':('Test — ' if record['is_test'] else '')+status,'date_paid':date_paid,'last_payment_date':last_payment,
            'payments':rows,'totals':totals,'note':'Test entries only. No amount is payable.' if record['is_test'] else 'Recorded payments only. Reversed payments are excluded.'}
