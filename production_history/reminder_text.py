"""Reviewed reminder wording. Templates are plain text with a fixed token set."""
import re
from datetime import date
from email_delivery import clean

TOKENS={'customer','invoice','due_date','balance','days_overdue','days_until_due'}
REQUIRED={'invoice','due_date','balance'}
DEFAULT_MESSAGES={
 'before_due': 'Hello {customer},\n\nThis is a friendly reminder that invoice {invoice}, with a remaining balance of {balance}, is due on {due_date}.\n\nPlease arrange payment by the due date. If payment has already been made, please reply with the payment reference so we can update our records.\n\nThank you for your business.\n\nKind regards,\nCustom U',
 'due_today': 'Hello {customer},\n\nThis is a friendly reminder that payment for invoice {invoice} is due today, {due_date}. The remaining balance is {balance}.\n\nPlease arrange payment today. If payment has already been made, please reply with the payment reference so we can update our records.\n\nThank you for your business.\n\nKind regards,\nCustom U',
 'overdue': 'Hello {customer},\n\nOur records show that invoice {invoice}, due on {due_date}, is now {days_overdue} days overdue. The remaining balance is {balance}.\n\nPlease arrange payment at your earliest convenience. If payment has already been made, or you need to discuss the balance, please reply so we can assist.\n\nThank you.\n\nKind regards,\nCustom U'
}

def validate_messages(messages):
    if not isinstance(messages,dict) or set(messages)!=set(DEFAULT_MESSAGES):raise ValueError('INVALID_REMINDER_MESSAGES')
    for message in messages.values():
        if clean(message,2000)!=message:raise ValueError('INVALID_REMINDER_MESSAGES')
        names=set(re.findall(r'\{([a-z_]+)\}',message))
        if not REQUIRED<=names or not names<=TOKENS or re.search(r'[{}]',re.sub(r'\{[a-z_]+\}','',message)):raise ValueError('INVALID_REMINDER_MESSAGES')
    return messages

def phase(stage):return 'before_due' if stage<0 else 'due_today' if stage==0 else 'overdue'
def stage_label(stage):return str(-stage)+' days before due date' if stage<0 else 'Due date' if stage==0 else str(stage)+' days past due'
def render_message(messages,row,stage,today):
    validate_messages(messages)
    age=(date.fromisoformat(today)-date.fromisoformat(row['due_date'])).days
    values={'customer':row['customer_name'],'invoice':row['number'],'due_date':row['due_date'],'balance':'BSD '+format(row['balance_cents']/100,',.2f'),'days_overdue':str(max(age,0)),'days_until_due':str(max(-age,0))}
    # Substitute once: braces in a customer name remain literal text.
    return clean(re.sub(r'\{([a-z_]+)\}',lambda m:values[m.group(1)],messages[phase(stage)]),3800)
